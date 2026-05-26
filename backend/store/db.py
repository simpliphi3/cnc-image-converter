from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from backend import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    cover_image_id TEXT
);

CREATE TABLE IF NOT EXISTS turns (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    idx         INTEGER NOT NULL,
    prompt      TEXT NOT NULL,
    ref_image_ids TEXT NOT NULL DEFAULT '[]',
    models      TEXT NOT NULL DEFAULT '[]',
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS images (
    id          TEXT PRIMARY KEY,
    project_id  TEXT REFERENCES projects(id) ON DELETE CASCADE,
    turn_id     TEXT REFERENCES turns(id) ON DELETE SET NULL,
    model       TEXT,
    role        TEXT NOT NULL,  -- 'reference' | 'generated' | 'depth' | 'export'
    filename    TEXT NOT NULL,
    width       INTEGER,
    height      INTEGER,
    error       TEXT,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS exports (
    id          TEXT PRIMARY KEY,
    project_id  TEXT REFERENCES projects(id) ON DELETE CASCADE,
    source_image_id TEXT REFERENCES images(id),
    kind        TEXT NOT NULL,   -- 'stl' | 'svg' | 'depth_png'
    params      TEXT NOT NULL,
    filename    TEXT NOT NULL,
    aspire_copy_path TEXT,
    created_at  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_turns_project ON turns(project_id, idx);
CREATE INDEX IF NOT EXISTS idx_images_project ON images(project_id);
CREATE INDEX IF NOT EXISTS idx_images_turn ON images(turn_id);
CREATE INDEX IF NOT EXISTS idx_exports_project ON exports(project_id);
"""


def _connect() -> sqlite3.Connection:
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


_conn: sqlite3.Connection | None = None


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _connect()
        _conn.executescript(SCHEMA)
        _conn.commit()
    return _conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    c = conn()
    with _lock:
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> float:
    return time.time()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None
