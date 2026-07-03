from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


def _default_data_dir() -> Path:
    override = os.environ.get("CNC_DATA_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cnc-image-converter"


DATA_DIR: Path = _default_data_dir()
FILES_DIR: Path = DATA_DIR / "files"
DB_PATH: Path = DATA_DIR / "projects.db"
CONFIG_JSON: Path = DATA_DIR / "config.json"
HF_CACHE: Path = DATA_DIR / "hf_cache"


class RuntimeConfig(BaseModel):
    aspire_folder: str | None = None
    default_units: Literal["mm", "in"] = "in"
    last_used_models: list[str] = ["openai", "gemini"]


def ensure_dirs() -> None:
    for d in (DATA_DIR, FILES_DIR, HF_CACHE):
        d.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(HF_CACHE))


def load_runtime_config() -> RuntimeConfig:
    ensure_dirs()
    if CONFIG_JSON.exists():
        try:
            return RuntimeConfig.model_validate_json(CONFIG_JSON.read_text())
        except Exception:
            pass
    cfg = RuntimeConfig(default_units=os.environ.get("CNC_DEFAULT_UNITS", "in"))  # type: ignore[arg-type]
    env_aspire = os.environ.get("CNC_ASPIRE_FOLDER")
    if env_aspire:
        cfg.aspire_folder = env_aspire
    save_runtime_config(cfg)
    return cfg


def save_runtime_config(cfg: RuntimeConfig) -> None:
    ensure_dirs()
    CONFIG_JSON.write_text(json.dumps(cfg.model_dump(), indent=2))


def host() -> str:
    return os.environ.get("CNC_HOST", "127.0.0.1")


def port() -> int:
    return int(os.environ.get("CNC_PORT", "7777"))


def depth_model_id() -> str:
    return os.environ.get(
        "CNC_DEPTH_MODEL", "depth-anything/Depth-Anything-V2-Small-hf"
    )


def openai_key() -> str | None:
    v = os.environ.get("OPENAI_API_KEY", "").strip()
    return v or None


def google_key() -> str | None:
    v = os.environ.get("GOOGLE_API_KEY", "").strip()
    return v or None
