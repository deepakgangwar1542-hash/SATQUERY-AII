"""Asset registry — maps uploaded asset_ids to stored file paths.

Uploads live under <data_dir>/uploads/ with an index.json sidecar recording
the §9.3.1 validation report. resolve_asset_paths() is the single lookup the
orchestrator uses.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from ..services.job_store import DATA_DIR

UPLOADS_DIR = DATA_DIR / "uploads"
_INDEX = UPLOADS_DIR / "index.json"
_LOCK = threading.Lock()


def register_asset(asset_id: str, path: str, report: dict, meta: dict) -> None:
    with _LOCK:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        index = {}
        if _INDEX.exists():
            index = json.loads(_INDEX.read_text(encoding="utf-8"))
        index[asset_id] = {"path": str(path), "validation": report, **meta}
        _INDEX.write_text(json.dumps(index, indent=2), encoding="utf-8")


def get_asset(asset_id: str) -> dict | None:
    if not _INDEX.exists():
        return None
    index = json.loads(_INDEX.read_text(encoding="utf-8"))
    return index.get(asset_id)


def resolve_asset_paths(assets: list[dict]) -> dict[str, str]:
    """{asset_id: filesystem path} for assets that exist on disk."""
    out: dict[str, str] = {}
    for a in assets:
        aid = a.get("asset_id")
        rec = get_asset(aid) if aid else None
        if rec and os.path.exists(rec["path"]):
            out[aid] = rec["path"]
    return out
