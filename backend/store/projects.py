from __future__ import annotations

import json
from typing import Any

from backend.store import db


def create_project(name: str) -> dict[str, Any]:
    pid = db.new_id()
    ts = db.now()
    with db.tx() as c:
        c.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?,?,?,?)",
            (pid, name, ts, ts),
        )
    return {"id": pid, "name": name, "created_at": ts, "updated_at": ts}


def list_projects() -> list[dict[str, Any]]:
    c = db.conn()
    rows = c.execute(
        "SELECT p.*, "
        " (SELECT filename FROM images i WHERE i.id = p.cover_image_id) AS cover_filename "
        "FROM projects p ORDER BY p.updated_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_project(project_id: str) -> dict[str, Any] | None:
    c = db.conn()
    row = c.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return db.row_to_dict(row)


def rename_project(project_id: str, name: str) -> None:
    with db.tx() as c:
        c.execute(
            "UPDATE projects SET name=?, updated_at=? WHERE id=?",
            (name, db.now(), project_id),
        )


def delete_project(project_id: str) -> None:
    with db.tx() as c:
        c.execute("DELETE FROM projects WHERE id=?", (project_id,))


def touch_project(project_id: str, cover_image_id: str | None = None) -> None:
    with db.tx() as c:
        if cover_image_id is not None:
            c.execute(
                "UPDATE projects SET updated_at=?, cover_image_id=? WHERE id=?",
                (db.now(), cover_image_id, project_id),
            )
        else:
            c.execute(
                "UPDATE projects SET updated_at=? WHERE id=?",
                (db.now(), project_id),
            )


def add_turn(
    project_id: str,
    *,
    prompt: str,
    ref_image_ids: list[str],
    models: list[str],
) -> dict[str, Any]:
    c = db.conn()
    row = c.execute(
        "SELECT COALESCE(MAX(idx), -1) + 1 AS next_idx FROM turns WHERE project_id=?",
        (project_id,),
    ).fetchone()
    next_idx = row["next_idx"]
    turn_id = db.new_id()
    with db.tx() as c2:
        c2.execute(
            "INSERT INTO turns (id, project_id, idx, prompt, ref_image_ids, models, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                turn_id,
                project_id,
                next_idx,
                prompt,
                json.dumps(ref_image_ids),
                json.dumps(models),
                db.now(),
            ),
        )
    return {
        "id": turn_id,
        "project_id": project_id,
        "idx": next_idx,
        "prompt": prompt,
        "ref_image_ids": ref_image_ids,
        "models": models,
    }


def list_turns(project_id: str) -> list[dict[str, Any]]:
    c = db.conn()
    rows = c.execute(
        "SELECT * FROM turns WHERE project_id=? ORDER BY idx ASC", (project_id,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["ref_image_ids"] = json.loads(d.get("ref_image_ids") or "[]")
        d["models"] = json.loads(d.get("models") or "[]")
        result.append(d)
    return result


def last_generated_image_id(project_id: str, model: str) -> str | None:
    """Carry-forward memory: the most recent successful generation from a given model in this project."""
    c = db.conn()
    row = c.execute(
        "SELECT id FROM images "
        "WHERE project_id=? AND model=? AND role='generated' AND (error IS NULL OR error='') "
        "ORDER BY created_at DESC LIMIT 1",
        (project_id, model),
    ).fetchone()
    return row["id"] if row else None


def list_exports(project_id: str) -> list[dict[str, Any]]:
    c = db.conn()
    rows = c.execute(
        "SELECT * FROM exports WHERE project_id=? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["params"] = json.loads(d.get("params") or "{}")
        except Exception:
            pass
        out.append(d)
    return out
