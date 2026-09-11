"""GET /api/v1/job/{id} + SSE stream (§7.1 P1, §9.1)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from ..services import job_store
from .errors import problem

router = APIRouter(tags=["job"])


@router.get("/job/{job_id}")
def job_status(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        return problem(404, "Not Found", f"unknown job {job_id}")
    return {"job_id": job_id, "status": job["status"], "agents": job["agents"],
            "progress_pct": job["progress_pct"], "error": job["error"]}


@router.get("/job/{job_id}/stream")
async def job_stream(job_id: str, request: Request):
    job = job_store.get_job(job_id)
    if job is None:
        return problem(404, "Not Found", f"unknown job {job_id}")

    async def gen():
        sent = 0
        while True:
            if await request.is_disconnected():
                break
            events = job_store.get_events(job_id)
            while sent < len(events):
                yield {"data": job_store.json_dumps(events[sent])}
                sent += 1
            job = job_store.get_job(job_id)
            if job and job["status"] in ("completed", "failed") and sent >= len(events):
                yield {"event": "end", "data": '{"status": "%s"}' % job["status"]}
                break
            await asyncio.sleep(0.4)

    return EventSourceResponse(gen())
