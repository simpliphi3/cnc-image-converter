from __future__ import annotations

import asyncio
import io
import threading
from typing import Any, Literal

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from backend import config

DepthMode = Literal["ai", "luminance", "hybrid"]

_pipeline = None
_pipeline_lock = threading.Lock()
_device_info: dict[str, Any] = {"device": "unknown", "model": None, "loaded": False}

# Depth sources arrive 8-bit quantized (luminance from an 8-bit image; the AI
# pipeline's PIL depth is 0..255). On smooth, gently-sloped regions — a portrait's
# cheeks, forehead, background — the equal-valued plateaus are wider than any
# sane blur kernel, so smoothing alone can't remove the resulting contour bands
# (measured: blur sigma=3.5 leaves every terrace on a gentle gradient). Adding
# sub-LSB dither breaks the plateaus so the downstream blur reconstructs a
# continuous ramp. Amplitude is +-0.5 of one 8-bit step (~1/510 of full depth,
# well under CNC resolution). Fixed seed keeps exports reproducible.
_DEBAND_STEP = 1.0 / 255.0


def _deband_8bit(arr01: np.ndarray) -> np.ndarray:
    """Dither a [0,1] map by +-0.5 LSB to break 8-bit contour plateaus.

    A fresh seeded RNG per call makes the dither deterministic, so converting
    the same image twice yields byte-identical output.
    """
    rng = np.random.default_rng(0)
    noise = rng.uniform(
        -0.5 * _DEBAND_STEP, 0.5 * _DEBAND_STEP, size=arr01.shape
    ).astype(np.float32)
    return arr01 + noise


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
    quantized = isinstance(depth, Image.Image)  # PIL depth is 0..255; tensor is continuous
    if quantized:
        arr = np.array(depth).astype(np.float32)
    else:
        arr = np.asarray(depth, dtype=np.float32)
    arr = arr - arr.min()
    m = arr.max()
    if m > 0:
        arr = arr / m
    if quantized:
        arr = _deband_8bit(arr)  # only the 8-bit PIL path needs plateau-breaking dither
    return arr


async def estimate(image_bytes: bytes) -> np.ndarray:
    return await asyncio.to_thread(_estimate_sync, image_bytes)


def luminance_from_image_sync(image_bytes: bytes, smoothing: float = 0.0) -> np.ndarray:
    """Use image luminance directly as depth.

    For stylized bas-relief images (especially AI-generated portraits), the
    carved-relief detail is encoded in the photo's lighting and tonal values,
    not in real 3D structure. Monocular depth models will collapse a portrait
    to a uniform silhouette; luminance preserves every facial feature.

    No smoothing by default: this extraction must deliver the source's full
    sharpness. All user-visible smoothing lives in the STL params (blur /
    bilateral sliders) so the Convert page's controls tell the whole truth —
    a hidden blur here meant "sliders at zero" still exported a softened mesh.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    arr = np.array(img, dtype=np.float32) / 255.0
    arr = _deband_8bit(arr)  # break 8-bit plateaus; reconstructs a ramp if blur is applied later
    if smoothing > 0:
        arr = gaussian_filter(arr, sigma=float(smoothing))
    arr = arr - arr.min()
    m = arr.max()
    if m > 0:
        arr = arr / m
    return arr


async def luminance_from_image(image_bytes: bytes, smoothing: float = 0.0) -> np.ndarray:
    return await asyncio.to_thread(luminance_from_image_sync, image_bytes, smoothing)


async def depth_by_mode(image_bytes: bytes, mode: DepthMode) -> np.ndarray:
    """Return a 0..1 depth map using the chosen strategy.

    - 'ai': Depth Anything V2. Best for objects, animals, landscapes, anything
      with real 3D structure. Collapses portraits to silhouettes.
    - 'luminance': Image luminance directly. Best for stylized bas-relief
      artwork (AI-generated portraits, logos, line drawings) — preserves
      every feature encoded in the source's shading.
    - 'hybrid': Multiply AI depth (silhouette) by image luminance. Useful when
      you want the AI to handle background separation while still preserving
      in-subject detail from the photo's tones.
    """
    if mode == "luminance":
        return await luminance_from_image(image_bytes)
    if mode == "ai":
        return await estimate(image_bytes)
    # hybrid
    ai_d = await estimate(image_bytes)
    lum = await luminance_from_image(image_bytes)
    combined = ai_d * lum
    combined -= combined.min()
    m = float(combined.max())
    if m > 0:
        combined /= m
    return combined


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
