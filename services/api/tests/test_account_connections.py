import asyncio
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from tooldawn.modules.operations.accounts import AccountRepository
from tooldawn.modules.operations.schemas import AccountInput


@pytest.mark.parametrize(
    "case", ["valid", "empty", "unauthorized", "invalid", "oversized", "timeout"]
)
def test_discover_models_bounded_and_sanitized(case):
    async def scenario():
        def respond(request):
            assert str(request.url) == "https://example.com/v1/models"
            assert request.headers["authorization"] == "Bearer test-key"
            if case == "unauthorized":
                return httpx.Response(401, text="private upstream test-key")
            if case == "invalid":
                return httpx.Response(200, json={"data": {"private": "test-key"}})
            if case == "oversized":
                return httpx.Response(200, content=b"x" * 524289)
            if case == "timeout":
                raise httpx.ReadTimeout("private test-key")
            return httpx.Response(
                200,
                json={
                    "data": []
                    if case == "empty"
                    else [
                        {"id": "text-model"},
                        {"id": "image-model"},
                        {"id": "text-model"},
                        {"id": 42},
                        None,
                        {"id": "bad\nmodel"},
                        {"id": "x" * 121},
                    ]
                },
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        with patch("tooldawn.modules.operations.accounts.httpx.AsyncClient", return_value=client):
            if case in ("valid", "empty"):
                assert await AccountRepository.fetch_models(
                    "https://example.com/v1", "test-key"
                ) == ([] if case == "empty" else ["image-model", "text-model"])
            else:
                with pytest.raises(HTTPException) as exc:
                    await AccountRepository.fetch_models("https://example.com/v1", "test-key")
                assert exc.value.status_code == 502
                assert "private" not in exc.value.detail and "test-key" not in exc.value.detail
        assert client.is_closed

    asyncio.run(scenario())


def test_capability_model_validation():
    base = dict(name="Example", base_url="https://example.com/v1", model="default")
    row = AccountInput(
        **base,
        capabilities=["text", "image_edit"],
        capability_models={"image_edit": " image-model "},
    )
    assert row.capability_models == {"image_edit": "image-model"}
    for changes in (
        {"capability_models": {"vision": "v"}},
        {"capability_models": {"text": " "}},
        {"model": " "},
        {"capability_models": {"unknown": "model"}},
    ):
        with pytest.raises(ValidationError):
            AccountInput(**{**base, **changes})
