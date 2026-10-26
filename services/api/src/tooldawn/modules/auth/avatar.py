import asyncio
import io
import warnings
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from PIL import Image, ImageOps
from sqlalchemy import delete

from tooldawn.modules.admin.repository import audit
from tooldawn.modules.auth.dependencies import auth_service, check_origin, require_user
from tooldawn.modules.auth.models import UserAvatar, UserRecord
from tooldawn.modules.auth.schemas import UserResponse

router = APIRouter(prefix="/me/avatar", tags=["profile"])
User = Annotated[UserResponse, Depends(require_user)]
MAX_AVATAR = 4 * 1024 * 1024


def normalize_avatar(content: bytes) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if (
                    image.format not in {"PNG", "JPEG", "WEBP"}
                    or getattr(image, "n_frames", 1) != 1
                    or image.width * image.height > 16_000_000
                ):
                    raise ValueError()
                image.load()
                square = ImageOps.fit(
                    ImageOps.exif_transpose(image).convert("RGBA"),
                    (256, 256),
                    method=Image.Resampling.LANCZOS,
                )
                clean = Image.frombytes("RGBA", square.size, square.tobytes())
                output = io.BytesIO()
                clean.save(output, "WEBP", quality=85)
                return output.getvalue()
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "头像无法读取，请选择静态 PNG、JPG 或 WebP 图片。") from None


@router.get("")
async def get_avatar(request: Request, user: User):
    async with auth_service(request).repository.sessions() as db:
        row = await db.get(UserAvatar, user.id)
        if not row:
            raise HTTPException(404, "头像不存在。")
        return Response(
            row.image,
            media_type="image/webp",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )


@router.put("", response_model=UserResponse, dependencies=[Depends(check_origin)])
async def put_avatar(request: Request, user: User):
    service = auth_service(request)
    await service.limiter.check("avatar-upload", str(user.id), 10, 60)
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_AVATAR:
            raise HTTPException(413, "请选择 4 MB 以内的头像。")
    image = await asyncio.to_thread(normalize_avatar, bytes(content))
    async with service.repository.sessions.begin() as db:
        owner = await db.get(UserRecord, user.id, with_for_update=True)
        if not owner or owner.disabled:
            raise HTTPException(403, "账户已禁用。")
        row = await db.get(UserAvatar, user.id)
        if row:
            row.image = image
        else:
            db.add(UserAvatar(user_id=user.id, image=image))
        owner.avatar_revision = uuid4()
        audit(db, user.id, "profile.avatar.update", str(user.id), ["avatar"])
        return UserResponse.model_validate(owner)


@router.delete("", response_model=UserResponse, dependencies=[Depends(check_origin)])
async def remove_avatar(request: Request, user: User):
    async with auth_service(request).repository.sessions.begin() as db:
        owner = await db.get(UserRecord, user.id, with_for_update=True)
        if not owner or owner.disabled:
            raise HTTPException(403, "账户已禁用。")
        await db.execute(delete(UserAvatar).where(UserAvatar.user_id == user.id))
        owner.avatar_revision = None
        audit(db, user.id, "profile.avatar.remove", str(user.id), ["avatar"])
        return UserResponse.model_validate(owner)
