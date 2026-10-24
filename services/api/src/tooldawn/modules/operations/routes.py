from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from tooldawn.modules.ai_tools.registry import TOOLS
from tooldawn.modules.auth.dependencies import (
    auth_service,
    check_origin,
    require_admin,
    require_superadmin,
    require_user,
)
from tooldawn.modules.auth.schemas import UserResponse
from tooldawn.modules.operations.schemas import (
    AccountInput,
    ConfigInput,
    PaymentConfigInput,
    ReplyInput,
    TicketInput,
    TicketState,
)
from tooldawn.modules.operations.settings import runtime

router = APIRouter(tags=["operations"])
User = Annotated[UserResponse, Depends(require_user)]
Admin = Annotated[UserResponse, Depends(require_admin)]
Super = Annotated[UserResponse, Depends(require_superadmin)]
Offset = Annotated[int, Query(ge=0, le=100000)]
Limit = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=100)]
RunStatus = Literal["running", "succeeded", "failed"]
TicketStatus = Literal["open", "processing", "replied", "closed"]
guard = [Depends(check_origin)]


def required(request, name):
    value = getattr(request.app.state, name, None)
    if value is None:
        raise HTTPException(503, "管理服务需要数据库连接。")
    return value


@router.get("/site")
async def site(request: Request):
    repo = getattr(request.app.state, "control", None)
    if repo:
        return await repo.public()
    config = await runtime(request)
    return config.model_dump(
        include={
            "site_name",
            "site_logo",
            "announcement",
            "contact_email",
            "registration_enabled",
            "ai_enabled",
            "tickets_enabled",
        }
    )


@router.get("/admin/settings")
async def settings(request: Request, actor: Super):
    return await required(request, "control").view()


@router.put("/admin/settings", dependencies=guard)
async def save_settings(data: ConfigInput, request: Request, actor: Super):
    return await required(request, "control").save(data, actor.id)


@router.get("/admin/model-accounts")
async def accounts(request: Request, actor: Super):
    return await required(request, "accounts").listing()


@router.get("/admin/billing/config")
async def payment_config(request: Request, actor: Super):
    return await required(request, "control").payment_view()


@router.put("/admin/billing/config", dependencies=guard)
async def save_payment_config(data: PaymentConfigInput, request: Request, actor: Super):
    return await required(request, "control").save(data, actor.id)


@router.post("/admin/model-accounts", dependencies=guard)
async def create_account(data: AccountInput, request: Request, actor: Super):
    return await required(request, "accounts").save(data, actor.id)


@router.put("/admin/model-accounts/{identity}", dependencies=guard)
async def save_account(identity: UUID, data: AccountInput, request: Request, actor: Super):
    return await required(request, "accounts").save(data, actor.id, identity)


@router.post("/admin/model-accounts/{identity}/test", dependencies=guard)
async def test_account(identity: UUID, request: Request, actor: Super):
    await auth_service(request).limiter.check("model-test", str(actor.id), 10, 60)
    return await required(request, "accounts").test(identity, actor.id)


@router.get("/admin/tool-definitions")
async def definitions(actor: Super):
    return [
        {"slug": tool.slug, "name": tool.name, "instruction": tool.instruction}
        for tool in TOOLS.values()
    ]


@router.get("/admin/dashboard")
async def dashboard(request: Request, actor: Admin, days: int = 7):
    if days not in (7, 30):
        raise HTTPException(422, "日期范围不正确。")
    return await required(request, "analytics").dashboard(days)


@router.get("/admin/monitoring")
async def monitoring(request: Request, actor: Admin):
    return await required(request, "analytics").monitoring(request.app.state)


@router.get("/admin/audit")
async def audit(
    request: Request,
    actor: Admin,
    q: Search = "",
    offset: Offset = 0,
    limit: Limit = 20,
    start: datetime | None = None,
    end: datetime | None = None,
):
    validate_range(start, end)
    return await required(request, "analytics").audit(q, offset, limit, start, end)


