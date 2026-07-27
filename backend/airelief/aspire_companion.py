"""Aspire post-processing cheat-sheet writer.

Two flavors depending on how the STL was carved from an AI bas-relief render:

- ``subject_only=True`` (default) — STL contains just the carved subject on a
  plain field. The full mockup's frame, sunburst, and any caption need to be
  added in Aspire with dedicated toolpaths (cleaner but more work).
- ``subject_only=False`` — STL was carved from the full mockup, so frame /
  sunburst / caption are already baked in. Companion just covers toolpath
  order and reminds the user what's included so they don't double-add.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _fmt_mm(v: Any, fallback: str = "—") -> str:
    try:
        return f"{float(v):.1f} mm"
    except (TypeError, ValueError):
        return fallback


def _geometry_and_notes_footer(
    max_depth: Any, base: Any, total: str, section, lines: list[str]
) -> None:
    lines.append(section("Geometry used"))
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


def _write_subject_only(
    *,
    stl_basename: str,
    max_depth: Any,
    base: Any,
    total: str,
    has_text: bool,
    has_sunburst: bool,
    has_frame: bool,
    text: str,
) -> list[str]:
    lines: list[str] = []
    lines.append(f"# Aspire post-processing for `{stl_basename}.stl`")
    lines.append("")
    lines.append(
        "This STL contains the carved **subject only**. To match the AI "
        "mockup, add the items below in Aspire after importing the STL onto "
        "your job board. Skip any section that doesn't apply to this piece."
    )
    lines.append("")

    section_n = 0

    def section(title: str) -> str:
        nonlocal section_n
        section_n += 1
        return f"## {section_n}. {title}"

    if has_sunburst:
        lines.append(section("Radiating sunburst background"))
        lines.append("")
        lines.append("- Aspire → **Modeling** tab → import a radial/sunburst texture")
        lines.append("  (or model one with the polar-array tool).")
        lines.append("- Place behind the subject relief; set depth to")
        lines.append("  ~1.5–2 mm *below* the relief base so the subject stands proud.")
        lines.append("- 3D finishing pass with a small ball-nose (1/16\") for crisp rays.")
        lines.append("")

    if has_frame:
        lines.append(section("Wooden frame"))
        lines.append("")
        lines.append("- Aspire → **Drawing** → rectangle, inset ~10–15 mm from the board edge.")
        lines.append("- Pocket toolpath inside the rectangle to 3–5 mm depth.")
        lines.append("- Optional: round-over the inside edge with a corner-round bit.")
        lines.append("")

    if has_text:
        lines.append(section("Lettering"))
        lines.append("")
        if text:
            lines.append(f"- Text to engrave: **{text}**")
        lines.append("- Aspire → **Vectors → Create Text**, place at the bottom of the piece.")
        lines.append("- Font: a formal serif (Trajan Pro, Times) reads well for memorial work.")
        lines.append("- **V-carve** toolpath, 60° v-bit, 1–2 mm depth.")
        lines.append("")

    lines.append(section("Toolpath order"))
    lines.append("")
    step = 1
    lines.append(f"{step}. **Roughing** — 6 mm end mill, clear bulk to 0.5 mm above finish.")
    step += 1
    lines.append(f"{step}. **3D finishing** — 1/8\" ball-nose, raster strategy across the relief.")
    step += 1
    lines.append(f"{step}. **3D detail pass** — 1/16\" ball-nose, pencil/penciling strategy for fine detail.")
    if has_text:
        step += 1
        lines.append(f"{step}. **V-carve text** — 60° v-bit.")
    if has_frame:
        step += 1
        lines.append(f"{step}. **Frame pocket / profile** — straight bit, multiple passes.")
    lines.append("")

    _geometry_and_notes_footer(max_depth, base, total, section, lines)
    return lines


def _write_full_mockup(
    *,
    stl_basename: str,
    max_depth: Any,
    base: Any,
    total: str,
    has_text: bool,
    has_sunburst: bool,
    has_frame: bool,
    text: str,
) -> list[str]:
    lines: list[str] = []
    lines.append(f"# Aspire post-processing for `{stl_basename}.stl`")
    lines.append("")
    lines.append(
        "This STL was carved from the **full AI mockup**, so the frame, "
        "sunburst background, and any caption are already in the mesh — no "
        "compositing in Aspire required. Just cut it."
    )
    lines.append("")

    section_n = 0

    def section(title: str) -> str:
        nonlocal section_n
        section_n += 1
        return f"## {section_n}. {title}"

    included: list[str] = []
    if has_frame:
        included.append("- **Frame** — carved as part of the relief.")
    if has_sunburst:
        included.append("- **Radiating sunburst background** — carved as part of the relief.")
    if has_text:
        label = f' ({text!r})' if text else ""
        included.append(
            f"- **Caption / lettering**{label} — already inscribed by the AI. "
            "Do NOT add text vectors on top or you'll double-engrave."
        )
    if included:
        lines.append(section("What's already in the STL"))
        lines.append("")
        lines.extend(included)
        lines.append("")

    lines.append(section("Toolpath order"))
    lines.append("")
    lines.append("1. **Roughing** — 6 mm end mill, clear bulk to 0.5 mm above finish.")
    lines.append("2. **3D finishing** — 1/8\" ball-nose, raster strategy across the whole mesh.")
    lines.append("3. **3D detail pass** — 1/16\" ball-nose, pencil/penciling strategy for fine detail (hair, sunburst rays, caption edges).")
    lines.append("")
    lines.append("No v-carve or pocket passes needed — everything decorative is 3D relief.")
    lines.append("")

    lines.append(section("If you want a physical board edge around the plaque"))
    lines.append("")
    lines.append("- The STL's outer rectangle IS the piece boundary. If you want a")
    lines.append("  larger board with a routed edge outside the plaque, add a")
    lines.append("  profile-cut vector in Aspire around the STL's footprint.")
    lines.append("")

    _geometry_and_notes_footer(max_depth, base, total, section, lines)
    return lines


def write_steps(
    out_path: Path,
    *,
    stl_basename: str,
    stl_params: dict[str, Any],
    has_text: bool,
    has_sunburst: bool,
    has_frame: bool,
    text: str = "",
    subject_only: bool = True,
) -> Path:
    max_depth = stl_params.get("max_depth_mm")
    base = stl_params.get("base_thickness_mm")
    total = "—"
    try:
        total = f"{float(max_depth or 0) + float(base or 0):.1f} mm"
    except (TypeError, ValueError):
        pass

    if subject_only:
        lines = _write_subject_only(
            stl_basename=stl_basename,
            max_depth=max_depth,
            base=base,
            total=total,
            has_text=has_text,
            has_sunburst=has_sunburst,
            has_frame=has_frame,
            text=text,
        )
    else:
        lines = _write_full_mockup(
            stl_basename=stl_basename,
            max_depth=max_depth,
            base=base,
            total=total,
            has_text=has_text,
            has_sunburst=has_sunburst,
            has_frame=has_frame,
            text=text,
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
