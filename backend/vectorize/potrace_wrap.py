from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import potrace
from PIL import Image


@dataclass
class VectorizeParams:
    threshold: int = 128       # 0..255 - pixels darker than this become solid
    invert: bool = False
    turdsize: int = 4          # despeckle: ignore islands smaller than N pixels
    alphamax: float = 1.0      # corner smoothing, 0..1.3
    opttolerance: float = 0.2  # curve fitting tolerance
    max_dim_px: int = 1500     # downscale before trace if larger


def _prepare_bitmap(
    image_bytes: bytes, p: VectorizeParams
) -> tuple[np.ndarray, float, int, int]:
    """Returns (grayscale_array, blacklevel, width, height).

    potrace's `Bitmap(arr, blacklevel)` treats pixels with value < 255*blacklevel as foreground.
    We pass the raw 0..255 grayscale and let potrace threshold; that gives us anti-aliased
    edges potrace can smooth, vs the staircase we'd get from a pre-binarized mask.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    if max(img.size) > p.max_dim_px:
        ratio = p.max_dim_px / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    arr = np.array(img, dtype=np.uint8)
    if p.invert:
        arr = 255 - arr
    blacklevel = max(0.001, min(0.999, p.threshold / 255.0))
    return arr, blacklevel, img.size[0], img.size[1]


def _path_to_svg_path(curve) -> str:
    parts = []
    start = curve.start_point
    parts.append(f"M {start.x:.2f} {start.y:.2f}")
    for seg in curve.segments:
        if getattr(seg, "is_corner", False):
            c = seg.c
            end = seg.end_point
            parts.append(f"L {c.x:.2f} {c.y:.2f} L {end.x:.2f} {end.y:.2f}")
        else:
            c1 = seg.c1
            c2 = seg.c2
            end = seg.end_point
            parts.append(
                f"C {c1.x:.2f} {c1.y:.2f} {c2.x:.2f} {c2.y:.2f} {end.x:.2f} {end.y:.2f}"
            )
    parts.append("Z")
    return " ".join(parts)


def vectorize_sync(image_bytes: bytes, p: VectorizeParams) -> tuple[str, int, int]:
    arr, blacklevel, w, h = _prepare_bitmap(image_bytes, p)
    pot = potrace.Bitmap(arr, blacklevel=blacklevel)
    path = pot.trace(
        turdsize=int(p.turdsize),
        alphamax=float(p.alphamax),
        opttolerance=float(p.opttolerance),
    )
    paths_svg = []
    for curve in path:
        paths_svg.append(_path_to_svg_path(curve))
    d = " ".join(paths_svg)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
        f'<path d="{d}" fill="black" stroke="none" fill-rule="evenodd"/>'
        f"</svg>"
    )
    return svg, w, h


async def vectorize(image_bytes: bytes, params: VectorizeParams) -> tuple[str, int, int]:
    return await asyncio.to_thread(vectorize_sync, image_bytes, params)


def write_svg(svg: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    return out_path
