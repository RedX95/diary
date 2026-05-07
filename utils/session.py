import json
import os
from typing import Any


_SESSION_PATH: str | None = None


def init_session_storage(base_dir: str):
    global _SESSION_PATH
    _SESSION_PATH = os.path.join(base_dir, "session.json")


def load_session() -> dict[str, Any]:
    if not _SESSION_PATH:
        raise RuntimeError("Session storage not initialized")
    if not os.path.exists(_SESSION_PATH):
        return {}
    try:
        with open(_SESSION_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def save_session(data: dict[str, Any]):
    if not _SESSION_PATH:
        raise RuntimeError("Session storage not initialized")
    with open(_SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clear_session():
    if not _SESSION_PATH:
        raise RuntimeError("Session storage not initialized")
    try:
        os.remove(_SESSION_PATH)
    except FileNotFoundError:
        pass
