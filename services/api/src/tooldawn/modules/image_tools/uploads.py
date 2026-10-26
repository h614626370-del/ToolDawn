import base64
import io
import warnings

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD = 8 * 1024 * 1024


def normalize_reference(content: bytes):
    if not content or len(content) > MAX_UPLOAD:
        raise HTTPException(413, "请选择 8 MB 以内的图片。")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if (
                    image.format not in {"PNG", "JPEG", "WEBP"}
                    or getattr(image, "n_frames", 1) != 1
                ):
                    raise ValueError()
                if image.width * image.height > 20_000_000:
                    raise ValueError()
                image.load()
                normalized = ImageOps.exif_transpose(image).convert("RGBA")
                normalized.thumbnail((2048, 2048))
                # Rebuild pixels to strip EXIF, metadata and other embedded payloads.
                clean = Image.frombytes("RGBA", normalized.size, normalized.tobytes())
                out = io.BytesIO()
                clean.save(out, "PNG")
                if out.tell() > MAX_UPLOAD:
                    raise ValueError()
                return base64.b64encode(out.getvalue()).decode(), clean.width, clean.height
    except (
        ValueError,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(422, "图片无法读取，请使用静态 PNG、JPG 或 WebP 图片。") from None