def validate_range(start, end):
    if any(value is not None and value.utcoffset() is None for value in (start, end)):
        raise HTTPException(422, "日期范围不正确。")
    if start and end and start >= end:
        raise HTTPException(422, "日期范围不正确。")


async def usage(request, owner, q, status, tool, start, end, offset, limit):
    validate_range(start, end)
    return await required(request, "analytics").usage(
        owner,
        q,
        status,
        tool,
        start,
        end,
        offset,
        limit,
    )


@router.get("/admin/usage")
async def admin_usage(
    request: Request,
    actor: Admin,
    q: Search = "",
    status: RunStatus | None = None,
    tool: Annotated[str | None, Query(max_length=80)] = None,
    start: datetime | None = None,
    end: datetime | None = None,
    offset: Offset = 0,
    limit: Limit = 20,
):
    return await usage(request, None, q, status, tool, start, end, offset, limit)


@router.get("/me/usage")
async def my_usage(
    request: Request,
    user: User,
    status: RunStatus | None = None,
    tool: Annotated[str | None, Query(max_length=80)] = None,
    start: datetime | None = None,
    end: datetime | None = None,
    offset: Offset = 0,
    limit: Limit = 20,
):
    # Reconcile expired requests and refunds before displaying the user's records.
    runs = required(request, "text_runs")
    async with runs.sessions.begin() as db:
        await runs.billing._lock_user(db, user.id)
        await runs._expire(db, user.id)
    return await usage(request, user.id, "", status, tool, start, end, offset, limit)


@router.get("/me/usage/{identity}")
async def output(identity: UUID, request: Request, user: User):
    return await required(request, "analytics").output(identity, user.id)


async def ticket_write(request, user, create=False):
    if not (await runtime(request)).tickets_enabled:
        raise HTTPException(503, "工单服务暂时关闭。")
    await auth_service(request).limiter.check(
        "ticket-create" if create else "ticket-reply",
        str(user.id),
        5 if create else 20,
        600,
    )


@router.get("/tickets")
async def my_tickets(
    request: Request,
    user: User,
    status: TicketStatus | None = None,
    q: Search = "",
    offset: Offset = 0,
    limit: Limit = 20,
):
    return await required(request, "tickets").listing(user.id, status, q, offset, limit)


@router.post("/tickets", dependencies=guard)
async def create_ticket(data: TicketInput, request: Request, user: User):
    await ticket_write(request, user, create=True)
    return await required(request, "tickets").create(data, user.id)


@router.get("/tickets/{identity}")
async def my_ticket(identity: UUID, request: Request, user: User):
    return await required(request, "tickets").get(identity, user.id)


@router.post("/tickets/{identity}/replies", dependencies=guard)
async def my_reply(identity: UUID, data: ReplyInput, request: Request, user: User):
    await ticket_write(request, user)
    return await required(request, "tickets").reply(identity, data, user.id)


@router.patch("/tickets/{identity}", dependencies=guard)
async def my_ticket_state(identity: UUID, data: TicketState, request: Request, user: User):
    return await required(request, "tickets").state(identity, data, user.id)


@router.get("/admin/tickets")
async def tickets(
    request: Request,
    actor: Admin,
    status: TicketStatus | None = None,
    q: Search = "",
    offset: Offset = 0,
    limit: Limit = 20,
):
    return await required(request, "tickets").listing(None, status, q, offset, limit)


@router.get("/admin/tickets/{identity}")
async def ticket(identity: UUID, request: Request, actor: Admin):
    return await required(request, "tickets").get(identity)


@router.post("/admin/tickets/{identity}/replies", dependencies=guard)
async def reply(identity: UUID, data: ReplyInput, request: Request, actor: Admin):
    await auth_service(request).limiter.check("ticket-reply", str(actor.id), 60, 600)
    return await required(request, "tickets").reply(identity, data, actor.id, staff=True)


@router.patch("/admin/tickets/{identity}", dependencies=guard)
async def ticket_state(identity: UUID, data: TicketState, request: Request, actor: Admin):
    return await required(request, "tickets").state(identity, data, actor.id, staff=True)
