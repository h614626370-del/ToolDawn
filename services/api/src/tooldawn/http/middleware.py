import logging
from time import perf_counter
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("tooldawn.http")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        started = perf_counter()
        status = 500
        metrics = getattr(scope.get("app").state, "metrics", None) if scope.get("app") else None
        if metrics:
            metrics.inflight += 1

        async def send_with_context(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
                if (
                    scope["path"].startswith(
                        (
                            "/api/v1/auth/",
                            "/api/v1/admin/",
                            "/api/v1/billing/",
                            "/api/v1/ai-tools/",
                            "/api/v1/me/",
                            "/api/v1/tickets",
                        )
                    )
                    or scope["path"] == "/api/v1/me"
                ):
                    message["headers"].append((b"cache-control", b"no-store"))
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        finally:
            if metrics:
                metrics.inflight -= 1
                metrics.record(status, (perf_counter() - started) * 1000)
            # Do not log query strings, bodies, credentials, or client-supplied request IDs.
            route = scope.get("route")
            logger.info(
                "request_id=%s method=%s route=%s status=%s duration_ms=%.1f",
                request_id,
                scope["method"],
                getattr(route, "path", "unmatched"),
                status,
                (perf_counter() - started) * 1000,
            )
