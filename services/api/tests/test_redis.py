import asyncio
import os
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError

from tooldawn.config import Settings
from tooldawn.infra.redis import create_redis
from tooldawn.main import create_app
from tooldawn.modules.auth.limiter import AuthLimiter
from tooldawn.modules.auth.security import token_digest


@pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_REDIS_URL"), reason="Requires test Redis connection"
)
def test_idle_connection_health_check_recovers_before_rate_limit_write():
    async def run():
        cache = create_redis(os.environ["TOOLDAWN_TEST_REDIS_URL"])
        key = f"tooldawn:auth:reconnect:{token_digest(uuid4().hex)}"
        connection = None
        try:
            connection = await cache.connection_pool.get_connection()
            connection.next_health_check = -1
            original = type(connection)._send_ping
            attempts = 0

            async def disconnected_once(self):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise ConnectionError("simulated stale idle socket")
                return await original(self)

            await cache.connection_pool.release(connection)
            connection = None
            with patch("redis.asyncio.connection.AbstractConnection._send_ping", disconnected_once):
                from tooldawn.modules.auth.limiter import WINDOW_SCRIPT

                assert await cache.eval(WINDOW_SCRIPT, 1, key, 60) == 1
            assert attempts == 2
            assert await cache.get(key) == "1"
        finally:
            if connection is not None:
                await cache.connection_pool.release(connection)
            await cache.delete(key)
            await cache.aclose()

    asyncio.run(run())


def test_redis_outage_blocks_readiness_without_leaking_credentials():
    settings = Settings(_env_file=None, environment="test", catalog_backend="seed", redis_url=None)
    with TestClient(create_app(settings)) as client:
        cache = AsyncMock()
        cache.ping.side_effect = ConnectionError("private connection details")
        client.app.state.redis = cache
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert "private connection details" not in response.text
        assert client.get("/api/v1/health/live").status_code == 200


@pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_REDIS_URL"), reason="Requires remote test Redis connection"
)
def test_remote_redis_namespaced_roundtrip():
    async def roundtrip():
        cache = create_redis(os.environ["TOOLDAWN_TEST_REDIS_URL"])
        key = f"tooldawn:test:{uuid4().hex}"
        try:
            assert await cache.ping()
            assert await cache.set(key, "connected", ex=30)
            assert await cache.get(key) == "connected"
        finally:
            await cache.delete(key)
            await cache.aclose()

    asyncio.run(roundtrip())


@pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_REDIS_URL"), reason="Requires test Redis connection"
)
def test_auth_atomic_rate_limit_cooldown_and_ttl_repair():
    async def run():
        cache = create_redis(os.environ["TOOLDAWN_TEST_REDIS_URL"])
        identity = f"test-{uuid4().hex}"
        window_key = f"tooldawn:auth:test:{token_digest(identity)}"
        cooldown_key = f"tooldawn:auth:cooldown:{token_digest(identity)}"
        limiter = AuthLimiter(cache)
        try:
            # Simulate a counter left without an expiry by an interrupted older implementation.
            await cache.set(window_key, "0")
            results = await asyncio.gather(
                *(limiter.check("test", identity, 3, 60) for _ in range(10)), return_exceptions=True
            )
            assert sum(result is None for result in results) == 3
            assert (
                sum(
                    isinstance(result, HTTPException) and result.status_code == 429
                    for result in results
                )
                == 7
            )
            assert 0 < await cache.ttl(window_key) <= 60
            await limiter.cooldown(identity)
            with pytest.raises(HTTPException) as error:
                await limiter.cooldown(identity)
            assert error.value.status_code == 429
            assert 0 < await cache.ttl(cooldown_key) <= 60
        finally:
            await cache.delete(window_key, cooldown_key)
            await cache.aclose()

    asyncio.run(run())
