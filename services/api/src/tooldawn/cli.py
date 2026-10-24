import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from tooldawn.config import Settings
from tooldawn.infra.database import create_database
from tooldawn.modules.ai_tools.registry import TOOLS
from tooldawn.modules.auth.repository import AuthRepository
from tooldawn.modules.auth.schemas import EmailRequest
from tooldawn.modules.catalog.models import CategoryRecord, ToolRecord
from tooldawn.modules.catalog.seed import load_seed


async def seed_catalog(settings: Settings) -> None:
    if not settings.database_url:
        raise ValueError("Set TOOLDAWN_DATABASE_URL before seeding")
    engine, sessions = create_database(settings.database_url)
    categories, tools = load_seed()
    try:
        async with sessions.begin() as session:
            for index, category in enumerate(categories):
                await session.execute(
                    insert(CategoryRecord)
                    .values(**category.model_dump(), sort_order=index)
                    .on_conflict_do_nothing(index_elements=["slug"])
                )
            for tool in tools:
                data = tool.model_dump()
                if data["external_url"] is not None:
                    data["external_url"] = str(data["external_url"])
                await session.execute(
                    insert(ToolRecord)
                    .values(**data)
                    .on_conflict_do_nothing(index_elements=["slug"])
                )
    finally:
        await engine.dispose()
    print("Catalog seed inserted; existing records were preserved.")


async def manage_auth(settings: Settings, command: str, email: str | None) -> None:
    if not settings.database_url:
        raise ValueError("Set TOOLDAWN_DATABASE_URL first")
    engine, sessions = create_database(settings.database_url)
    repository = AuthRepository(sessions)
    try:
        if command == "create-admin":
            if not email:
                raise ValueError("--email is required")
            normalized = str(EmailRequest(email=email).email)
            await repository.create_admin(normalized)
            print("Administrator role granted. Sign in with an email verification code.")
        else:
            await repository.cleanup()
            print("Expired email challenges and sessions removed.")
    finally:
        await engine.dispose()


async def install_text_tools(settings: Settings) -> None:
    await seed_catalog(settings)
    engine, sessions = create_database(settings.database_url)
    _, tools = load_seed()
    try:
        async with sessions.begin() as db:
            for spec in tools:
                if spec.slug not in TOOLS:
                    continue
                row = await db.scalar(
                    select(ToolRecord).where(ToolRecord.slug == spec.slug).with_for_update()
                )
                # Promote untouched placeholders, preserving administrator edits.
                if (
                    row.kind == "internal"
                    and row.published
                    and row.status == "coming_soon"
                    and "此工具正在开发，当前不发送模型请求。" in row.description
                    and row.revision == 1
                ):
                    for field in ("description", "features", "keywords", "status", "updated_at"):
                        setattr(row, field, getattr(spec, field))
                    row.revision += 1
    finally:
        await engine.dispose()
    print("Text tools installed; customized catalog records were preserved.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ToolDawn maintenance commands")
    parser.add_argument(
        "command", choices=["seed-catalog", "create-admin", "cleanup-auth", "install-text-tools"]
    )
    parser.add_argument("--email")
    args = parser.parse_args()
    if args.command == "create-admin" and not args.email:
        parser.error("create-admin requires --email")
    settings = Settings()
    if args.command == "seed-catalog":
        asyncio.run(seed_catalog(settings))
    elif args.command == "install-text-tools":
        asyncio.run(install_text_tools(settings))
    else:
        asyncio.run(manage_auth(settings, args.command, args.email))


if __name__ == "__main__":
    main()
