import asyncio
import base64
import binascii
import io
import json
import struct

import httpx
from PIL import Image

from tooldawn.modules.ai_tools.gateway import ModelFailure

MAX_IMAGE = 15 * 1024 * 1024


def decode_image(value):
    if not isinstance(value, str) or len(value) > MAX_IMAGE * 4 // 3 + 4:
        raise ModelFailure()
    try:
        image = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise ModelFailure() from None
    # Request PNG explicitly. Do not serve HTML/SVG or fetch arbitrary upstream URLs.
    if len(image) < 33 or len(image) > MAX_IMAGE or image[:8] != b"\x89PNG\r\n\x1a\n":
        raise ModelFailure()
    if image[12:16] != b"IHDR":
        raise ModelFailure()
    width, height = struct.unpack(">II", image[16:24])
    if not (1 <= width <= 4096 and 1 <= height <= 4096) or width * height > 10_000_000:
        raise ModelFailure()
    return image


async def generate_image(settings, payload):
    try:
        parameters = {
            "model": settings.llm_model,
            "prompt": payload["prompt"],
            "size": payload["size"],
            "n": 1,
            "quality": payload.get("quality", "low"),
            "output_format": "png",
        }
        if payload.get("background") == "transparent":
            parameters["background"] = "transparent"
        edit = payload.get("mode") == "edit"
        if edit:
            options = {
                "data": {k: str(v) for k, v in parameters.items()},
                "files": {
                    "image": (
                        "reference.png",
                        base64.b64decode(payload["reference_base64"], validate=True),
                        "image/png",
                    )
                },
            }
        else:
            options = {"json": parameters}
        async with (
            asyncio.timeout(180),
            httpx.AsyncClient(
                timeout=httpx.Timeout(175, connect=10), trust_env=False, follow_redirects=False
            ) as client,
        ):
            async with client.stream(
                "POST",
                settings.llm_base_url.rstrip("/")
                + ("/images/edits" if edit else "/images/generations"),
                headers={"Authorization": "Bearer " + settings.llm_api_key.get_secret_value()},
                **options,
            ) as response:
                if response.status_code != 200:
                    raise ModelFailure.from_status(
                        response.status_code, response.headers.get("retry-after")
                    )
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_IMAGE * 4 // 3 + 65536:
                        raise ModelFailure()
            data = json.loads(body)
            image = decode_image(data["data"][0]["b64_json"])
            if payload.get("background") == "transparent":
                await asyncio.to_thread(require_transparency, image)
            return image
    except ModelFailure:
        raise
    except (httpx.HTTPError, TimeoutError):
        raise ModelFailure("network_error", retryable=True) from None
    except (ValueError, KeyError, IndexError, TypeError):
        raise ModelFailure() from None


def require_transparency(content):
    try:
        with Image.open(io.BytesIO(content)) as image:
            alpha = image.convert("RGBA").getchannel("A")
            low, high = alpha.getextrema()
            if low == 255 or high == 0:
                raise ModelFailure("transparency_missing")
    except (OSError, ValueError):
        raise ModelFailure() from None
