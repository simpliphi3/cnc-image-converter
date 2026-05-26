"""Procedural wood texture.

Generates an RGB float32 array with grain rings + fine longitudinal grain.
No image assets shipped — keeps the install lean and avoids licensing concerns.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from scipy.ndimage import gaussian_filter

Palette = Literal["walnut", "oak", "cherry", "maple"]

PALETTES: dict[str, dict] = {
    "walnut": {"light": (170, 120, 80), "dark": (70, 40, 22),  "ring_freq": 0.10, "ring_jitter": 6.0},
    "oak":    {"light": (230, 195, 145), "dark": (140, 95, 55), "ring_freq": 0.07, "ring_jitter": 8.0},
    "cherry": {"light": (205, 130, 95), "dark": (110, 50, 35), "ring_freq": 0.09, "ring_jitter": 7.0},
    "maple":  {"light": (240, 215, 175), "dark": (185, 145, 105), "ring_freq": 0.12, "ring_jitter": 5.0},
}


def make_wood_texture(
    h: int,
    w: int,
    palette: Palette = "walnut",
    seed: int = 0,
) -> np.ndarray:
    """Returns a float32 RGB array shape (h, w, 3) with values in 0..255."""
    pal = PALETTES.get(palette, PALETTES["walnut"])
    rng = np.random.default_rng(seed)

    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    # Place the ring center far below the image so the visible grain looks
    # near-parallel — typical for a plaque cut from the side of the log.
    cx = w * 0.5
    cy = h * 3.5
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

    # Low-frequency turbulence smoothed into something organic.
    noise = (rng.random((h, w), dtype=np.float32) - 0.5) * 12.0
    noise = gaussian_filter(noise, sigma=4.0)

    # Ring pattern (annual growth rings, perturbed by noise).
    rings = np.sin((d + noise * pal["ring_jitter"]) * pal["ring_freq"])
    rings = (rings + 1.0) * 0.5

    # Fine grain stripes (lengthwise micro-grain).
    fine_grain = np.sin((x / 2.8) + noise * 0.4)
    fine_grain = (fine_grain * 0.5 + 0.5) * 0.12

    blend = np.clip(rings * 0.85 + fine_grain, 0.0, 1.0)

    light = np.array(pal["light"], dtype=np.float32)
    dark = np.array(pal["dark"], dtype=np.float32)
    rgb = dark[None, None, :] + (light - dark)[None, None, :] * blend[..., None]
    return rgb


def available_palettes() -> list[str]:
    return list(PALETTES.keys())
