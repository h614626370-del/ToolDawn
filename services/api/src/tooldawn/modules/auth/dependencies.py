from ipaddress import ip_address

from fastapi import HTTPException, Request

from tooldawn.modules.auth.schemas import UserResponse
from tooldawn.modules.auth.security import token_digest
from tooldawn.modules.auth.service import AuthService

COOKIE_NAME = "tooldawn_session"


def auth_service(request: Request) -> AuthService:
    service = request.app.state.auth
    if service is None:
        raise HTTPException(503, "服务暂时不可用，请稍后重试。")
    return service


def check_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.public_origins:
        raise HTTPException(403, "请求来源不受信任，请返回本站重试。")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "请求来源不受信任，请返回本站重试。")


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if peer in {"127.0.0.1", "::1"}:
        forwarded = request.headers.get("x-forwarded-for", "")
        try:
            return str(ip_address(forwarded))
        except ValueError:
            pass
    return peer


async def require_user(request: Request) -> UserResponse:
    service = auth_service(request)
    token = request.cookies.get(COOKIE_NAME, "")
    if not token or len(token) > 200:
        raise HTTPException(401, "请先登录。")
    user = await service.repository.current_user(token_digest(token))
    if user is None:
        raise HTTPException(401, "登录已过期，请重新登录。")
    return UserResponse.model_validate(user)


async def require_admin(request: Request) -> UserResponse:
    user = await require_user(request)
    if user.role != "admin":
        raise HTTPException(403, "需要管理员权限。")
    if user.must_change_password:
        raise HTTPException(403, "请先修改初始密码。")
    return user


async def require_superadmin(request: Request) -> UserResponse:
    user = await require_admin(request)
    if not user.is_superadmin:
        raise HTTPException(403, "需要超级管理员权限。")
    return user
