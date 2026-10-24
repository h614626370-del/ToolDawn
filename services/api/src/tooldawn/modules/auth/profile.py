import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from tooldawn.modules.admin.repository import audit
from tooldawn.modules.auth.dependencies import (
    COOKIE_NAME,
    auth_service,
    check_origin,
    client_ip,
    require_user,
)
from tooldawn.modules.auth.models import SessionRecord, UserRecord
from tooldawn.modules.auth.passwords import hash_password, verify_password
from tooldawn.modules.auth.schemas import (
    CredentialsInput,
    PasswordInput,
    PasswordLogin,
    ProfileInput,
    UserResponse,
)
from tooldawn.modules.auth.security import token_digest

router = APIRouter(tags=["profile"])
User = Annotated[UserResponse, Depends(require_user)]
guard = [Depends(check_origin)]


def set_session(request, response, token):
    settings = request.app.state.settings
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/api/v1",
    )


@router.post("/auth/password", response_model=UserResponse, dependencies=guard)
async def password_login(data: PasswordLogin, request: Request, response: Response):
    service = auth_service(request)
    await service.limiter.check("password-ip", client_ip(request), 20, 600)
    await service.limiter.check("password-email", str(data.email), 10, 600)
    async with service.repository.sessions() as db:
        row = await db.scalar(select(UserRecord).where(UserRecord.email == str(data.email)))
        encoded = row.password_hash if row else None
    valid = await asyncio.to_thread(verify_password, data.password, encoded)
    if not valid:
        raise HTTPException(400, "账号或密码不正确。")
    token = secrets.token_urlsafe(32)
    async with service.repository.sessions.begin() as db:
        row = await db.scalar(
            select(UserRecord).where(UserRecord.email == str(data.email)).with_for_update()
        )
        if not row or row.disabled or row.password_hash != encoded:
            raise HTTPException(400, "账号或密码不正确。")
        previous = request.cookies.get(COOKIE_NAME)
        if previous:
            await db.execute(
                delete(SessionRecord).where(SessionRecord.token_digest == token_digest(previous))
            )
        now = datetime.now(UTC)
        db.add(
            SessionRecord(
                token_digest=token_digest(token),
                user_id=row.id,
                created_at=now,
                expires_at=now + timedelta(days=service.settings.session_days),
            )
        )
        audit(db, row.id, "auth.password_login", str(row.id), [])
        result = UserResponse.model_validate(row)
    set_session(request, response, token)
    return result


@router.patch("/me/profile", response_model=UserResponse, dependencies=guard)
async def profile(data: ProfileInput, request: Request, user: User):
    async with auth_service(request).repository.sessions.begin() as db:
        row = await db.get(UserRecord, user.id, with_for_update=True)
        row.display_name = data.display_name.strip()
        audit(db, user.id, "profile.update", str(user.id), ["display_name"])
        return UserResponse.model_validate(row)


async def update_credentials(data, request, response, user, change_email=False):
    service = auth_service(request)
    await service.limiter.check("password-change", str(user.id), 10, 600)
    async with service.repository.sessions() as db:
        row = await db.get(UserRecord, user.id)
        encoded = row.password_hash
    if encoded and not await asyncio.to_thread(verify_password, data.current_password, encoded):
        raise HTTPException(400, "当前密码不正确。")
    if data.new_password == data.current_password:
        raise HTTPException(422, "新密码不能与当前密码相同。")
    password = await asyncio.to_thread(hash_password, data.new_password)
    token = secrets.token_urlsafe(32)
    try:
        async with service.repository.sessions.begin() as db:
            row = await db.get(UserRecord, user.id, with_for_update=True)
            if row.password_hash != encoded or row.disabled:
                raise HTTPException(409, "账户已变更，请重新登录。")
            if change_email:
                if not row.is_superadmin:
                    raise HTTPException(403, "需要超级管理员权限。")
                row.email = str(data.email).strip().lower()
            row.password_hash, row.must_change_password = password, False
            await db.execute(delete(SessionRecord).where(SessionRecord.user_id == user.id))
            now = datetime.now(UTC)
            db.add(
                SessionRecord(
                    token_digest=token_digest(token),
                    user_id=row.id,
                    created_at=now,
                    expires_at=now + timedelta(days=service.settings.session_days),
                )
            )
            audit(
                db,
                user.id,
                "auth.credentials_change",
                str(user.id),
                ["password_hash", "email"] if change_email else ["password_hash"],
            )
            result = UserResponse.model_validate(row)
    except IntegrityError:
        raise HTTPException(409, "该邮箱已被使用。") from None
    if user.must_change_password and user.is_superadmin:
        try:
            Path(service.settings.bootstrap_credentials).unlink(missing_ok=True)
        except OSError:
            logging.getLogger("tooldawn.setup").warning(
                "Could not remove bootstrap credentials file"
            )
    set_session(request, response, token)
    return result


@router.put("/me/password", response_model=UserResponse, dependencies=guard)
async def password(data: PasswordInput, request: Request, response: Response, user: User):
    return await update_credentials(data, request, response, user)


@router.put("/me/admin-credentials", response_model=UserResponse, dependencies=guard)
async def credentials(data: CredentialsInput, request: Request, response: Response, user: User):
    return await update_credentials(data, request, response, user, change_email=True)


@router.get("/me/sessions")
async def sessions(request: Request, user: User):
    current = token_digest(request.cookies.get(COOKIE_NAME, ""))
    async with auth_service(request).repository.sessions() as db:
        rows = await db.scalars(
            select(SessionRecord)
            .where(
                SessionRecord.user_id == user.id,
                SessionRecord.expires_at > datetime.now(UTC),
            )
            .order_by(SessionRecord.created_at.desc())
            .limit(100)
        )
        return [
            {
                "created_at": row.created_at,
                "expires_at": row.expires_at,
                "current": row.token_digest == current,
            }
            for row in rows
        ]


@router.delete("/me/sessions/others", status_code=204, dependencies=guard)
async def revoke_others(request: Request, user: User):
    current = token_digest(request.cookies.get(COOKIE_NAME, ""))
    async with auth_service(request).repository.sessions.begin() as db:
        await db.get(UserRecord, user.id, with_for_update=True)
        await db.execute(
            delete(SessionRecord).where(
                SessionRecord.user_id == user.id,
                SessionRecord.token_digest != current,
            )
        )
        audit(db, user.id, "auth.revoke_sessions", str(user.id), ["sessions"])
