"""Persisted job/result storage — implements PRD §7.2/§7.4 (FR-11).

Jobs are stored as one JSON file per job under <data_dir>/jobs/ so the trace
and result survive process restarts and report exports work from persisted
data alone (FR-18 AC1). An in-memory event log feeds the SSE stream.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.RLock()  # reentrant: mutators call get_job() while held

DATA_DIR = Path(os.environ.get("SATQUERY_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
JOBS_DIR = DATA_DIR / "jobs"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def new_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:6]}"


def new_asset_id() -> str:
    return f"asset_{uuid.uuid4().hex[:6]}"


def create_job(query: dict) -> dict:
    job = {
        "job_id": new_job_id(),
        "status": "queued",
        "created_at": _now_iso(),
        "request": query,
        "agents": [],
        "progress_pct": 0,
        "result": None,
        "error": None,
        "execution_trace": [],
        "events": [],  # in-memory ring for SSE
    }
    with _LOCK:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        _persist(job)
        _EVENTS[job["job_id"]] = job["events"]
    _emit(job["job_id"], {"status": "queued"})
    return job


def _persist(job: dict) -> None:
    path = JOBS_DIR / f"{job['job_id']}.json"
    snapshot = {k: v for k, v in job.items() if k != "events"}
    # atomic write: readers never observe a half-written file
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def get_job(job_id: str) -> dict | None:
    path = JOBS_DIR / f"{job_id}.json"
    if not path.exists():
        return None
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None  # transient read racing an atomic replace; caller retries
    with _LOCK:
        job["events"] = _EVENTS.get(job_id, [])
    return job


_EVENTS: dict[str, list] = {}


def _emit(job_id: str, event: dict) -> None:
    events = _EVENTS.get(job_id)
    if events is not None:
        events.append({"ts": _now_iso(), **event})


def set_status(job_id: str, status: str, progress: int | None = None,
               error: str | None = None) -> None:
    with _LOCK:
        job = get_job(job_id)
        if job is None:
            return
        job["status"] = status
        if progress is not None:
            job["progress_pct"] = progress
        if error is not None:
            job["error"] = error
        _persist(job)
    _emit(job_id, {"status": status, "progress_pct": job.get("progress_pct")})


def set_agent_status(job_id: str, agent: str, status: str) -> None:
    """agent status: pending|running|completed|failed|skipped"""
    with _LOCK:
        job = get_job(job_id)
        if job is None:
            return
        for entry in job["agents"]:
            if entry["name"] == agent:
                entry["status"] = status
                break
        else:
            job["agents"].append({"name": agent, "status": status})
        _persist(job)
    _emit(job_id, {"agent": agent, "agent_status": status})


def append_trace(job_id: str, event: dict) -> None:
    """Append a §12.5 trace event and persist it (FR-11 AC1, §7.4 P0)."""
    with _LOCK:
        job = get_job(job_id)
        if job is None:
            return
        job["execution_trace"].append({"timestamp": _now_iso(), **event})
        _persist(job)


def set_result(job_id: str, result: dict) -> None:
    with _LOCK:
        job = get_job(job_id)
        if job is None:
            return
        job["result"] = result
        job["status"] = "completed"
        job["progress_pct"] = 100
        _persist(job)
    _emit(job_id, {"status": "completed"})


def fail_job(job_id: str, error: str) -> None:
    with _LOCK:
        job = get_job(job_id)
        if job is None:
            return
        job["status"] = "failed"
        job["error"] = error
        _persist(job)
    _emit(job_id, {"status": "failed", "error": error})


def emit_event(job_id: str, event_type: str, data: dict | None = None) -> None:
    """Emits typed investigation events for real-time SSE streaming (Section 21)."""
    payload = {"event": event_type, "data": data or {}}
    with _LOCK:
        _emit(job_id, payload)


def get_events(job_id: str) -> list[dict]:
    """Live event log for the SSE stream (in-memory; trace is the durable record)."""
    with _LOCK:
        return list(_EVENTS.get(job_id, []))



def json_dumps(obj) -> str:
    return json.dumps(obj, default=str)

