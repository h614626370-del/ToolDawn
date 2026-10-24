from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from tooldawn.modules.admin.repository import AdminRepository
from tooldawn.modules.admin.schemas import (
    AdminCategory,
    AdminTool,
    AdminToolPage,
    AdminUser,
    AdminUserPage,
    CategoryInput,
    ToolInput,
    UserState,
)
from tooldawn.modules.auth.dependencies import check_origin, require_admin
from tooldawn.modules.auth.schemas import UserResponse

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)
Admin = Annotated[UserResponse, Depends(require_admin)]
Offset = Annotated[int, Query(ge=0, le=100000)]
Limit = Annotated[int, Query(ge=1, le=100)]


def repository(request: Request) -> AdminRepository:
    repo = request.app.state.admin
    if repo is None:
        raise HTTPException(503, "管理服务需要数据库连接。")
    return repo


Repo = Annotated[AdminRepository, Depends(repository)]


@router.get("/categories", response_model=list[AdminCategory])
async def categories(repo: Repo):
    return await repo.categories()


@router.post(
    "/categories",
    response_model=AdminCategory,
    status_code=201,
    dependencies=[Depends(check_origin)],
)
async def create_category(data: CategoryInput, repo: Repo, actor: Admin):
    return await repo.save_category(data, actor.id, create=True)


@router.put(
    "/categories/{slug}", response_model=AdminCategory, dependencies=[Depends(check_origin)]
)
async def update_category(slug: str, data: CategoryInput, repo: Repo, actor: Admin):
    if data.slug != slug:
        raise HTTPException(422, "分类标识不可修改。")
    return await repo.save_category(data, actor.id, create=False)


@router.get("/tools", response_model=AdminToolPage)
async def tools(
    repo: Repo,
    q: Annotated[str, Query(max_length=100)] = "",
    category: Annotated[str | None, Query(max_length=80)] = None,
    published: bool | None = None,
    offset: Offset = 0,
    limit: Limit = 20,
):
    return await repo.tools(q, category, published, offset, limit)


@router.post(
    "/tools", response_model=AdminTool, status_code=201, dependencies=[Depends(check_origin)]
)
async def create_tool(data: ToolInput, repo: Repo, actor: Admin):
    return await repo.save_tool(data, actor.id, create=True)


@router.put("/tools/{slug}", response_model=AdminTool, dependencies=[Depends(check_origin)])
async def update_tool(slug: str, data: ToolInput, repo: Repo, actor: Admin):
    if data.slug != slug:
        raise HTTPException(422, "工具标识不可修改。")
    return await repo.save_tool(data, actor.id, create=False)


@router.get("/users", response_model=AdminUserPage)
async def users(
    repo: Repo,
    q: Annotated[str, Query(max_length=100)] = "",
    offset: Offset = 0,
    limit: Limit = 20,
    role: Literal["admin", "user"] | None = None,
    disabled: bool | None = None,
):
    return await repo.users(q, offset, limit, role, disabled)


@router.patch("/users/{user_id}", response_model=AdminUser, dependencies=[Depends(check_origin)])
async def update_user(user_id: UUID, data: UserState, repo: Repo, actor: Admin):
    return await repo.set_user_state(user_id, data.disabled, actor.id)
