from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import trimesh
from scipy.ndimage import gaussian_filter, zoom

Units = Literal["mm", "in"]

_DETAIL_RADIUS_PX = 2.0  # blur radius for the unsharp-mask high-pass
_DETAIL_MAX_GAIN = 1.5   # sharpening applied at detail = 1.0


@dataclass
class StlParams:
    max_depth_mm: float = 6.0
    base_thickness_mm: float = 3.0
    width_mm: float = 150.0           # physical width of the carved area
    gaussian_blur_sigma: float = 1.5  # smooths noisy depth maps
    detail: float = 0.0               # 0..1 unsharp strength; re-emphasizes fine relief
    background_threshold: float = 0.0  # values <= this are flattened to 0
    invert: bool = False              # set True if dark = high looks better
    target_max_dim_px: int = 600      # downsample heightmap before meshing
    include_skirt: bool = True        # add a vertical wall around the perimeter
    close_bottom: bool = True         # add a flat bottom face for a watertight mesh
    units: Units = "mm"

    def to_export_units_scale(self) -> float:
        return 1.0 if self.units == "mm" else 1.0 / 25.4


@dataclass
class StlResult:
    mesh: trimesh.Trimesh
    processed_depth: np.ndarray  # the 0..1 depth map actually used
    params: StlParams = field(default_factory=StlParams)


def _resample(depth01: np.ndarray, target_max_dim: int) -> np.ndarray:
    h, w = depth01.shape
    m = max(h, w)
    if m <= target_max_dim:
        return depth01.astype(np.float32)
    s = target_max_dim / m
    return zoom(depth01, s, order=1).astype(np.float32)


def _process_depth(depth01: np.ndarray, p: StlParams) -> np.ndarray:
    d = depth01.astype(np.float32)
    if p.invert:
        d = 1.0 - d
    if p.gaussian_blur_sigma and p.gaussian_blur_sigma > 0:
        d = gaussian_filter(d, sigma=float(p.gaussian_blur_sigma))
    if p.detail and p.detail > 0:
        # Unsharp mask: re-emphasize genuine relief after the denoise blur.
        # final = d + k*A*(d - blur(d)) is algebraically the raw/enhanced
        # crossfade with k = p.detail; clip tames overshoot so a single hot
        # pixel can't compress the whole map when we normalize below.
        blurred = gaussian_filter(d, sigma=_DETAIL_RADIUS_PX)
        d = d + (float(p.detail) * _DETAIL_MAX_GAIN) * (d - blurred)
        d = np.clip(d, 0.0, 1.0)
    if p.background_threshold > 0:
        d = np.where(d <= p.background_threshold, 0.0, d)
    d = d - d.min()
    m = d.max()
    if m > 0:
        d = d / m
    d = _resample(d, p.target_max_dim_px)
    return d


def _build_mesh(depth01: np.ndarray, p: StlParams) -> trimesh.Trimesh:
    """Build a watertight relief mesh from a 0..1 heightmap.

    Coordinate frame: X right, Y up, Z out of the board (toward the viewer).
    Z = 0 is the back of the board; Z = base_thickness + max_depth is the highest point.
    """
    # Image row 0 is the TOP of the picture, but our Y axis points up (row r ->
    # y increasing), so a raw mapping lands the top of the image at the bottom
    # of the board — a vertical mirror. Flip rows here (not by reversing the Y
    # coords, which would invert the face winding / normals) so the relief comes
    # out oriented like the source. Applied only in the mesh; the exported depth
    # PNG keeps source row order for Aspire's Component-from-Bitmap importer.
    depth01 = np.flipud(depth01)
    h, w = depth01.shape
    aspect = h / w
    width_mm = p.width_mm
    height_mm = width_mm * aspect

    xs = np.linspace(0.0, width_mm, w, dtype=np.float32)
    ys = np.linspace(0.0, height_mm, h, dtype=np.float32)
    xv, yv = np.meshgrid(xs, ys)

    top_z = p.base_thickness_mm + depth01 * p.max_depth_mm
    top_verts = np.stack([xv, yv, top_z.astype(np.float32)], axis=-1).reshape(-1, 3)

    def idx(r: int, c: int) -> int:
        return r * w + c

    faces: list[list[int]] = []
    for r in range(h - 1):
        for c in range(w - 1):
            a = idx(r, c)
            b = idx(r, c + 1)
            cc = idx(r + 1, c)
            d = idx(r + 1, c + 1)
            faces.append([a, b, d])
            faces.append([a, d, cc])

    vertices = top_verts

    if p.close_bottom or p.include_skirt:
        bottom_xv = xv.copy()
        bottom_yv = yv.copy()
        bottom_z = np.zeros_like(top_z)
        bot_verts = np.stack(
            [bottom_xv, bottom_yv, bottom_z.astype(np.float32)], axis=-1
        ).reshape(-1, 3)
        bot_offset = len(vertices)
        vertices = np.concatenate([vertices, bot_verts], axis=0)

        def bidx(r: int, c: int) -> int:
            return bot_offset + r * w + c

        if p.close_bottom:
            for r in range(h - 1):
                for c in range(w - 1):
                    a = bidx(r, c)
                    b = bidx(r, c + 1)
                    cc = bidx(r + 1, c)
                    d = bidx(r + 1, c + 1)
                    faces.append([a, d, b])
                    faces.append([a, cc, d])

        if p.include_skirt:
            for c in range(w - 1):
                t1, t2 = idx(0, c), idx(0, c + 1)
                b1, b2 = bidx(0, c), bidx(0, c + 1)
                faces.append([t1, b1, t2])
                faces.append([t2, b1, b2])
                t1, t2 = idx(h - 1, c), idx(h - 1, c + 1)
                b1, b2 = bidx(h - 1, c), bidx(h - 1, c + 1)
                faces.append([t1, t2, b1])
                faces.append([t2, b2, b1])
            for r in range(h - 1):
                t1, t2 = idx(r, 0), idx(r + 1, 0)
                b1, b2 = bidx(r, 0), bidx(r + 1, 0)
                faces.append([t1, t2, b1])
                faces.append([t2, b2, b1])
                t1, t2 = idx(r, w - 1), idx(r + 1, w - 1)
                b1, b2 = bidx(r, w - 1), bidx(r + 1, w - 1)
                faces.append([t1, b1, t2])
                faces.append([t2, b1, b2])

    faces_arr = np.asarray(faces, dtype=np.int64)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces_arr, process=False)
    scale = p.to_export_units_scale()
    if scale != 1.0:
        mesh.apply_scale(scale)
    return mesh


def heightmap_to_stl_sync(depth01: np.ndarray, params: StlParams) -> StlResult:
    processed = _process_depth(depth01, params)
    mesh = _build_mesh(processed, params)
    return StlResult(mesh=mesh, processed_depth=processed, params=params)


async def heightmap_to_stl(depth01: np.ndarray, params: StlParams) -> StlResult:
    return await asyncio.to_thread(heightmap_to_stl_sync, depth01, params)


def write_stl(result: StlResult, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.mesh.export(out_path, file_type="stl")
    return out_path
