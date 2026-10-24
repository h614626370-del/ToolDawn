import asyncio
import hashlib
import hmac
import json
from dataclasses import replace
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from tooldawn.modules.ai_tools.gateway import ModelFailure, ModelGateway
from tooldawn.modules.ai_tools.registry import TOOLS
from tooldawn.modules.ai_tools.schemas import Run, RunInput
from tooldawn.modules.auth.dependencies import check_origin, require_user
from tooldawn.modules.auth.schemas import UserResponse
from tooldawn.modules.operations.settings import runtime

router = APIRouter(prefix="/ai-tools", tags=["ai-tools"])
User = Annotated[UserResponse, Depends(require_user)]


async def definition(request: Request, slug: str):
    tool = TOOLS.get(slug)
    listed = await request.app.state.catalog.get_tool(slug)
    if not tool or not listed or listed.kind != "internal" or listed.status != "available":
        raise HTTPException(404, "工具未开放或已下架。")
    return tool


def repository(request: Request):
    if request.app.state.text_runs is None:
        raise HTTPException(503, "积分服务需要数据库连接。")
    return request.app.state.text_runs


@router.get("/{slug}")
async def tool_config(slug: str, request: Request):
    tool = await definition(request, slug)
    config = await runtime(request)
    override = config.tool_overrides.get(slug)
    identity, settings = (
        await request.app.state.accounts.resolve(slug, config)
        if getattr(request.app.state, "accounts", None)
        else (None, None)
    )
    available = bool(settings) if identity else request.app.state.model_gateway.enabled
    return {
        **tool.public(),
        "enabled": available
        and config.ai_enabled
        and (not override or override.enabled)
        and request.app.state.text_runs is not None
        and request.app.state.auth is not None,
        "cost": override.cost if override and override.cost is not None else config.ai_tool_cost,
        "max_length": 12000,
    }


@router.get("/{slug}/runs", response_model=list[Run])
async def history(slug: str, request: Request, user: User):
    await definition(request, slug)
    return await repository(request).history(user.id, slug)


@router.post("/{slug}/runs", response_model=Run, dependencies=[Depends(check_origin)])
async def generate(slug: str, data: RunInput, request: Request, user: User):
    tool = await definition(request, slug)
    if data.style not in tool.styles:
        raise HTTPException(422, "请求参数不正确，请检查后重试。")
    runs = repository(request)
    config = await runtime(request)
    override = config.tool_overrides.get(slug)
    if not config.ai_enabled or (override and not override.enabled):
        raise HTTPException(503, "该工具暂时停用。")
    if override and override.instruction.strip():
        tool = replace(tool, instruction=override.instruction)
    identity, settings = (
        await request.app.state.accounts.resolve(slug, config)
        if getattr(request.app.state, "accounts", None)
        else (None, None)
    )
    gateway = request.app.state.model_gateway
    if (identity and not settings) or (not identity and not gateway.enabled):
        raise HTTPException(503, "AI 服务尚未配置，请稍后再试。")
    await request.app.state.auth.limiter.check(
        "ai-run", str(user.id), config.ai_requests_per_minute, 60
    )
    fingerprint = hmac.new(
        request.app.state.settings.auth_secret.get_secret_value().encode(),
        json.dumps(
            {"slug": slug, **data.model_dump(mode="json", exclude={"request_key"})},
            sort_keys=True,
            ensure_ascii=False,
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
    run, fresh = await runs.prepare(
        user.id,
        slug,
        data,
        fingerprint,
        override.cost if override and override.cost is not None else config.ai_tool_cost,
        identity,
        settings.llm_model if settings else request.app.state.settings.llm_model,
    )
    if not fresh:
        return run
    temporary_gateway = None
    try:
        if settings:
            temporary_gateway = ModelGateway(settings)
            gateway = temporary_gateway
        output = await gateway.generate(tool, data)
    except ModelFailure:
        return await runs.finish(user.id, run.id, None)
    except asyncio.CancelledError:
        await asyncio.shield(runs.finish(user.id, run.id, None))
        raise
    except Exception:
        await runs.finish(user.id, run.id, None)
        raise
    finally:
        if temporary_gateway:
            await temporary_gateway.close()
    return await runs.finish(user.id, run.id, output)


@router.delete("/runs/{run_id}/output", status_code=204, dependencies=[Depends(check_origin)])
async def clear_output(run_id: UUID, request: Request, user: User):
    await repository(request).clear(user.id, run_id)
    return Response(status_code=204)
