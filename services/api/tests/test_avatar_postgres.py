# ruff: noqa: F811
import io
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from PIL import Image, PngImagePlugin
from sqlalchemy import delete
from test_operations_postgres import ORIGIN, ops, sign_in  # noqa: F401

from tooldawn.modules.ai_tools.models import TextRunRecord
from tooldawn.modules.auth.models import UserRecord

pytestmark = pytest.mark.skipif(
    not os.environ.get("TOOLDAWN_TEST_DATABASE_URL"), reason="Requires migrated test PostgreSQL"
)


def picture(color="red"):
    output = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private", "must be removed")
    Image.new("RGB", (400, 300), color).save(output, "PNG", pnginfo=metadata)
    return output.getvalue()


def test_avatar_lifecycle_and_owner_isolation(ops):
    client, app, prefix, _ = ops
    for method in (client.get, client.put, client.delete):
        assert method("/api/v1/me/avatar", headers=ORIGIN).status_code == 401
    sign_in(client, prefix, "user")
    assert client.put("/api/v1/me/avatar", content=picture()).status_code == 403
    uploaded = client.put("/api/v1/me/avatar", headers=ORIGIN, content=picture())
    assert uploaded.status_code == 200, uploaded.text
    avatar_url = uploaded.json()["avatar_url"]
    result = client.get(avatar_url)
    assert result.status_code == 200
    assert {"private", "no-store"} <= set(result.headers["cache-control"].split(", "))
    assert result.headers["x-content-type-options"] == "nosniff"
    with Image.open(io.BytesIO(result.content)) as image:
        assert image.size == (256, 256)
        assert image.format == "WEBP"
        assert "private" not in image.info
    replaced = client.put("/api/v1/me/avatar", headers=ORIGIN, content=picture("blue"))
    assert replaced.json()["avatar_url"] != avatar_url
    for role in ("other", "admin"):
        sign_in(client, prefix, role)
        assert client.get(avatar_url).status_code == 404
    other = sign_in(client, prefix, "other")

    async def make_regular_admin():
        async with app.state.control.sessions.begin() as db:
            row = await db.get(UserRecord, UUID(other["id"]))
            row.role = "admin"
            row.is_superadmin = False

    client.portal.call(make_regular_admin)
    assert client.get(avatar_url).status_code == 404
    sign_in(client, prefix, "user")
    assert client.delete("/api/v1/me/avatar", headers=ORIGIN).json()["avatar_url"] is None
    assert client.get(avatar_url).status_code == 404


def test_avatar_rejects_invalid_and_disabled_accounts(ops):
    client, app, prefix, _ = ops
    user = sign_in(client, prefix, "user")
    for content in (b"<svg></svg>", b"not an image"):
        assert client.put("/api/v1/me/avatar", headers=ORIGIN, content=content).status_code == 422
    assert (
        client.put(
            "/api/v1/me/avatar", headers=ORIGIN, content=b"x" * (4 * 1024 * 1024 + 1)
        ).status_code
        == 413
    )
    animated = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(
        animated, "PNG", save_all=True, append_images=[Image.new("RGB", (20, 20), "blue")]
    )
    assert (
        client.put("/api/v1/me/avatar", headers=ORIGIN, content=animated.getvalue()).status_code
        == 422
    )

    async def disable():
        async with app.state.control.sessions.begin() as db:
            row = await db.get(UserRecord, UUID(user["id"]))
            row.disabled = True

    client.portal.call(disable)
    assert client.put("/api/v1/me/avatar", headers=ORIGIN, content=picture()).status_code in (
        401,
        403,
    )


def test_usage_previews_are_only_returned_to_owner(ops):
    client, app, prefix, _ = ops
    user = sign_in(client, prefix, "user")
    owner = UUID(user["id"])
    identity = uuid4()

    async def insert():
        async with app.state.control.sessions.begin() as db:
            db.add(
                TextRunRecord(
                    id=identity,
                    user_id=owner,
                    request_key=uuid4(),
                    fingerprint="a" * 64,
                    tool_slug="birthday-message",
                    status="succeeded",
                    output="private result",
                    cost=1,
                    language="zh",
                    created_at=datetime.now(UTC),
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                )
            )

    async def cleanup():
        async with app.state.control.sessions.begin() as db:
            await db.execute(delete(TextRunRecord).where(TextRunRecord.id == identity))

    client.portal.call(insert)
    try:
        own = client.get("/api/v1/me/usage").json()["items"]
        assert own[0]["result_preview"] == "private result"
        assert own[0]["has_output"]
        sign_in(client, prefix, "other")
        assert str(identity) not in client.get("/api/v1/me/usage").text
        sign_in(client, prefix, "admin")
        rows = client.get("/api/v1/admin/usage").json()["items"]
        assert all("result_preview" not in row and "image_url" not in row for row in rows)
    finally:
        client.portal.call(cleanup)
