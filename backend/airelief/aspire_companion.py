"""Aspire post-processing cheat-sheet writer.

When an STL was generated from an AI bas-relief render, we drop a short
markdown file next to it explaining what to do in Aspire to match the look
of the AI mockup — specifically the things that cannot come from a depth map:
sunburst background, frame, lettering.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _fmt_mm(v: Any, fallback: str = "—") -> str:
    try:
        return f"{float(v):.1f} mm"
    except (TypeError, ValueError):
        return fallback


def write_steps(
    out_path: Path,
    *,
    stl_basename: str,
    stl_params: dict[str, Any],
    has_text: bool,
    has_sunburst: bool,
    has_frame: bool,
    text: str = "",
) -> Path:
    max_depth = stl_params.get("max_depth_mm")
    base = stl_params.get("base_thickness_mm")
    total = "—"
    try:
        total = f"{float(max_depth or 0) + float(base or 0):.1f} mm"
    except (TypeError, ValueError):
        pass

    lines: list[str] = []
    lines.append(f"# Aspire post-processing for `{stl_basename}.stl`")
    lines.append("")
    lines.append(
        "This STL contains the carved subject only. To match the AI mockup, "
        "add the items below in Aspire after importing the STL onto your job "
        "board. Skip any section that doesn't apply to this piece."
    )
    lines.append("")

    if has_sunburst:
        lines.append("## 1. Radiating sunburst background")
        lines.append("")
        lines.append("- Aspire → **Modeling** tab → import a radial/sunburst texture")
        lines.append("  (or model one with the polar-array tool).")
        lines.append("- Place behind the subject relief; set depth to")
        lines.append("  ~1.5–2 mm *below* the relief base so the subject stands proud.")
        lines.append("- 3D finishing pass with a small ball-nose (1/16\") for crisp rays.")
        lines.append("")

    if has_frame:
        lines.append("## 2. Wooden frame")
        lines.append("")
        lines.append("- Aspire → **Drawing** → rectangle, inset ~10–15 mm from the board edge.")
        lines.append("- Pocket toolpath inside the rectangle to 3–5 mm depth.")
        lines.append("- Optional: round-over the inside edge with a corner-round bit.")
        lines.append("")

    if has_text:
        lines.append("## 3. Lettering")
        lines.append("")
        if text:
            lines.append(f"- Text to engrave: **{text}**")
        lines.append("- Aspire → **Vectors → Create Text**, place at the bottom of the piece.")
        lines.append("- Font: a formal serif (Trajan Pro, Times) reads well for memorial work.")
        lines.append("- **V-carve** toolpath, 60° v-bit, 1–2 mm depth.")
        lines.append("")

    lines.append("## 4. Toolpath order")
    lines.append("")
    lines.append("1. **Roughing** — 6 mm end mill, clear bulk to 0.5 mm above finish.")
    lines.append("2. **3D finishing** — 1/8\" ball-nose, raster strategy across the relief.")
    lines.append("3. **3D detail pass** — 1/16\" ball-nose, pencil/penciling strategy for fine detail.")
    if has_text:
        lines.append("4. **V-carve text** — 60° v-bit.")
    if has_frame:
        n = 5 if has_text else 4
        lines.append(f"{n}. **Frame pocket / profile** — straight bit, multiple passes.")
    lines.append("")

    lines.append("## 5. Geometry used")
    lines.append("")
    lines.append(f"- Max carve depth: **{_fmt_mm(max_depth)}**")
    lines.append(f"- Base thickness: **{_fmt_mm(base)}**")
    lines.append(f"- Total stock thickness needed: **{total}**")
    lines.append("")

    lines.append("## Notes on AI render vs. carve")
    lines.append("")
    lines.append("- The CNC bit sets the smallest detail the carving can hold")
    lines.append("  (≈ half the finish-bit diameter). Sub-millimeter features in")
    lines.append("  the AI render — single hair strands, glasses pinstripes,")
    lines.append("  fine knit-stitch — will round over and may not survive.")
    lines.append("- Use the 3D STL viewer on the Convert page to confirm what")
    lines.append("  actually made it into the mesh before committing to a carve.")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
