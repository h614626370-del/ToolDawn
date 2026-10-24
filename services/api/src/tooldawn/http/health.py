from fastapi import APIRouter, HTTPException, Request
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, str]:
    if request.app.state.engine is not None:
        try:
            async with request.app.state.engine.connect() as connection:
                await connection.execute(text("SELECT slug FROM tools LIMIT 1"))
        except SQLAlchemyError:
            raise HTTPException(503, "数据库连接或迁移尚未就绪。") from None
    if request.app.state.redis is not None:
        try:
            await request.app.state.redis.ping()
        except RedisError:
            raise HTTPException(503, "Redis 连接尚未就绪。") from None
    return {
        "status": "ok",
        "catalog_backend": request.app.state.settings.catalog_backend,
        "redis": "ok" if request.app.state.redis is not None else "unconfigured",
    }
