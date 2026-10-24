from redis.asyncio import Redis


def create_redis(url: str) -> Redis:
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        max_connections=20,
    )
