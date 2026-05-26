from __future__ import annotations

import asyncio
import os
from typing import Iterable

from google import genai
from google.genai import types

from backend import config

# Default to "Nano Banana 2" — Gemini's current fast image model (May 2026).
# Override via CNC_GEMINI_MODEL in .env if Google renames again, or to flip
# to "gemini-3-pro-image-preview" (Nano Banana Pro) for higher quality at the
# cost of speed.
MODEL_ID = os.environ.get("CNC_GEMINI_MODEL", "gemini-3.1-flash-image-preview")


def _client() -> genai.Client:
    key = config.google_key()
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Add it in Settings or to your .env file."
        )
    return genai.Client(api_key=key)


async def generate(
    prompt: str,
    reference_images: Iterable[bytes] | None = None,
) -> bytes:
    """Single entry point for prompt-only and prompt + reference modes.

    Returns raw PNG bytes from the first inline_data part in the response.
    """
    client = _client()

    parts: list = [prompt]
    for b in reference_images or []:
        parts.append(types.Part.from_bytes(data=b, mime_type="image/png"))

    def _call() -> bytes:
        resp = client.models.generate_content(
            model=MODEL_ID,
            contents=parts,
        )
        for cand in getattr(resp, "candidates", []) or []:
            content = getattr(cand, "content", None)
            for p in getattr(content, "parts", []) or []:
                inline = getattr(p, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    data = inline.data
                    if isinstance(data, str):
                        import base64

                        return base64.b64decode(data)
                    return bytes(data)
        text = getattr(resp, "text", "") or ""
        raise RuntimeError(
            f"Gemini returned no image data. Text response: {text[:200]}"
        )

    return await asyncio.to_thread(_call)


async def _smoke() -> None:
    out = await generate("a simple smiley face, black line art, white background")
    print(f"Got {len(out)} bytes")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_smoke())
