import logging

from fastapi import HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError

from tooldawn.modules.auth.security import token_digest

logger = logging.getLogger("tooldawn.auth")

WINDOW_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if redis.call('TTL', KEYS[1]) < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class AuthLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def check(self, action: str, identity: str, limit: int, window: int) -> None:
        key = f"tooldawn:auth:{action}:{token_digest(identity)}"
        try:
            count = await self.redis.eval(WINDOW_SCRIPT, 1, key, window)
        except RedisError as error:
            logger.warning(
                "Redis limiter unavailable action=%s error_type=%s", action, type(error).__name__
            )
            raise HTTPException(503, "登录服务暂时不可用，请稍后重试。") from None
        if count > limit:
            raise HTTPException(429, "操作过于频繁，请稍后重试。")

    async def cooldown(self, email: str) -> None:
        key = f"tooldawn:auth:cooldown:{token_digest(email)}"
        try:
            accepted = await self.redis.set(key, "1", ex=60, nx=True)
        except RedisError as error:
            logger.warning("Redis cooldown unavailable error_type=%s", type(error).__name__)
            raise HTTPException(503, "登录服务暂时不可用，请稍后重试。") from None
        if not accepted:
            raise HTTPException(429, "验证码已发送，请等待 60 秒后再试。")
