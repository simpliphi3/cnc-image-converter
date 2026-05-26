"""Dimension presets for the Convert panel.

`width_mm` is applied to the horizontal (X) dimension of the source image;
height is derived from the image's aspect ratio. `max_depth_mm` is a sensible
default carve depth for that size; the user can still override.
"""

from __future__ import annotations

from typing import TypedDict


class DimensionPreset(TypedDict):
    id: str
    name: str
    width_mm: float | None
    max_depth_mm: float | None


DIMENSION_PRESETS: list[DimensionPreset] = [
    {"id": "custom", "name": "Custom — set values manually", "width_mm": None, "max_depth_mm": None},
    {"id": "coaster_4in", "name": "Coaster — 4 in wide (102 mm)", "width_mm": 102.0, "max_depth_mm": 3.0},
    {"id": "medallion_6in", "name": "Medallion — 6 in (152 mm)", "width_mm": 152.0, "max_depth_mm": 5.0},
    {"id": "small_plaque_8in", "name": "Small plaque — 8 in wide (203 mm)", "width_mm": 203.0, "max_depth_mm": 5.0},
    {"id": "address_sign_12in", "name": "Address sign — 12 in wide (305 mm)", "width_mm": 305.0, "max_depth_mm": 4.0},
    {"id": "plaque_12in", "name": "Plaque — 12 in wide (305 mm)", "width_mm": 305.0, "max_depth_mm": 6.0},
    {"id": "door_sign_18in", "name": "Door sign — 18 in wide (457 mm)", "width_mm": 457.0, "max_depth_mm": 5.0},
    {"id": "cutting_board_18in", "name": "Cutting board — 18 in wide (457 mm)", "width_mm": 457.0, "max_depth_mm": 3.0},
    {"id": "large_sign_24in", "name": "Large sign — 24 in wide (610 mm)", "width_mm": 610.0, "max_depth_mm": 8.0},
    {"id": "extra_large_36in", "name": "Extra-large — 36 in wide (914 mm)", "width_mm": 914.0, "max_depth_mm": 10.0},
]
