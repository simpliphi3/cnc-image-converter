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
    """Stable hash so identical requests reuse the same cached render."""
    h = hashlib.sha256()
    h.update(image_id.encode())
    h.update(req.provider.encode())
    h.update(build_prompt(req).encode())
    return h.hexdigest()[:16]


async def generate_relief(image_bytes: bytes, req: AiReliefRequest) -> bytes:
    prompt = build_prompt(req)
    if req.provider == "openai":
        return await openai_client.generate(prompt, [image_bytes])
    return await gemini_client.generate(prompt, [image_bytes])
