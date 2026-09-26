"""Android WebP bridge for jmcomic's Pillow image pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def is_webp(content: bytes) -> bool:
    return (
        len(content) >= 12
        and content[:4] == b"RIFF"
        and content[8:12] == b"WEBP"
    )


def android_webp_to_png(content: bytes) -> bytes:
    from android.graphics import Bitmap, BitmapFactory
    from java import jarray, jbyte
    from java.io import ByteArrayOutputStream

    signed_bytes = jarray(jbyte)([
        value if value < 128 else value - 256
        for value in content
    ])
    bitmap = BitmapFactory.decodeByteArray(
        signed_bytes,
        0,
        len(signed_bytes),
    )
    if bitmap is None:
        raise ValueError("Android BitmapFactory returned null.")

    output = ByteArrayOutputStream()
    try:
        if not bitmap.compress(Bitmap.CompressFormat.PNG, 100, output):
            raise ValueError("Bitmap PNG compression failed.")
        return bytes(output.toByteArray())
    finally:
        bitmap.recycle()


def install_webp_support(jm_image_tool: Any) -> bool:
    """Patch jmcomic's image opener before any download thread starts."""

    if getattr(jm_image_tool, "_android_webp_patched", False):
        return True

    original_open = jm_image_tool.open_image

    def open_image(cls: Any, fp: Any):
        if isinstance(fp, (bytes, bytearray, memoryview)):
            payload = bytes(fp)
            if is_webp(payload):
                payload = android_webp_to_png(payload)
            return original_open(payload)

        if isinstance(fp, (str, os.PathLike)):
            path = Path(fp)
            try:
                payload = path.read_bytes()
            except OSError:
                return original_open(fp)
            if is_webp(payload):
                return original_open(android_webp_to_png(payload))

        return original_open(fp)

    jm_image_tool.open_image = classmethod(open_image)
    jm_image_tool._android_webp_patched = True
    return True
