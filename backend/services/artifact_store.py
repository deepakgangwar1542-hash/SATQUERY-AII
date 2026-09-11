"""Artifact storage — files produced by jobs, served at /artifacts/{job_id}/name."""
from __future__ import annotations

import shutil
from pathlib import Path

from .job_store import DATA_DIR

ARTIFACTS_DIR = DATA_DIR / "artifacts"


def job_artifact_dir(job_id: str) -> Path:
    d = ARTIFACTS_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_file(job_id: str, source_path: str | Path, name: str | None = None) -> str:
    """Copy a produced file into the artifact store; returns its public URL."""
    src = Path(source_path)
    dest = job_artifact_dir(job_id) / (name or src.name)
    shutil.copyfile(src, dest)
    return f"/artifacts/{job_id}/{dest.name}"


def save_bytes(job_id: str, data: bytes, name: str) -> str:
    dest = job_artifact_dir(job_id) / name
    dest.write_bytes(data)
    return f"/artifacts/{job_id}/{name}"


def save_json(job_id: str, payload: dict, name: str) -> str:
    import json
    dest = job_artifact_dir(job_id) / name
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return f"/artifacts/{job_id}/{name}"
