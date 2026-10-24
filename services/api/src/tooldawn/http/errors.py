from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "code": code,
            "message": message,
            "request_id": request.state.request_id,
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        codes = {
            400: "invalid_request",
            401: "unauthenticated",
            403: "forbidden",
            404: "not_found",
            429: "rate_limited",
            503: "service_unavailable",
        }
        return error_response(
            request, exc.status_code, codes.get(exc.status_code, "request_failed"), str(exc.detail)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(request, 422, "invalid_parameters", "请求参数不正确，请检查后重试。")

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        return error_response(request, 503, "service_unavailable", "服务暂时不可用，请稍后重试。")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return error_response(request, 500, "internal_error", "服务暂时不可用，请稍后重试。")
