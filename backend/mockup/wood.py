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
    # contrast = how strongly rings stand out (0..1)
    "walnut": {"light": (135, 95, 65),  "dark": (75, 45, 28),  "contrast": 0.55},
    "oak":    {"light": (215, 180, 135), "dark": (160, 115, 75), "contrast": 0.45},
    "cherry": {"light": (180, 115, 85), "dark": (120, 65, 45),  "contrast": 0.50},
    "maple":  {"light": (235, 210, 170), "dark": (195, 165, 125), "contrast": 0.35},
}


def make_wood_texture(
    h: int,
    w: int,
    palette: Palette = "walnut",
    seed: int = 0,
) -> np.ndarray:
    """Returns a float32 RGB array shape (h, w, 3) with values in 0..255.

    Plank-style flat-sawn grain: mostly parallel lines along one axis with a
    very gentle long-wavelength wave, soft fiber noise along the grain, and a
    couple of optional low-contrast figure marks. Tuned to look like a sanded
    board, not a leather hide.
    """
    pal = PALETTES.get(palette, PALETTES["walnut"])
    rng = np.random.default_rng(seed)

    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    long_side = float(max(h, w))

    # Lay grain along the LONG axis. For a portrait image (h > w), grain runs
    # vertically; for landscape, horizontally. Use `along` for the direction
    # PARALLEL to grain and `across` for PERPENDICULAR (where rings stack up).
    if h >= w:
        along, across = y, x
    else:
        along, across = x, y

    # Aim for ~8 visible grain lines on the across-grain axis.
    cross_extent = float(np.ptp(across))
    target_rings = 8.0
    ring_period = max(8.0, cross_extent / target_rings)

    # Two very gentle long waves so grain isn't pin-straight. Tiny amplitude
    # relative to image — gives a subtle cathedral curve.
    phase = rng.random() * 6.28
    wave_amp = ring_period * 0.20
    wave_wl = long_side * 0.9
    waved = across + wave_amp * np.sin(2 * np.pi * along / wave_wl + phase)
    waved += wave_amp * 0.4 * np.sin(2 * np.pi * along / (wave_wl * 0.43) + phase * 1.7)

    # Very slight per-pixel perpendicular jitter for organic edges. SMALL.
    # Gaussian-smoothed along the grain so it doesn't add high-frequency noise.
    if h >= w:
        jitter_sigma = (long_side * 0.04, max(1.0, long_side * 0.003))
    else:
        jitter_sigma = (max(1.0, long_side * 0.003), long_side * 0.04)
    jitter = (rng.random((h, w), dtype=np.float32) - 0.5)
    jitter = gaussian_filter(jitter, sigma=jitter_sigma)
    jitter /= max(jitter.std(), 1e-6)
    waved = waved + jitter * ring_period * 0.06

    # Grain lines: lightly sharpened sine.
    base = np.sin(waved * (2 * np.pi / ring_period))
    rings = 0.5 + 0.5 * np.sign(base) * (np.abs(base) ** 0.7)

    # Soft along-grain fiber: low-contrast streaks parallel to the grain.
    fiber_sigma = (
        (max(0.5, long_side * 0.0006), long_side * 0.02)
        if h >= w else
        (long_side * 0.02, max(0.5, long_side * 0.0006))
    )
    fiber = gaussian_filter(
        (rng.random((h, w), dtype=np.float32) - 0.5), sigma=fiber_sigma
    )
    fiber /= max(fiber.std(), 1e-6)

    value = 0.5 + (rings - 0.5) * pal["contrast"] + fiber * 0.07
    value = np.clip(value, 0.0, 1.0)

    light = np.array(pal["light"], dtype=np.float32)
    dark = np.array(pal["dark"], dtype=np.float32)
    rgb = dark[None, None, :] + (light - dark)[None, None, :] * value[..., None]
    return rgb


def available_palettes() -> list[str]:
    return list(PALETTES.keys())
