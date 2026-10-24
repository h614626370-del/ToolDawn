from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from tooldawn.modules.auth.dependencies import (
    COOKIE_NAME,
    auth_service,
    check_origin,
    client_ip,
    require_user,
)
from tooldawn.modules.auth.schemas import (
    ChallengeResponse,
    EmailRequest,
    UserResponse,
    VerifyRequest,
)
from tooldawn.modules.auth.security import token_digest

router = APIRouter(tags=["auth"])
write_guard = [Depends(check_origin)]


@router.post("/auth/email-code", response_model=ChallengeResponse, dependencies=write_guard)
async def email_code(data: EmailRequest, request: Request):
    return await auth_service(request).send_code(str(data.email), client_ip(request))


@router.post("/auth/verify", response_model=UserResponse, dependencies=write_guard)
async def verify(data: VerifyRequest, request: Request, response: Response):
    service = auth_service(request)
    user, token = await service.verify(data, client_ip(request))
    previous = request.cookies.get(COOKIE_NAME)
    if previous:
        await service.repository.revoke(token_digest(previous))
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=service.settings.session_days * 86400,
        httponly=True,
        secure=service.settings.environment == "production",
        samesite="lax",
        path="/api/v1",
    )
    return UserResponse.model_validate(user)


@router.post("/auth/logout", status_code=204, dependencies=write_guard)
async def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        await auth_service(request).repository.revoke(token_digest(token))
    response.delete_cookie(
        COOKIE_NAME,
        path="/api/v1",
        httponly=True,
        samesite="lax",
        secure=request.app.state.settings.environment == "production",
    )


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[UserResponse, Depends(require_user)]):
    return user
