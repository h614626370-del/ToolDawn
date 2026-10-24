from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError, TimeoutError


def create_redis(url: str) -> Redis:
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        max_connections=20,
        # Check idle pooled sockets before using them, including across WSL wakeups.
        health_check_interval=30,
        retry=Retry(ExponentialBackoff(base=0.05, cap=0.2), 1),
        retry_on_error=[ConnectionError, TimeoutError],
    )
