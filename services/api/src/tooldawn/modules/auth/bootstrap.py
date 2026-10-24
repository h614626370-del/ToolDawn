import asyncio
import json
import logging
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, text

from tooldawn.modules.auth.models import UserRecord
from tooldawn.modules.auth.passwords import hash_password
from tooldawn.modules.operations.models import SettingRecord


async def bootstrap_admin(sessions, settings):
    if not settings.bootstrap_admin or settings.environment == "test":
        return
    async with sessions.begin() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(72649102)"))
        if await db.get(SettingRecord, "admin_bootstrap"):
            return
        exists = await db.scalar(select(UserRecord.id).where(UserRecord.is_superadmin))
        if not exists:
            path = Path(settings.bootstrap_credentials).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                # Recover the same credentials if a previous database commit failed.
                credentials = json.loads(path.read_text(encoding="utf-8"))
                email, password = credentials["email"], credentials["password"]
                if (
                    not isinstance(email, str)
                    or not isinstance(password, str)
                    or len(password) < 24
                ):
                    raise RuntimeError("Invalid bootstrap credentials file")
            else:
                email = f"admin-{secrets.token_hex(4)}@tooldawn.com"
                password = secrets.token_urlsafe(24)
                with os.fdopen(
                    os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
                ) as f:
                    json.dump({"email": email, "password": password}, f)
            encoded = await asyncio.to_thread(hash_password, password)
            db.add(
                UserRecord(
                    id=uuid4(),
                    email=email,
                    role="admin",
                    disabled=False,
                    display_name="ToolDawn Admin",
                    password_hash=encoded,
                    is_superadmin=True,
                    must_change_password=True,
                    created_at=datetime.now(UTC),
                )
            )
            logging.getLogger("tooldawn.setup").warning(
                "Initial administrator credentials saved privately to %s", path
            )
        db.add(
            SettingRecord(
                key="admin_bootstrap",
                value={"initialized": True},
                revision=1,
                updated_at=datetime.now(UTC),
            )
        )
