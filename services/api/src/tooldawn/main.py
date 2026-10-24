from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI

from tooldawn.config import Settings
from tooldawn.http.errors import register_error_handlers
from tooldawn.http.health import router as health_router
from tooldawn.http.metrics import HttpMetrics
from tooldawn.http.middleware import RequestContextMiddleware
from tooldawn.infra.database import create_database
from tooldawn.infra.logging import configure_logging
from tooldawn.infra.redis import create_redis
from tooldawn.integrations.mail import MailSender
from tooldawn.modules.admin.repository import AdminRepository
from tooldawn.modules.admin.routes import router as admin_router
from tooldawn.modules.ai_tools.gateway import ModelGateway
from tooldawn.modules.ai_tools.repository import TextRunRepository
from tooldawn.modules.ai_tools.routes import router as ai_tools_router
from tooldawn.modules.auth.bootstrap import bootstrap_admin
from tooldawn.modules.auth.limiter import AuthLimiter
from tooldawn.modules.auth.profile import router as profile_router
from tooldawn.modules.auth.recovery import router as recovery_router
from tooldawn.modules.auth.repository import AuthRepository
from tooldawn.modules.auth.routes import router as auth_router
from tooldawn.modules.auth.service import AuthService
from tooldawn.modules.billing.gateway import StripeGateway
from tooldawn.modules.billing.provider_routes import router as provider_router
from tooldawn.modules.billing.repository import BillingRepository
from tooldawn.modules.billing.routes import router as billing_router
from tooldawn.modules.catalog.repository import PostgresCatalogRepository, SeedCatalogRepository
from tooldawn.modules.catalog.routes import router as catalog_router
from tooldawn.modules.operations.accounts import AccountRepository
from tooldawn.modules.operations.analytics import AnalyticsRepository
from tooldawn.modules.operations.routes import router as operations_router
from tooldawn.modules.operations.settings import SettingsRepository
from tooldawn.modules.operations.tickets import TicketRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.engine = None
        app.state.auth = None
        app.state.admin = None
        app.state.billing = None
        app.state.text_runs = None
        app.state.control = None
        app.state.accounts = None
        app.state.analytics = None
        app.state.tickets = None
        app.state.started_at = perf_counter()
        app.state.metrics = HttpMetrics()
        app.state.model_gateway = ModelGateway(settings)
        app.state.gateway = StripeGateway(settings)
        app.state.redis = create_redis(settings.redis_url) if settings.redis_url else None
        if settings.catalog_backend == "postgres":
            engine, sessions = create_database(settings.database_url)
            app.state.engine = engine
            app.state.catalog = PostgresCatalogRepository(sessions)
            app.state.admin = AdminRepository(sessions)
            app.state.billing = BillingRepository(sessions)
            app.state.text_runs = TextRunRepository(app.state.billing)
            app.state.control = SettingsRepository(sessions, settings)
            app.state.accounts = AccountRepository(app.state.control)
            app.state.analytics = AnalyticsRepository(sessions)
            app.state.tickets = TicketRepository(sessions)
            if settings.auth_secret and app.state.redis is not None:
                app.state.auth = AuthService(
                    AuthRepository(sessions),
                    AuthLimiter(app.state.redis),
                    MailSender(settings, app.state.control),
                    settings,
                )
                app.state.auth.control = app.state.control
                await bootstrap_admin(sessions, settings)
        else:
            app.state.catalog = SeedCatalogRepository()
        try:
            yield
        finally:
            await app.state.model_gateway.close()
            if app.state.redis is not None:
                await app.state.redis.aclose()
            if app.state.engine is not None:
                await app.state.engine.dispose()

    app = FastAPI(
        title="ToolDawn API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.environment != "production" else None,
    )
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(catalog_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(billing_router, prefix="/api/v1")
    app.include_router(provider_router, prefix="/api/v1")
    app.include_router(ai_tools_router, prefix="/api/v1")
    app.include_router(profile_router, prefix="/api/v1")
    app.include_router(recovery_router, prefix="/api/v1")
    app.include_router(operations_router, prefix="/api/v1")
    return app
