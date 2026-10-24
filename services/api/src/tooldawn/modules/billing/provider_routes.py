from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from tooldawn.modules.auth.dependencies import check_origin, require_superadmin, require_user
from tooldawn.modules.auth.schemas import UserResponse
from tooldawn.modules.billing.provider_config import CATALOG, ProviderInput
from tooldawn.modules.billing.provider_gateway import ProviderGateway
from tooldawn.modules.billing.providers import ProviderRepository
from tooldawn.modules.billing.routes import Repo
from tooldawn.modules.operations.settings import effective_settings

router = APIRouter(tags=["payment providers"])
Super = Annotated[UserResponse, Depends(require_superadmin)]
User = Annotated[UserResponse, Depends(require_user)]
guard = [Depends(check_origin)]


def repository(request: Request):
    control = getattr(request.app.state, "control", None)
    if not control:
        raise HTTPException(503, "管理服务需要数据库连接。")
    return ProviderRepository(control)


Providers = Annotated[ProviderRepository, Depends(repository)]


@router.get("/admin/billing/provider-types")
async def types(actor: Super):
    return [{"kind": key, **value} for key, value in CATALOG.items()]


@router.get("/admin/billing/providers")
async def listing(actor: Super, providers: Providers):
    return {"items": await providers.listing()}


@router.post("/admin/billing/providers", dependencies=guard)
async def create(data: ProviderInput, actor: Super, providers: Providers):
    return await providers.save(data, actor.id)


@router.put("/admin/billing/providers/{identity}", dependencies=guard)
async def update(identity: UUID, data: ProviderInput, actor: Super, providers: Providers):
    return await providers.save(data, actor.id, identity)


@router.delete("/admin/billing/providers/{identity}", dependencies=guard)
async def delete(
    identity: UUID, actor: Super, providers: Providers, revision: Annotated[int, Query(ge=1)]
):
    await providers.delete(identity, revision, actor.id)
    return {"deleted": True}


@router.get("/billing/methods")
async def methods(request: Request):
    control = getattr(request.app.state, "control", None)
    values = await ProviderRepository(control).listing(public=True) if control else []
    settings = await effective_settings(request)
    if settings.stripe_secret_key and settings.stripe_webhook_secret:
        values.append(
            dict(
                id=None,
                name="Stripe",
                kind="stripe",
                methods=["card"],
                currencies=["usd", "eur", "cny"],
            )
        )
    return {"items": values}


@router.post("/billing/orders/{identity}/resume", dependencies=guard)
async def resume(identity: UUID, user: User, repo: Repo):
    return await repo.provider_checkout(identity, user.id)


@router.api_route("/billing/providers/{identity}/webhook", methods=["GET", "POST"])
async def webhook(identity: UUID, request: Request, providers: Providers, repo: Repo):
    provider = await providers.get(identity)
    if request.method == "GET" and provider.kind != "easypay":
        raise HTTPException(405, "请求方式不正确。")
    body = bytearray()
    if request.method == "GET":
        body.extend(request.scope["query_string"])
    else:
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 262144:
                raise HTTPException(413, "支付通知过大。")
    if len(body) > 262144:
        raise HTTPException(413, "支付通知过大。")
    gateway = ProviderGateway(provider, providers.decode(provider), request.app.state.settings)
    notice = gateway.notification(bytes(body), request.headers)
    if notice:
        await repo.fulfill_provider(identity, notice)
    if provider.kind in {"easypay", "alipay"}:
        return PlainTextResponse("success")
    if provider.kind == "wxpay":
        return {"code": "SUCCESS", "message": "成功"}
    return {"received": True}
