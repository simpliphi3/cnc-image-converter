"""AI bas-relief render generation.

Sends a source photo to a single image-gen model (Gemini by default) with a
tuned prompt that produces a carved-walnut-plaque render. The result is both
the customer-facing mockup AND the source for the depth -> STL pipeline,
which is how we keep what we render and what we carve in lockstep.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from backend.image_gen import gemini_client, openai_client

Style = Literal["memorial", "portrait", "scenic", "sign_logo"]
Frame = Literal["none", "simple", "ornate"]
Provider = Literal["gemini", "openai"]

_STYLE_DESCRIPTIONS: dict[str, str] = {
    "memorial": "memorial plaque carving with a respectful, formal composition",
    "portrait": "decorative portrait carving suitable for a home wall plaque",
    "scenic": "scenic landscape relief with naturalistic carved detail",
    "sign_logo": "logo or sign carving with bold flat-style relief and crisp edges",
}

_FRAME_DESCRIPTIONS: dict[str, str] = {
    "none": "no frame — the carved subject fills the board edge to edge",
    "simple": "a simple wooden inset frame with beveled inner edges surrounding the piece",
    "ornate": "an ornate carved wooden frame with classical molding around the piece",
}

_PALETTE_TO_WOOD: dict[str, str] = {
    "walnut": "rich dark American walnut with subtle straight grain",
    "oak": "white oak with prominent open grain figure",
    "cherry": "black cherry with smooth reddish-brown grain",
    "maple": "hard maple with subtle pale grain and a creamy tone",
}


@dataclass
class AiReliefRequest:
    style: Style = "portrait"
    palette: str = "walnut"
    frame: Frame = "simple"
    text: str = ""
    sunburst_background: bool = True
    additional_notes: str = ""
    provider: Provider = "gemini"


def build_prompt(req: AiReliefRequest) -> str:
    wood = _PALETTE_TO_WOOD.get(req.palette, _PALETTE_TO_WOOD["walnut"])
    style_desc = _STYLE_DESCRIPTIONS.get(req.style, _STYLE_DESCRIPTIONS["portrait"])
    frame_desc = _FRAME_DESCRIPTIONS.get(req.frame, _FRAME_DESCRIPTIONS["simple"])

    background_clause = (
        " Background: tightly-spaced radiating concentric sunburst pattern "
        "machined in lower relief behind the subject, like a CNC sunburst toolpath."
        if req.sunburst_background
        else " Background: smoothly carved flat field, no decorative pattern."
    )

    text_clause = ""
    if req.text:
        text_clause = (
            f' Carved inscription at the bottom of the piece in formal serif '
            f'lettering reading exactly: "{req.text}". V-carved appearance with '
            f'crisp triangular grooves.'
        )

    notes = f" {req.additional_notes.strip()}" if req.additional_notes else ""

    return (
        f"Render the subject of this photograph as a high-relief carving in {wood}, "
        f"in the form of a {style_desc}. The subject must be carved in deep "
        f"dimensional bas-relief — convex cheeks, defined brow ridges, sculpted "
        f"hair with visible strands, textured clothing showing weave and folds, "
        f"glasses and jewelry with realistic shadow lines. Lighting from upper-"
        f"left with dramatic shadows that convey real depth.{background_clause} "
        f"{frame_desc.capitalize()}. Photorealistic walnut wood carving, "
        f"professional CNC-machined plaque appearance, sharp small detail, "
        f"smooth large surfaces, single integrated wood piece.{text_clause}{notes}"
    )


def cache_key(image_id: str, req: AiReliefRequest) -> str:
    """Stable hash so identical requests reuse the same cached render.

    Hashes BOTH prompts: a change to either the render prompt or the
    heightmap-conversion prompt must invalidate the cached pair, since the
    heightmap is chained from the render.
    """
    h = hashlib.sha256()
    h.update(image_id.encode())
    h.update(req.provider.encode())
    h.update(build_prompt(req).encode())
    h.update(build_heightmap_prompt(req).encode())
    return h.hexdigest()[:16]


async def generate_relief(image_bytes: bytes, req: AiReliefRequest) -> bytes:
    prompt = build_prompt(req)
    if req.provider == "openai":
        return await openai_client.generate(prompt, [image_bytes])
    return await gemini_client.generate(prompt, [image_bytes])


def build_heightmap_prompt(req: AiReliefRequest) -> str:
    """Prompt to convert the LIT RENDER into a grayscale height map.

    The input image for this call is the carving render itself (not the source
    photo), so the model's job is a faithful re-encoding, not a re-imagining:
    reproduce the exact composition, but express elevation as brightness
    instead of lit wood. This is what keeps 'what you approved' and 'what
    carves' aligned — chaining from the render means the frame, sunburst, and
    caption the user saw all survive into the carve source, with correct
    height semantics (a dark-stained subject no longer sinks below pale
    pillows the way raw render luminance made it).
    """
    return (
        "This image shows a finished CNC wood relief carving. Convert it into the "
        "GRAYSCALE HEIGHT MAP (depth map) that would carve this exact piece. "
        "CRITICAL: reproduce THIS image's composition, layout, and every element "
        "exactly — same frame, same background pattern, same subject pose and "
        "position, same lettering if present. Do not add, remove, move, or "
        "restyle anything. Encode ONLY surface elevation as brightness: pure "
        "white = the highest surfaces (the parts of the carving that project "
        "furthest toward the viewer — the main subject's nearest forms), "
        "progressively darker grays = surfaces set further back, black = the "
        "deepest recesses. Ignore the wood's color and staining entirely: a "
        "dark-stained area that projects forward must be BRIGHT, because "
        "brightness means elevation, not tone. Remove all lighting: NO cast "
        "shadows, NO directional shading, NO specular highlights, NO wood grain "
        "or color. The main subject must read as the proudest (brightest) "
        "element, standing clearly above pillows, bedding, or backdrop elements "
        "around it. Preserve fine relief texture — fur strands, fabric weave, "
        "wrinkles, feather lines — as subtle shallow brightness modulation on "
        "top of each form's base elevation rather than smoothing it away. "
        "A raised frame border sits at one consistent mid-high level; a "
        "background pattern (e.g. sunburst rays) stays in low relief just above "
        "the deepest background. Output a clean, matte grayscale image, "
        "straight-on orthographic view."
    )


async def generate_heightmap(render_bytes: bytes, req: AiReliefRequest) -> bytes:
    """Convert the lit render into a height map. ``render_bytes`` must be the
    output of :func:`generate_relief`, not the original source photo."""
    prompt = build_heightmap_prompt(req)
    if req.provider == "openai":
        return await openai_client.generate(prompt, [render_bytes])
    return await gemini_client.generate(prompt, [render_bytes])
