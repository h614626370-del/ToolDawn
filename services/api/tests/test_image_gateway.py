import asyncio
import base64
import io
import struct
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException
from PIL import Image, PngImagePlugin

from tooldawn.config import Settings
from tooldawn.modules.ai_tools.gateway import ModelFailure
from tooldawn.modules.image_tools.gateway import decode_image, generate_image, require_transparency
from tooldawn.modules.image_tools.uploads import MAX_UPLOAD, normalize_reference

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII="
)


def reference_png():
    image = Image.new("RGBA", (16, 16), (30, 150, 90, 255))
    image.putpixel((0, 0), (0, 0, 0, 0))
    out = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private", "private reference metadata")
    image.save(out, "PNG", pnginfo=metadata)
    return out.getvalue()


def test_reference_validation_metadata_and_transparency():
    encoded, width, height = normalize_reference(reference_png())
    clean = base64.b64decode(encoded)
    assert (width, height) == (16, 16)
    assert b"private reference metadata" not in clean
    require_transparency(clean)
    out = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(out, "PNG")
    with pytest.raises(ModelFailure, match="transparency_missing"):
        require_transparency(out.getvalue())
    for value, status in [(b"<svg/>", 422), (b"x" * (MAX_UPLOAD + 1), 413)]:
        with pytest.raises(HTTPException) as failure:
            normalize_reference(value)
        assert failure.value.status_code == status


def test_image_edit_multipart_contract():
    image = reference_png()
    settings = Settings(
        _env_file=None,
        llm_base_url="https://images.example/v1",
        llm_api_key="test-key",
        llm_model="edit-model",
    )

    def handler(request):
        assert str(request.url) == "https://images.example/v1/images/edits"
        assert request.headers["content-type"].startswith("multipart/form-data;")
        content = request.read()
        assert b'name="image"; filename="reference.png"' in content
        assert image in content
        for field, value in [
            ("model", "edit-model"),
            ("quality", "high"),
            ("background", "transparent"),
        ]:
            assert f'name="{field}"\r\n\r\n{value}'.encode() in content
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(image).decode()}]})

    async def run():
        client_type = httpx.AsyncClient
        with patch(
            "tooldawn.modules.image_tools.gateway.httpx.AsyncClient",
            side_effect=lambda **kw: client_type(transport=httpx.MockTransport(handler), **kw),
        ):
            return await generate_image(
                settings,
                {
                    "mode": "edit",
                    "prompt": "Change color",
                    "size": "1024x1024",
                    "quality": "high",
                    "background": "transparent",
                    "reference_base64": base64.b64encode(image).decode(),
                },
            )

    assert asyncio.run(run()) == image


@pytest.mark.parametrize(
    "value",
    [
        None,
        "not base64",
        base64.b64encode(b"<svg/>").decode(),
        base64.b64encode(PNG[:16] + struct.pack(">II", 9000, 9000) + PNG[24:]).decode(),
    ],
)
def test_image_rejects_invalid_or_oversized_content(value):
    with pytest.raises(ModelFailure):
        decode_image(value)


def test_image_gateway_contract_and_no_arbitrary_url_fetch():
    settings = Settings(
        _env_file=None,
        llm_base_url="https://images.example/v1",
        llm_api_key="test-private-key",
        llm_model="image-model",
    )
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://images.example/v1/images/generations"
        assert request.headers["Authorization"] == "Bearer test-private-key"
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(PNG).decode()}]})

    client_type = httpx.AsyncClient

    async def run(handler):
        with patch(
            "tooldawn.modules.image_tools.gateway.httpx.AsyncClient",
            side_effect=lambda **kw: client_type(transport=httpx.MockTransport(handler), **kw),
        ):
            return await generate_image(settings, {"prompt": "A cat", "size": "1024x1024"})

    assert asyncio.run(run(handler)) == PNG
    assert len(calls) == 1
    with pytest.raises(ModelFailure):
        asyncio.run(
            run(lambda _: httpx.Response(200, json={"data": [{"url": "http://127.0.0.1/private"}]}))
        )
    with pytest.raises(ModelFailure) as failure:
        asyncio.run(run(lambda _: httpx.Response(429, text="private upstream body")))
    assert failure.value.retryable
    assert str(failure.value) == "rate_limited"
