"""Render a depth map as a carved relief on a wooden background.

Pipeline:
  1. Smooth / invert / threshold the depth (same conceptual prep as STL).
  2. Compute surface normals from the depth gradient.
  3. Lambert-shade against a light direction.
  4. Add a touch of ambient occlusion so deep carved areas read as 'recessed'.
  5. Multiply the shading against a procedural wood texture.
  6. Encode as JPEG (smaller than PNG for the client preview, lossy is fine).
"""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from typing import Literal

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, zoom

from backend.mockup.wood import Palette, make_wood_texture


@dataclass
class MockupParams:
    palette: Palette = "walnut"
    wood_seed: int = 7
    relief_scale: float = 60.0       # higher = sharper carved edges in shading
    ambient: float = 0.35             # 0..1, floor brightness
    ao_strength: float = 0.35         # 0..1, how dark the deepest carves get
    light_x: float = -0.55            # negative = light from the left
    light_y: float = -0.55            # negative = light from the top
    light_z: float = 0.62
    smoothing: float = 1.2
    invert: bool = False              # carve the dark areas vs the light areas
    background_threshold: float = 0.0
    max_dim_px: int = 900             # cap render size for speed


def _prep_depth(depth01: np.ndarray, p: MockupParams) -> np.ndarray:
    d = depth01.astype(np.float32)
    if p.invert:
        d = 1.0 - d
    if p.smoothing > 0:
        d = gaussian_filter(d, sigma=float(p.smoothing))
    if p.background_threshold > 0:
        d = np.where(d <= p.background_threshold, 0.0, d)
    d = d - d.min()
    m = d.max()
    if m > 0:
        d = d / m
    h, w = d.shape
    m_dim = max(h, w)
    if m_dim > p.max_dim_px:
        d = zoom(d, p.max_dim_px / m_dim, order=1).astype(np.float32)
    return d


def render_sync(depth01: np.ndarray, p: MockupParams) -> bytes:
    d = _prep_depth(depth01, p)
    h, w = d.shape

    gy, gx = np.gradient(d)
    nx = -gx * p.relief_scale
    ny = -gy * p.relief_scale
    nz = np.ones_like(nx)
    inv_n = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    nx *= inv_n
    ny *= inv_n
    nz *= inv_n

    lx, ly, lz = p.light_x, p.light_y, p.light_z
    ll = float(np.sqrt(lx * lx + ly * ly + lz * lz)) or 1.0
    lx, ly, lz = lx / ll, ly / ll, lz / ll

    lambert = np.clip(nx * lx + ny * ly + nz * lz, 0.0, 1.0)

    # Carved areas (low d) sit in a slight shadow.
    ao = 1.0 - (1.0 - d) * p.ao_strength

    intensity = p.ambient + (1.0 - p.ambient) * lambert
    intensity *= ao

    wood = make_wood_texture(h, w, p.palette, p.wood_seed)
    rgb = wood * intensity[..., None]
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    buf = io.BytesIO()
    Image.fromarray(rgb, mode="RGB").save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def render(depth01: np.ndarray, p: MockupParams) -> bytes:
    return await asyncio.to_thread(render_sync, depth01, p)
