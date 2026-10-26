import asyncio
import hashlib
import hmac
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from tooldawn.modules.auth.dependencies import check_origin, require_user
from tooldawn.modules.auth.schemas import UserResponse
from tooldawn.modules.image_tools.repository import SLUG
from tooldawn.modules.image_tools.schemas import ImageInput, ImageRun
from tooldawn.modules.image_tools.uploads import MAX_UPLOAD, normalize_reference
from tooldawn.modules.operations.settings import runtime

router = APIRouter(prefix="/image-tools", tags=["image-tools"])
User = Annotated[UserResponse, Depends(require_user)]


async def config(request, mode="generate"):
    listed = await request.app.state.catalog.get_tool(SLUG)
    if not listed or listed.status != "available":
        raise HTTPException(404, "工具未开放或已下架。")
    state = request.app.state
    if not state.image_runs:
        raise HTTPException(503, "服务暂时不可用，请稍后重试。")
    settings = await runtime(request)
    override = settings.tool_overrides.get(SLUG)
    capability = "image_edit" if mode == "edit" else "image_generate"
    plan = await state.accounts.group_plan(SLUG, capability)
    enabled = bool(
        settings.ai_enabled
        and (not override or override.enabled)
        and plan
        and plan[1] == capability
        and plan[2]
        and state.auth
    )
    cost = override.cost if override and override.cost is not None else settings.ai_tool_cost
    return settings, plan, {"enabled": enabled, "cost": cost}


@router.get("/image-generate")
async def configuration(request: Request):
    public = (await config(request))[2]
    edit = (await config(request, "edit"))[2]
    return {
        **public,
        "edit_enabled": edit["enabled"],
        "costs": {
            quality: public["cost"] * multiplier
            for quality, multiplier in (("low", 1), ("medium", 2), ("high", 4))
        },
    }


@router.get("/image-generate/runs", response_model=list[ImageRun])
async def history(request: Request, user: User):
    await config(request)
    return await request.app.state.image_runs.history(user.id)


@router.post("/image-generate/runs", response_model=ImageRun, dependencies=[Depends(check_origin)])
async def generate(data: ImageInput, request: Request, user: User):
    settings, plan, public = await config(request, data.mode)
    repo = request.app.state.image_runs
    fingerprint = hmac.new(
        request.app.state.settings.auth_secret.get_secret_value().encode(),
        (SLUG + data.model_dump_json(exclude={"request_key"})).encode(),
        hashlib.sha256,
    ).hexdigest()
    previous = await repo.previous(user.id, data.request_key, fingerprint)
    if previous:
        return previous
    if not public["enabled"]:
        raise HTTPException(503, "服务暂时不可用，请稍后重试。")
    await request.app.state.auth.limiter.check(
        "ai-run", str(user.id), settings.ai_requests_per_minute, 60
    )
    cost = public["cost"] * {"low": 1, "medium": 2, "high": 4}[data.quality]
    return await repo.prepare(user.id, data, fingerprint, cost, plan[0])


@router.post("/references", dependencies=[Depends(check_origin)])
async def upload(request: Request, user: User):
    await config(request, "edit")
    await request.app.state.auth.limiter.check("image-upload", str(user.id), 15, 60)
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_UPLOAD:
            raise HTTPException(413, "请选择 8 MB 以内的图片。")
    normalized = await asyncio.to_thread(normalize_reference, bytes(content))
    return await request.app.state.image_runs.upload(user.id, normalized)


@router.delete("/references/{reference_id}", status_code=204, dependencies=[Depends(check_origin)])
async def remove_reference(reference_id: UUID, request: Request, user: User):
    await request.app.state.image_runs.remove_reference(user.id, reference_id)
    return Response(status_code=204)


@router.get("/runs/{run_id}/image")
async def image(run_id: UUID, request: Request, user: User, download: bool = False):
    content = await request.app.state.image_runs.image(user.id, run_id)
    disposition = "attachment" if download else "inline"
    return Response(
        content,
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'{disposition}; filename="tooldawn-{run_id}.png"',
        },
    )


@router.delete("/runs/{run_id}/image", status_code=204, dependencies=[Depends(check_origin)])
async def clear(run_id: UUID, request: Request, user: User):
    await request.app.state.image_runs.image(user.id, run_id, delete=True)
    return Response(status_code=204)
