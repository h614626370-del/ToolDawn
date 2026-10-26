from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from tooldawn.modules.auth.dependencies import check_origin, require_admin, require_user
from tooldawn.modules.auth.schemas import UserResponse
from tooldawn.modules.billing.gateway import StripeGateway
from tooldawn.modules.billing.repository import BillingRepository
from tooldawn.modules.billing.schemas import (
    AdjustmentInput,
    AdminOrderPage,
    Checkout,
    CheckoutInput,
    CreditEntry,
    CreditPage,
    Order,
    OrderPage,
    Packages,
    Wallet,
)
from tooldawn.modules.operations.routes import validate_range
from tooldawn.modules.operations.settings import effective_settings

router = APIRouter(tags=["billing"])
User = Annotated[UserResponse, Depends(require_user)]
Admin = Annotated[UserResponse, Depends(require_admin)]
Offset = Annotated[int, Query(ge=0, le=100000)]
Limit = Annotated[int, Query(ge=1, le=100)]


def repository(request: Request) -> BillingRepository:
    if request.app.state.billing is None:
        raise HTTPException(503, "服务暂时不可用，请稍后重试。")
    return request.app.state.billing


Repo = Annotated[BillingRepository, Depends(repository)]


@router.get("/billing/packages", response_model=Packages)
async def packages(request: Request):
    settings = await effective_settings(request)
    from tooldawn.modules.billing.providers import ProviderRepository

    control = getattr(request.app.state, "control", None)
    providers = await ProviderRepository(control).listing(public=True) if control else []
    return Packages(
        enabled=(
            bool(settings.stripe_secret_key and settings.stripe_webhook_secret) or bool(providers)
        )
        and request.app.state.auth is not None
        and bool(settings.credit_packages),
        items=settings.credit_packages,
    )


@router.get("/billing/wallet", response_model=Wallet)
async def wallet(user: User, repo: Repo):
    return Wallet(balance=await repo.balance(user.id))


@router.get("/billing/entries", response_model=CreditPage)
async def entries(user: User, repo: Repo, offset: Offset = 0, limit: Limit = 20):
    return await repo.entries(user.id, offset, limit)


@router.get("/billing/orders", response_model=OrderPage)
async def orders(user: User, repo: Repo, offset: Offset = 0, limit: Limit = 20):
    return await repo.orders(user.id, offset, limit)


@router.get("/billing/orders/{order_id}", response_model=Order)
async def order(order_id: UUID, user: User, repo: Repo):
    return await repo.order(order_id, user.id)


@router.post("/billing/checkout", response_model=Checkout, dependencies=[Depends(check_origin)])
async def checkout(data: CheckoutInput, user: User, repo: Repo, request: Request):
    settings = await effective_settings(request)
    if data.provider_id:
        from tooldawn.modules.billing.provider_gateway import ProviderGateway
        from tooldawn.modules.billing.providers import ProviderRepository

        control = getattr(request.app.state, "control", None)
        if not control:
            raise HTTPException(503, "支付尚未开放。")
        providers = ProviderRepository(control)
        record = await repo.prepare_order(
            user.id,
            data.request_key,
            data.package_id,
            settings.credit_packages,
            data.provider_id,
            data.payment_method,
        )
        provider = await providers.get(record.provider_id)
        gateway = ProviderGateway(provider, providers.decode(provider), settings)
        return await repo.provider_checkout(record.id, user.id, gateway)
    gateway = gateway_for(request, settings)
    if not gateway.enabled:
        raise HTTPException(503, "支付尚未开放。")
    record = await repo.prepare_order(
        user.id,
        data.request_key,
        data.package_id,
        settings.credit_packages,
        payment_method=data.payment_method,
    )
    if record.checkout_url:
        return Checkout(order_id=record.id, url=record.checkout_url)
    session_id, url = await gateway.checkout(record)
    await repo.attach_checkout(record.id, session_id, url)
    return Checkout(order_id=record.id, url=url)


@router.post("/billing/webhook")
async def webhook(request: Request, repo: Repo):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 262144:
            raise HTTPException(413, "支付通知过大。")
    gateway = gateway_for(request, await effective_settings(request))
    event = gateway.verify(bytes(body), request.headers.get("stripe-signature", ""))
    if event["type"] in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed",
        "checkout.session.expired",
    }:
        await repo.fulfill(event["data"]["object"], event["type"])
    return {"received": True}


def gateway_for(request, settings):
    base = request.app.state.settings
    if (settings.stripe_secret_key, settings.stripe_webhook_secret) == (
        base.stripe_secret_key,
        base.stripe_webhook_secret,
    ):
        return request.app.state.gateway
    return StripeGateway(settings)


@router.get("/admin/billing/orders", response_model=AdminOrderPage)
async def admin_orders(
    actor: Admin,
    repo: Repo,
    offset: Offset = 0,
    limit: Limit = 20,
    q: Annotated[str, Query(max_length=100)] = "",
    status: Literal["pending", "paid", "expired", "failed"] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
):
    validate_range(start, end)
    return await repo.orders(None, offset, limit, q, status, start, end)


@router.get("/admin/billing/statistics")
async def admin_statistics(
    actor: Admin,
    repo: Repo,
    q: Annotated[str, Query(max_length=100)] = "",
    status: Literal["pending", "paid", "expired", "failed"] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
):
    validate_range(start, end)
    return await repo.statistics(q, status, start, end)


@router.get("/admin/users/{user_id}/wallet", response_model=Wallet)
async def admin_wallet(user_id: UUID, actor: Admin, repo: Repo):
    return Wallet(balance=await repo.balance(user_id))


@router.get("/admin/users/{user_id}/credits", response_model=CreditPage)
async def admin_entries(
    user_id: UUID, actor: Admin, repo: Repo, offset: Offset = 0, limit: Limit = 20
):
    return await repo.entries(user_id, offset, limit)


@router.post(
    "/admin/users/{user_id}/credits",
    response_model=CreditEntry,
    dependencies=[Depends(check_origin)],
)
async def adjust(user_id: UUID, data: AdjustmentInput, actor: Admin, repo: Repo):
    return await repo.adjust(user_id, data, actor.id)
