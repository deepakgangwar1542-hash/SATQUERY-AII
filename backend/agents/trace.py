"""Execution-trace helpers — §12.5 event schema, FR-11."""
from __future__ import annotations

import time
from contextlib import contextmanager


@contextmanager
def traced(job_id: str | None, agent: str, action: str, sink: list | None = None,
           store=None):
    """Context manager that records a §12.5 trace event with duration."""
    started = time.monotonic()
    status, detail = "ok", None
    try:
        yield
    except Exception as exc:
        status, detail = "failed", str(exc)[:500]
        raise
    finally:
        event = {
            "agent": agent,
            "action": action,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "status": status,
        }
        if detail:
            event["detail"] = detail
        if sink is not None:
            sink.append(event)
        if store and job_id:
            store(job_id, event)
