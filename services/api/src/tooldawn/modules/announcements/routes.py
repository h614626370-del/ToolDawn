from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from tooldawn.modules.announcements.repository import AnnouncementRepository
from tooldawn.modules.announcements.schemas import (
    AdminAnnouncementPage,
    AnnouncementInput,
    AnnouncementPage,
    AnnouncementView,
    ReadInput,
    Status,
)
from tooldawn.modules.auth.dependencies import (
    COOKIE_NAME,
    check_origin,
    require_admin,
    require_user,
)
from tooldawn.modules.auth.schemas import UserResponse
from tooldawn.modules.auth.security import token_digest

router = APIRouter(tags=["announcements"])
Admin = Annotated[UserResponse, Depends(require_admin)]
User = Annotated[UserResponse, Depends(require_user)]
Offset = Annotated[int, Query(ge=0, le=100000)]
Limit = Annotated[int, Query(ge=1, le=100)]


def repository(request: Request) -> AnnouncementRepository:
    repo = request.app.state.announcements
    if repo is None:
        raise HTTPException(503, "服务暂时不可用，请稍后重试。")
    return repo


Repo = Annotated[AnnouncementRepository, Depends(repository)]


async def optional_user(request: Request):
    token = request.cookies.get(COOKIE_NAME, "")
    service = request.app.state.auth
    if token and len(token) <= 200 and service:
        user = await service.repository.current_user(token_digest(token))
        return user.id if user else None
    return None


@router.get("/announcements", response_model=AnnouncementPage)
async def listing(request: Request, response: Response, offset: Offset = 0, limit: Limit = 20):
    response.headers["Cache-Control"] = "private, no-store"
    repo = request.app.state.announcements
    if repo is None:
        return {"items": [], "total": 0, "unread_count": 0, "popups": []}
    return await repo.listing(await optional_user(request), offset, limit)


@router.post("/announcements/read", status_code=204, dependencies=[Depends(check_origin)])
async def read(data: ReadInput, user: User, repo: Repo):
    await repo.mark_read(data, user.id)


@router.get("/admin/announcements", response_model=AdminAnnouncementPage)
async def admin_list(
    actor: Admin,
    repo: Repo,
    response: Response,
    status: Status | None = None,
    q: Annotated[str, Query(max_length=100)] = "",
    offset: Offset = 0,
    limit: Limit = 20,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await repo.admin_listing(status, q, offset, limit)


@router.post(
    "/admin/announcements",
    response_model=AnnouncementView,
    status_code=201,
    dependencies=[Depends(check_origin)],
)
async def create(data: AnnouncementInput, actor: Admin, repo: Repo):
    return await repo.save(None, data, actor.id)


@router.put(
    "/admin/announcements/{identity}",
    response_model=AnnouncementView,
    dependencies=[Depends(check_origin)],
)
async def update(identity: UUID, data: AnnouncementInput, actor: Admin, repo: Repo):
    return await repo.save(identity, data, actor.id)
