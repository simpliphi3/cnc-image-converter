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

_BILATERAL_MAX_SIGMA = 5.0    # strength 1.0 -> spatial sigma of 1 + this
_BILATERAL_RANGE = 0.15      # tonal edges bigger than this are preserved
_BILATERAL_MAX_RADIUS = 10   # cap the window so cost stays bounded


@dataclass
class StlParams:
    max_depth_mm: float = 6.0
    base_thickness_mm: float = 3.0
    width_mm: float = 150.0           # physical width of the carved area
    gaussian_blur_sigma: float = 1.5  # smooths noisy depth maps
    bilateral_strength: float = 0.0   # 0..1 edge-preserving smoothing (flatten bg, keep edges)
    detail: float = 0.0               # 0..1 unsharp strength; re-emphasizes fine relief
    curve_points: list | None = None  # [[x,y],...] tonal remap; None = linear (identity)
    background_threshold: float = 0.0  # values <= this are flattened to 0
    invert: bool = False              # set True if dark = high looks better
    target_max_dim_px: int = 600      # downsample heightmap before meshing
    include_skirt: bool = True        # add a vertical wall around the perimeter
    close_bottom: bool = True         # add a flat bottom face for a watertight mesh
    units: Units = "in"

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


def _bilateral(d: np.ndarray, spatial_sigma: float, range_sigma: float) -> np.ndarray:
    """Edge-preserving smoothing: average each pixel with neighbours weighted by
    both distance (spatial) and height similarity (range). Flat regions smooth
    fully while pixels across a real height edge get near-zero weight, so subject
    outlines stay crisp — the local analog of EasyCreate's segmented background.
    """
    radius = int(max(1, min(_BILATERAL_MAX_RADIUS, round(spatial_sigma * 2))))
    padded = np.pad(d, radius, mode="edge")
    h, w = d.shape
    out = np.zeros_like(d)
    wsum = np.zeros_like(d)
    two_sr2 = 2.0 * spatial_sigma * spatial_sigma
    two_rr2 = 2.0 * range_sigma * range_sigma
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            shifted = padded[radius + dy : radius + dy + h, radius + dx : radius + dx + w]
            spatial_w = float(np.exp(-(dx * dx + dy * dy) / two_sr2))
            range_w = np.exp(-((shifted - d) ** 2) / two_rr2)
            weight = spatial_w * range_w
            out += weight * shifted
            wsum += weight
    return (out / wsum).astype(np.float32)


def _apply_curve(d: np.ndarray, points: list) -> np.ndarray:
    """Remap heights through a monotonic control-point curve (piecewise linear).

    x = input height 0..1, y = output height 0..1. An S-curve pushes highlights
    (faces) up and shadows (background) down, restoring bas-relief hierarchy.
    """
    pts = sorted(([float(x), float(y)] for x, y in points), key=lambda pt: pt[0])
    xs = np.array([pt[0] for pt in pts], dtype=np.float32)
    ys = np.array([pt[1] for pt in pts], dtype=np.float32)
    return np.interp(d, xs, ys).astype(np.float32)


def _process_depth(depth01: np.ndarray, p: StlParams) -> np.ndarray:
    d = depth01.astype(np.float32)
    if p.invert:
        d = 1.0 - d
    # Resample first so every shaping step below runs at the final mesh
    # resolution — bounds the cost of the bilateral pass and means what we
    # shape is exactly what gets meshed.
    d = _resample(d, p.target_max_dim_px)
    if p.gaussian_blur_sigma and p.gaussian_blur_sigma > 0:
        d = gaussian_filter(d, sigma=float(p.gaussian_blur_sigma))
    if p.bilateral_strength and p.bilateral_strength > 0:
        spatial = 1.0 + float(p.bilateral_strength) * _BILATERAL_MAX_SIGMA
        d = _bilateral(d, spatial_sigma=spatial, range_sigma=_BILATERAL_RANGE)
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
    # Curve remap runs on the normalized [0,1] range, after threshold — matching
    # EasyCreate's transformation order (threshold -> height curve).
    if p.curve_points:
        d = _apply_curve(d, p.curve_points)
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
        # The bottom is a flat plane, so it only needs its PERIMETER vertices —
        # a full grid would double the mesh for zero geometric information.
        # Walk the rectangle perimeter counter-clockwise (viewed from above),
        # create one z=0 vertex per perimeter grid point, then fan-triangulate.
        # The fan shares every perimeter edge with the skirt, so the mesh stays
        # topologically watertight (no T-vertices).
        perim_rc: list[tuple[int, int]] = []
        for c in range(w):                    # top row, left → right
            perim_rc.append((0, c))
        for r in range(1, h):                 # right column, top → bottom
            perim_rc.append((r, w - 1))
        for c in range(w - 2, -1, -1):        # bottom row, right → left
            perim_rc.append((h - 1, c))
        for r in range(h - 2, 0, -1):         # left column, bottom → top
            perim_rc.append((r, 0))

        bot_offset = len(vertices)
        perim_index: dict[tuple[int, int], int] = {
            rc: bot_offset + i for i, rc in enumerate(perim_rc)
        }
        bot_verts = np.array(
            [[xs[c], ys[r], 0.0] for (r, c) in perim_rc], dtype=np.float32
        )
        vertices = np.concatenate([vertices, bot_verts], axis=0)

        def bidx(r: int, c: int) -> int:
            return perim_index[(r, c)]

        if p.close_bottom:
            # Fan from the first perimeter vertex. Rectangle is convex, so the
            # fan is valid. The perimeter walk above is counter-clockwise seen
            # from +Z, so [v0, i+1, i] gives downward (-Z) normals — outward
            # for the bottom face.
            v0 = bot_offset
            n = len(perim_rc)
            for i in range(1, n - 1):
                faces.append([v0, v0 + i + 1, v0 + i])

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
