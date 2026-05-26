from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Literal

from PIL import Image

from backend import config
from backend.store import db

ImageRole = Literal["reference", "generated", "depth", "export"]


def project_dir(project_id: str) -> Path:
    p = config.FILES_DIR / project_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_image_bytes(
    project_id: str,
    image_bytes: bytes,
    *,
    role: ImageRole,
    turn_id: str | None = None,
    model: str | None = None,
    extension: str = "png",
) -> dict[str, Any]:
    image_id = db.new_id()
    filename = f"{image_id}.{extension}"
    path = project_dir(project_id) / filename
    path.write_bytes(image_bytes)

    width = height = None
    try:
        with Image.open(path) as im:
            width, height = im.size
    except Exception:
        pass

    with db.tx() as c:
        c.execute(
            "INSERT INTO images (id, project_id, turn_id, model, role, filename, width, height, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                image_id,
                project_id,
                turn_id,
                model,
                role,
                filename,
                width,
                height,
                db.now(),
            ),
        )
    return {
        "id": image_id,
        "project_id": project_id,
        "turn_id": turn_id,
        "model": model,
        "role": role,
        "filename": filename,
        "width": width,
        "height": height,
    }


def record_image_error(
    project_id: str,
    *,
    turn_id: str | None,
    model: str,
    error: str,
) -> dict[str, Any]:
    image_id = db.new_id()
    with db.tx() as c:
        c.execute(
            "INSERT INTO images (id, project_id, turn_id, model, role, filename, error, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (image_id, project_id, turn_id, model, "generated", "", error, db.now()),
        )
    return {
        "id": image_id,
        "project_id": project_id,
        "turn_id": turn_id,
        "model": model,
        "role": "generated",
        "error": error,
    }


def image_path(project_id: str, filename: str) -> Path:
    return project_dir(project_id) / filename


def get_image(image_id: str) -> dict[str, Any] | None:
    c = db.conn()
    row = c.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
    return db.row_to_dict(row)


def list_project_images(project_id: str) -> list[dict[str, Any]]:
    c = db.conn()
    rows = c.execute(
        "SELECT * FROM images WHERE project_id = ? ORDER BY created_at ASC",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def record_export(
    project_id: str,
    *,
    source_image_id: str | None,
    kind: Literal["stl", "svg", "depth_png"],
    params: dict[str, Any],
    src_path: Path,
    aspire_folder: str | None,
) -> dict[str, Any]:
    export_id = db.new_id()
    filename = src_path.name
    aspire_copy_path = None
    if aspire_folder:
        try:
            dest_dir = Path(aspire_folder).expanduser()
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / filename
            shutil.copy2(src_path, dest)
            aspire_copy_path = str(dest)
        except Exception as e:
            aspire_copy_path = f"ERROR: {e}"
    with db.tx() as c:
        c.execute(
            "INSERT INTO exports (id, project_id, source_image_id, kind, params, filename, aspire_copy_path, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                export_id,
                project_id,
                source_image_id,
                kind,
                json.dumps(params),
                filename,
                aspire_copy_path,
                db.now(),
            ),
        )
    return {
        "id": export_id,
        "kind": kind,
        "filename": filename,
        "params": params,
        "aspire_copy_path": aspire_copy_path,
        "src_path": str(src_path),
    }
