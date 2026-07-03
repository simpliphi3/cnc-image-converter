"""Validation script: generate a true grayscale height map from a source photo
and carve it, so we can eyeball whether forward-but-shadowed features (a neck
tucked under the chin) come out proud instead of sinking.

Usage (from the repo root):
    uv run python scripts/try_heightmap.py <photo.png | image_id> [--provider gemini|openai]

Writes into the scratchpad/output dir next to the input (or ./heightmap_out):
    <name>_heightmap.png   the AI height map (LOOK AT THIS FIRST)
    <name>_heightmap.stl   the carved relief from that height map
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

# Importing config runs load_dotenv() so GOOGLE_API_KEY / OPENAI_API_KEY resolve.
from backend import config  # noqa: F401
from backend.airelief.relief_gen import AiReliefRequest, generate_heightmap
from backend.depth import depth_anything
from backend.stl import heightmap_to_stl as stl_mod
from backend.store import files


def _resolve_input(arg: str) -> tuple[bytes, str]:
    p = Path(arg)
    if p.exists():
        return p.read_bytes(), p.stem
    # otherwise treat as an image_id from the app's library
    img = files.get_image(arg)
    if not img:
        raise SystemExit(f"'{arg}' is neither a file nor a known image_id")
    src = files.image_path(img["project_id"], img["filename"])
    return src.read_bytes(), f"img_{arg[:8]}"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="path to a source photo, or an image_id from the app")
    ap.add_argument("--provider", choices=["gemini", "openai"], default="gemini")
    ap.add_argument("--outdir", default="heightmap_out")
    args = ap.parse_args()

    image_bytes, stem = _resolve_input(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Generating height map via {args.provider} ...")
    req = AiReliefRequest(provider=args.provider)  # defaults: portrait / simple frame
    hm_png = await generate_heightmap(image_bytes, req)
    hm_path = outdir / f"{stem}_heightmap.png"
    hm_path.write_bytes(hm_png)
    print(f"  wrote {hm_path}  <-- LOOK AT THIS: is the neck lighter (higher) than the collar?")

    # Carve it: the height map's luminance IS the height, so luminance mode is correct.
    depth = depth_anything.luminance_from_image_sync(hm_png, smoothing=1.5)
    params = stl_mod.StlParams(width_mm=150.0, max_depth_mm=6.0, base_thickness_mm=3.0)
    result = stl_mod.heightmap_to_stl_sync(depth, params)
    stl_path = outdir / f"{stem}_heightmap.stl"
    stl_mod.write_stl(result, stl_path)
    print(f"  wrote {stl_path}  <-- open in a viewer/Aspire to confirm the neck stands proud")


if __name__ == "__main__":
    asyncio.run(main())
