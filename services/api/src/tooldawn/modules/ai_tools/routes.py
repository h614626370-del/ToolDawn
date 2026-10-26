import asyncio
import hashlib
import hmac
import json
from dataclasses import replace
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from tooldawn.modules.ai_tools.failover import generate_with_group
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
        raise HTTPException(503, "服务暂时不可用，请稍后重试。")
    return request.app.state.text_runs


@router.get("/{slug}")
async def tool_config(slug: str, request: Request):
    tool = await definition(request, slug)
    config = await runtime(request)
    override = config.tool_overrides.get(slug)
    accounts = getattr(request.app.state, "accounts", None)
    plan = await accounts.group_plan(slug) if accounts else None
    identity, settings = (
        await accounts.resolve(slug, config) if accounts and plan is None else (None, None)
    )
    available = (
        bool(plan[2])
        if plan is not None
        else (bool(settings) if identity else request.app.state.model_gateway.enabled)
    )
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
    fingerprint = hmac.new(
        request.app.state.settings.auth_secret.get_secret_value().encode(),
        json.dumps(
            {"slug": slug, **data.model_dump(mode="json", exclude={"request_key"})},
            sort_keys=True,
            ensure_ascii=False,
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
    previous = await runs.previous(user.id, data.request_key, fingerprint)
    if previous:
        return previous
    accounts = getattr(request.app.state, "accounts", None)
    plan = await accounts.group_plan(slug) if accounts else None
    identity, settings = (
        (await accounts.resolve(slug, config)) if accounts and plan is None else (None, None)
    )
    gateway = request.app.state.model_gateway
    if (plan is not None and not plan[2]) or (
        plan is None and ((identity and not settings) or (not identity and not gateway.enabled))
    ):
        raise HTTPException(503, "服务暂时不可用，请稍后重试。")
    await request.app.state.auth.limiter.check(
        "ai-run", str(user.id), config.ai_requests_per_minute, 60
    )
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
        output = (
            await generate_with_group(accounts, runs, user.id, run.id, plan, tool, data)
            if plan is not None
            else await gateway.generate(tool, data)
        )
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
    from tooldawn.modules.image_tools.models import ImageJob

    async with repository(request).sessions() as db:
        is_image = await db.get(ImageJob, run_id) is not None
    if is_image:
        await request.app.state.image_runs.image(user.id, run_id, delete=True)
        return Response(status_code=204)
    await repository(request).clear(user.id, run_id)
    return Response(status_code=204)
