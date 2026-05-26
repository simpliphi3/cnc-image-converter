from __future__ import annotations

import asyncio
import io
import threading
from typing import Any

import numpy as np
from PIL import Image

from backend import config

_pipeline = None
_pipeline_lock = threading.Lock()
_device_info: dict[str, Any] = {"device": "unknown", "model": None, "loaded": False}


def device_info() -> dict[str, Any]:
    return dict(_device_info)


def _load_pipeline():
    global _pipeline
    with _pipeline_lock:
        if _pipeline is not None:
            return _pipeline
        import torch
        from transformers import pipeline

        model_id = config.depth_model_id()
        device = 0 if torch.cuda.is_available() else -1
        _device_info["device"] = "cuda" if device == 0 else "cpu"
        _device_info["model"] = model_id
        _pipeline = pipeline(
            task="depth-estimation",
            model=model_id,
            device=device,
        )
        _device_info["loaded"] = True
        return _pipeline


def _estimate_sync(image_bytes: bytes) -> np.ndarray:
    """Returns a float32 array in [0, 1] where 1 = nearest to camera."""
    pipe = _load_pipeline()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    out = pipe(img)
    depth = out["depth"]
    if isinstance(depth, Image.Image):
        arr = np.array(depth).astype(np.float32)
    else:
        arr = np.asarray(depth, dtype=np.float32)
    arr = arr - arr.min()
    m = arr.max()
    if m > 0:
        arr = arr / m
    return arr


async def estimate(image_bytes: bytes) -> np.ndarray:
    return await asyncio.to_thread(_estimate_sync, image_bytes)


def depth_to_png_16bit(depth01: np.ndarray) -> bytes:
    """Encode a [0,1] depth map as 16-bit grayscale PNG (Aspire-friendly)."""
    arr16 = np.clip(depth01, 0.0, 1.0) * 65535.0
    arr16 = arr16.astype(np.uint16)
    img = Image.fromarray(arr16, mode="I;16")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def depth_to_png_8bit_preview(depth01: np.ndarray) -> bytes:
    arr8 = (np.clip(depth01, 0.0, 1.0) * 255.0).astype(np.uint8)
    img = Image.fromarray(arr8, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
