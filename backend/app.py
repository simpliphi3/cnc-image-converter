from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import (
    Body,
    FastAPI,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import json

from backend import config, presets
from backend.airelief import aspire_companion, relief_gen
from backend.depth import depth_anything
from backend.image_gen import router as image_router
from backend.mockup import render as mockup_render
from backend.stl import heightmap_to_stl as stl_mod
from backend.store import files, projects
from backend.system import folder_picker
from backend.vectorize import potrace_wrap

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("cnc")

config.ensure_dirs()
config.load_runtime_config()

app = FastAPI(title="CNC Image Converter", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "data_dir": str(config.DATA_DIR)}


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    cfg = config.load_runtime_config()
    return {
        "aspire_folder": cfg.aspire_folder,
        "default_units": cfg.default_units,
        "last_used_models": cfg.last_used_models,
        "has_openai_key": bool(config.openai_key()),
        "has_google_key": bool(config.google_key()),
        "depth": depth_anything.device_info(),
    }


class SettingsPatch(BaseModel):
    aspire_folder: str | None = None
    default_units: str | None = None
    last_used_models: list[str] | None = None


@app.patch("/api/settings")
def patch_settings(body: SettingsPatch) -> dict[str, Any]:
    cfg = config.load_runtime_config()
    if body.aspire_folder is not None:
        cfg.aspire_folder = body.aspire_folder or None
    if body.default_units in ("mm", "in"):
        cfg.default_units = body.default_units  # type: ignore[assignment]
    if body.last_used_models is not None:
        cfg.last_used_models = body.last_used_models
    config.save_runtime_config(cfg)
    return get_settings()


@app.get("/api/projects")
def api_list_projects() -> list[dict[str, Any]]:
    return projects.list_projects()


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@app.post("/api/projects")
def api_create_project(body: ProjectCreate) -> dict[str, Any]:
    return projects.create_project(body.name.strip())


def _enrich_pair_ids(project_id: str, images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach paired_image_id to ai_relief / ai_heightmap images by reading the
    per-image notes sidecar so the frontend can offer a 'Switch' link."""
    if not images:
        return images
    proj_dir = files.project_dir(project_id)
    out: list[dict[str, Any]] = []
    for img in images:
        if img.get("role") in ("ai_relief", "ai_heightmap"):
            sidecar = proj_dir / f".airelief_notes_{img['id']}.json"
            paired = None
            if sidecar.exists():
                try:
                    paired = json.loads(sidecar.read_text()).get("paired_image_id")
                except Exception:
                    paired = None
            img = {**img, "paired_image_id": paired}
        out.append(img)
    return out


@app.get("/api/projects/{project_id}")
def api_get_project(project_id: str) -> dict[str, Any]:
    p = projects.get_project(project_id)
    if not p:
        raise HTTPException(404, "project not found")
    imgs = files.list_project_images(project_id)
    return {
        "project": p,
        "turns": projects.list_turns(project_id),
        "images": _enrich_pair_ids(project_id, imgs),
        "exports": projects.list_exports(project_id),
    }


class ProjectPatch(BaseModel):
    name: str | None = None


@app.patch("/api/projects/{project_id}")
def api_patch_project(project_id: str, body: ProjectPatch) -> dict[str, Any]:
    if body.name is not None:
        projects.rename_project(project_id, body.name.strip())
    p = projects.get_project(project_id)
    if not p:
        raise HTTPException(404, "project not found")
    return p


@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: str) -> dict[str, Any]:
    projects.delete_project(project_id)
    return {"ok": True}


@app.post("/api/projects/{project_id}/references")
async def api_upload_reference(
    project_id: str, file: UploadFile = File(...)
) -> dict[str, Any]:
    if not projects.get_project(project_id):
        raise HTTPException(404, "project not found")
    data = await file.read()
    ext = "png"
    if file.filename and "." in file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()[:5] or "png"
    return files.save_image_bytes(
        project_id, data, role="reference", extension=ext
    )


class GenerateBody(BaseModel):
    prompt: str = Field(min_length=1)
    reference_image_ids: list[str] = []
    models: list[str] = ["openai", "gemini"]
    use_session_memory: bool = True


@app.post("/api/projects/{project_id}/generate")
async def api_generate(project_id: str, body: GenerateBody) -> dict[str, Any]:
    if not projects.get_project(project_id):
        raise HTTPException(404, "project not found")
    return await image_router.generate_for_turn(
        project_id,
        prompt=body.prompt,
        user_reference_image_ids=body.reference_image_ids,
        models=body.models,
        use_session_memory=body.use_session_memory,
    )


@app.get("/api/images/{image_id}/file")
def api_image_file(image_id: str) -> FileResponse:
    img = files.get_image(image_id)
    if not img or not img.get("filename"):
        raise HTTPException(404, "image not found")
    p = files.image_path(img["project_id"], img["filename"])
    if not p.exists():
        raise HTTPException(404, "image file missing")
    return FileResponse(p)


async def _depth_for_image(
    image_id: str, mode: depth_anything.DepthMode = "ai"
) -> tuple[np.ndarray, dict[str, Any]]:
    """Run (or load cached) depth map for a stored image, by mode.

    Cache is keyed by (image_id, mode) so flipping modes doesn't re-run an
    expensive AI inference, and each mode's result is independently cached.
    """
    img = files.get_image(image_id)
    if not img:
        raise HTTPException(404, "image not found")
    project_id = img["project_id"]
    # v2: depth pipeline now dithers 8-bit sources to break contour terracing.
    # The version tag invalidates pre-dither caches so the fix takes effect.
    cache = files.project_dir(project_id) / f".depth_v2_{mode}_{image_id}.npy"
    if cache.exists():
        try:
            return np.load(cache), img
        except Exception:
            cache.unlink(missing_ok=True)
    src = files.image_path(project_id, img["filename"])
    depth = await depth_anything.depth_by_mode(src.read_bytes(), mode)
    try:
        np.save(cache, depth.astype(np.float32))
    except Exception:
        pass
    return depth, img


class DepthPreviewBody(BaseModel):
    image_id: str
    mode: depth_anything.DepthMode = "ai"


@app.post("/api/depth/preview")
async def api_depth_preview(body: DepthPreviewBody) -> Response:
    depth01, _ = await _depth_for_image(body.image_id, body.mode)
    png = depth_anything.depth_to_png_8bit_preview(depth01)
    return Response(content=png, media_type="image/png")


class ConvertBody(BaseModel):
    image_id: str
    params: dict[str, Any] = {}
    output_basename: str | None = None
    depth_mode: depth_anything.DepthMode = "ai"


@app.post("/api/convert")
async def api_convert(body: ConvertBody) -> dict[str, Any]:
    depth01, img = await _depth_for_image(body.image_id, body.depth_mode)
    project_id = img["project_id"]

    p_kwargs = {k: v for k, v in body.params.items() if v is not None}
    params = stl_mod.StlParams(**p_kwargs)

    result = await stl_mod.heightmap_to_stl(depth01, params)

    base = body.output_basename or f"carve_{body.image_id[:8]}"
    base = "".join(c for c in base if c.isalnum() or c in ("-", "_")).strip("_-") or "carve"

    proj_dir = files.project_dir(project_id)
    stl_path = proj_dir / f"{base}.stl"
    depth_png_path = proj_dir / f"{base}_depth.png"

    stl_mod.write_stl(result, stl_path)
    depth_png_path.write_bytes(depth_anything.depth_to_png_16bit(result.processed_depth))

    cfg = config.load_runtime_config()
    stl_export = files.record_export(
        project_id,
        source_image_id=body.image_id,
        kind="stl",
        params=params.__dict__,
        src_path=stl_path,
        aspire_folder=cfg.aspire_folder,
    )
    depth_export = files.record_export(
        project_id,
        source_image_id=body.image_id,
        kind="depth_png",
        params=params.__dict__,
        src_path=depth_png_path,
        aspire_folder=cfg.aspire_folder,
    )
    aspire_steps_export = None
    if img.get("role") in ("ai_relief", "ai_heightmap"):
        notes_path = proj_dir / f".airelief_notes_{body.image_id}.json"
        notes: dict[str, Any] = {}
        if notes_path.exists():
            try:
                notes = json.loads(notes_path.read_text())
            except Exception:
                pass
        # ai_heightmap = shadowless subject-only source → companion tells the
        # user to add frame/sunburst/text in Aspire.
        # ai_relief    = full lit mockup source → companion says everything is
        # already carved into the STL, don't double-add.
        subject_only = img.get("role") == "ai_heightmap"
        md_path = proj_dir / f"{base}_aspire_steps.md"
        aspire_companion.write_steps(
            md_path,
            stl_basename=base,
            stl_params=params.__dict__,
            has_text=bool(notes.get("text")),
            has_sunburst=bool(notes.get("sunburst_background", True)),
            has_frame=(notes.get("frame", "simple") != "none"),
            text=notes.get("text", ""),
            subject_only=subject_only,
        )
        aspire_steps_export = files.record_export(
            project_id,
            source_image_id=body.image_id,
            kind="aspire_steps",
            params={},
            src_path=md_path,
            aspire_folder=cfg.aspire_folder,
        )

    projects.touch_project(project_id)
    out: dict[str, Any] = {"stl": stl_export, "depth_png": depth_export}
    if aspire_steps_export is not None:
        out["aspire_steps"] = aspire_steps_export
    return out


class VectorizeBody(BaseModel):
    image_id: str
    params: dict[str, Any] = {}
    output_basename: str | None = None
    preview_only: bool = False


@app.post("/api/vectorize")
async def api_vectorize(body: VectorizeBody) -> dict[str, Any]:
    img = files.get_image(body.image_id)
    if not img:
        raise HTTPException(404, "image not found")
    project_id = img["project_id"]
    src_path = files.image_path(project_id, img["filename"])
    image_bytes = src_path.read_bytes()

    p_kwargs = {k: v for k, v in body.params.items() if v is not None}
    params = potrace_wrap.VectorizeParams(**p_kwargs)
    svg, w, h = await potrace_wrap.vectorize(image_bytes, params)

    if body.preview_only:
        return {"svg": svg, "width": w, "height": h}

    base = body.output_basename or f"vector_{body.image_id[:8]}"
    base = "".join(c for c in base if c.isalnum() or c in ("-", "_")).strip("_-") or "vector"
    out_path = files.project_dir(project_id) / f"{base}.svg"
    potrace_wrap.write_svg(svg, out_path)
    cfg = config.load_runtime_config()
    rec = files.record_export(
        project_id,
        source_image_id=body.image_id,
        kind="svg",
        params=params.__dict__,
        src_path=out_path,
        aspire_folder=cfg.aspire_folder,
    )
    return {"svg_export": rec, "svg": svg, "width": w, "height": h}


@app.get("/api/exports/{export_id}/file")
def api_export_file(export_id: str) -> FileResponse:
    from backend.store import db

    c = db.conn()
    row = c.execute("SELECT * FROM exports WHERE id=?", (export_id,)).fetchone()
    if not row:
        raise HTTPException(404, "export not found")
    p = files.project_dir(row["project_id"]) / row["filename"]
    if not p.exists():
        raise HTTPException(404, "export file missing")
    return FileResponse(p, filename=row["filename"])


# --- Presets ---


@app.get("/api/presets/dimensions")
def api_dimension_presets() -> list[dict[str, Any]]:
    return [dict(p) for p in presets.DIMENSION_PRESETS]


# --- Native folder picker (Windows Tkinter dialog on the host) ---


class PickFolderBody(BaseModel):
    initial_dir: str | None = None


@app.post("/api/system/pick_folder")
async def api_pick_folder(
    body: PickFolderBody = Body(default_factory=PickFolderBody),
) -> dict[str, Any]:
    try:
        path = await folder_picker.pick_folder(body.initial_dir)
    except Exception as e:
        log.exception("folder picker failed")
        raise HTTPException(500, f"folder picker failed: {e}")
    return {"path": path}


# --- AI bas-relief render (the STL source for portraits / signs / plaques) ---


class AiReliefBody(BaseModel):
    image_id: str
    style: str = "portrait"
    palette: str = "walnut"
    frame: str = "simple"
    text: str = ""
    sunburst_background: bool = True
    additional_notes: str = ""
    provider: str = "gemini"


@app.post("/api/airelief")
async def api_airelief(body: AiReliefBody) -> dict[str, Any]:
    img = files.get_image(body.image_id)
    if not img:
        raise HTTPException(404, "image not found")
    project_id = img["project_id"]
    src_path = files.image_path(project_id, img["filename"])
    if not src_path.exists():
        raise HTTPException(404, "source image file missing")

    req = relief_gen.AiReliefRequest(
        style=body.style,  # type: ignore[arg-type]
        palette=body.palette,
        frame=body.frame,  # type: ignore[arg-type]
        text=body.text.strip(),
        sunburst_background=body.sunburst_background,
        additional_notes=body.additional_notes.strip(),
        provider=body.provider,  # type: ignore[arg-type]
    )

    cache_dir = files.project_dir(project_id)
    cache_meta = cache_dir / f".airelief_{relief_gen.cache_key(body.image_id, req)}.json"
    if cache_meta.exists():
        try:
            meta = json.loads(cache_meta.read_text())
            existing = files.get_image(meta["image_id"])
            if existing:
                hm_id = meta.get("heightmap_image_id")
                return {
                    **existing,
                    "heightmap_image_id": hm_id,
                    "paired_image_id": hm_id,
                }
        except Exception:
            cache_meta.unlink(missing_ok=True)

    src_bytes = src_path.read_bytes()
    # Generate the lit render (customer mockup) and the shadowless height map
    # (STL carve source) in parallel so total latency stays close to one call.
    # The render is required; the height map is best-effort — if it fails we
    # still return the render and the carve falls back to the render as before.
    render_res, hm_res = await asyncio.gather(
        relief_gen.generate_relief(src_bytes, req),
        relief_gen.generate_heightmap(src_bytes, req),
        return_exceptions=True,
    )
    if isinstance(render_res, BaseException):
        log.exception("AI relief generation failed", exc_info=render_res)
        raise HTTPException(502, f"AI relief generation failed: {render_res}")

    saved = files.save_image_bytes(
        project_id,
        render_res,
        role="ai_relief",
        model=req.provider,
        extension="png",
    )

    heightmap_image_id: str | None = None
    if isinstance(hm_res, BaseException):
        log.warning("AI height map generation failed; carve will use render: %s", hm_res)
    else:
        hm_saved = files.save_image_bytes(
            project_id,
            hm_res,
            role="ai_heightmap",
            model=req.provider,
            extension="png",
        )
        heightmap_image_id = hm_saved["id"]

    # Base notes shared by both sidecars.
    base_notes = {
        "style": req.style,
        "palette": req.palette,
        "frame": req.frame,
        "text": req.text,
        "sunburst_background": req.sunburst_background,
        "additional_notes": req.additional_notes,
        "provider": req.provider,
        "source_image_id": body.image_id,
        "prompt": relief_gen.build_prompt(req),
        "heightmap_image_id": heightmap_image_id,
    }
    # Sidecar for the lit-render (ai_relief) image — paired_image_id points at
    # the shadowless heightmap so the Convert page can offer a Switch link.
    relief_notes = {**base_notes, "paired_image_id": heightmap_image_id}
    (cache_dir / f".airelief_notes_{saved['id']}.json").write_text(
        json.dumps(relief_notes, indent=2)
    )
    # And the mirror sidecar for the heightmap — paired_image_id points back
    # at the lit render.
    if heightmap_image_id:
        hm_notes = {**base_notes, "paired_image_id": saved["id"]}
        (cache_dir / f".airelief_notes_{heightmap_image_id}.json").write_text(
            json.dumps(hm_notes, indent=2)
        )
    cache_meta.write_text(
        json.dumps({"image_id": saved["id"], "heightmap_image_id": heightmap_image_id})
    )

    projects.touch_project(project_id, cover_image_id=saved["id"])
    return {**saved, "heightmap_image_id": heightmap_image_id}


# --- Mockup on wood ---


class MockupBody(BaseModel):
    image_id: str
    palette: str = "walnut"
    wood_seed: int = 7
    relief_scale: float = 60.0
    ambient: float = 0.35
    ao_strength: float = 0.35
    light_x: float = -0.55
    light_y: float = -0.55
    light_z: float = 0.62
    smoothing: float = 1.2
    invert: bool = False
    background_threshold: float = 0.0
    max_dim_px: int = 900
    depth_mode: depth_anything.DepthMode = "ai"


@app.post("/api/mockup")
async def api_mockup(body: MockupBody) -> Response:
    depth01, _ = await _depth_for_image(body.image_id, body.depth_mode)
    params = mockup_render.MockupParams(
        palette=body.palette,  # type: ignore[arg-type]
        wood_seed=body.wood_seed,
        relief_scale=body.relief_scale,
        ambient=body.ambient,
        ao_strength=body.ao_strength,
        light_x=body.light_x,
        light_y=body.light_y,
        light_z=body.light_z,
        smoothing=body.smoothing,
        invert=body.invert,
        background_threshold=body.background_threshold,
        max_dim_px=body.max_dim_px,
    )
    jpg = await mockup_render.render(depth01, params)
    return Response(
        content=jpg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


# --- Static frontend ---
_FRONTEND_ROOT = Path(__file__).resolve().parent.parent / "frontend"
_FRONTEND_BUILD: Path | None = None
for _candidate in (_FRONTEND_ROOT / "dist", _FRONTEND_ROOT / "out"):
    if _candidate.exists():
        _FRONTEND_BUILD = _candidate
        break

if _FRONTEND_BUILD is not None:
    app.mount(
        "/", StaticFiles(directory=str(_FRONTEND_BUILD), html=True), name="frontend"
    )
else:

    @app.get("/")
    def _placeholder() -> JSONResponse:
        return JSONResponse(
            {
                "message": (
                    "Frontend has not been built yet. Run `npm install && npm run build` "
                    "inside `frontend/` (the setup script does this for you)."
                ),
                "frontend_root": str(_FRONTEND_ROOT),
            },
            status_code=200,
        )


def main() -> None:
    import uvicorn

    uvicorn.run(
        "backend.app:app",
        host=config.host(),
        port=config.port(),
        reload=False,
    )


if __name__ == "__main__":
    main()
