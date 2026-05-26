from __future__ import annotations

import asyncio
import base64
import io
from typing import Iterable

from openai import AsyncOpenAI

from backend import config

MODEL_ID = "gpt-image-1"


def _client() -> AsyncOpenAI:
    key = config.openai_key()
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it in Settings or to your .env file."
        )
    return AsyncOpenAI(api_key=key)


async def generate(
    prompt: str,
    reference_images: Iterable[bytes] | None = None,
    size: str = "1024x1024",
) -> bytes:
    """Single entry point for both prompt-only and prompt + reference image modes.

    Returns raw PNG bytes.
    """
    client = _client()
    refs = list(reference_images or [])

    if not refs:
        resp = await client.images.generate(
            model=MODEL_ID,
            prompt=prompt,
            size=size,
            n=1,
        )
    else:
        files = []
        for i, b in enumerate(refs):
            buf = io.BytesIO(b)
            buf.name = f"ref_{i}.png"
            files.append(buf)
        image_arg = files[0] if len(files) == 1 else files
        resp = await client.images.edit(
            model=MODEL_ID,
            image=image_arg,
            prompt=prompt,
            size=size,
            n=1,
        )

    data = resp.data[0]
    if getattr(data, "b64_json", None):
        return base64.b64decode(data.b64_json)
    if getattr(data, "url", None):
        import httpx

        async with httpx.AsyncClient() as hx:
            r = await hx.get(data.url)
            r.raise_for_status()
            return r.content
    raise RuntimeError("OpenAI image response had neither b64_json nor url")


async def _smoke() -> None:
    out = await generate("a simple smiley face, black line art, white background")
    print(f"Got {len(out)} bytes")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_smoke())
