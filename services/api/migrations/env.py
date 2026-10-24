import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from tooldawn.config import Settings
from tooldawn.infra.database import Base
from tooldawn.modules.admin import models as admin_models  # noqa: F401
from tooldawn.modules.ai_tools import models as ai_models  # noqa: F401
from tooldawn.modules.auth import models as auth_models  # noqa: F401
from tooldawn.modules.billing import models as billing_models  # noqa: F401
from tooldawn.modules.catalog import models  # noqa: F401
from tooldawn.modules.operations import models as operations_models  # noqa: F401

url = Settings().database_url
if not url:
    raise RuntimeError("Set TOOLDAWN_DATABASE_URL before running migrations")


def run_sync(connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_sync)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_online())
