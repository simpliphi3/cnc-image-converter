from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from backend import config
from backend.image_gen import gemini_client, openai_client
from backend.store import files, projects

SUPPORTED_MODELS = ["openai", "gemini"]


async def _generate_one(
    model: str,
    *,
    prompt: str,
    reference_bytes: list[bytes],
) -> bytes:
    if model == "openai":
        return await openai_client.generate(prompt, reference_bytes)
    if model == "gemini":
        return await gemini_client.generate(prompt, reference_bytes)
    raise ValueError(f"Unknown model: {model}")


def _load_image_bytes(image_id: str) -> bytes | None:
    img = files.get_image(image_id)
    if not img or not img.get("filename"):
        return None
    p = files.image_path(img["project_id"], img["filename"])
    if not p.exists():
        return None
    return p.read_bytes()


async def generate_for_turn(
    project_id: str,
    *,
    prompt: str,
    user_reference_image_ids: list[str],
    models: list[str],
    use_session_memory: bool = True,
) -> dict[str, Any]:
    """Run a generation turn.

    For each selected model:
      - Collect reference images: any user-provided refs for THIS turn, plus (if memory is
        on and no explicit refs were supplied) the most recent successful generation from
        this same model in this project. This is what gives multi-turn iteration its memory
        without forcing the user to re-attach the previous image.
      - Call the model in parallel with the others.
      - Save the result (or the error) under the new turn.
    """
    models = [m for m in models if m in SUPPORTED_MODELS]
    if not models:
        raise ValueError("No supported models selected")

    turn = projects.add_turn(
        project_id,
        prompt=prompt,
        ref_image_ids=user_reference_image_ids,
        models=models,
    )
    turn_id = turn["id"]

    user_ref_bytes = [
        b
        for b in (_load_image_bytes(i) for i in user_reference_image_ids)
        if b is not None
    ]

    async def _run_model(model: str) -> dict[str, Any]:
        refs = list(user_ref_bytes)
        if not refs and use_session_memory:
            prev_id = projects.last_generated_image_id(project_id, model)
            if prev_id:
                pb = _load_image_bytes(prev_id)
                if pb:
                    refs.append(pb)
        try:
            png = await _generate_one(model, prompt=prompt, reference_bytes=refs)
            saved = files.save_image_bytes(
                project_id,
                png,
                role="generated",
                turn_id=turn_id,
                model=model,
                extension="png",
            )
            projects.touch_project(project_id, cover_image_id=saved["id"])
            return saved
        except Exception as e:
            return files.record_image_error(
                project_id, turn_id=turn_id, model=model, error=str(e)
            )

    results = await asyncio.gather(*[_run_model(m) for m in models])
    projects.touch_project(project_id)
    return {"turn": turn, "results": results}
