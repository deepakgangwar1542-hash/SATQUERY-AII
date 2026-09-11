"""SatQuery AI backend entrypoint (§11.1, §19).

Run from the repo root:  uvicorn backend.main:app --port 8000
"""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import errors
from .api.routes_analysis import router as analysis_router
from .api.routes_change import router as change_router
from .api.routes_job import router as job_router
from .api.routes_query import router as query_router
from .api.routes_report import router as report_router
from .api.routes_spatial import router as spatial_router
from .api.routes_upload import router as upload_router
from .models import loaders
from .services import artifact_store, job_store

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(title="SatQuery AI", version="1.0.0",
              description="Autonomous multimodal geospatial intelligence API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"],
    allow_methods=["*"], allow_headers=["*"], allow_credentials=True,
)
errors.register_handlers(app)

API = "/api/v1"
app.include_router(upload_router, prefix=API)
app.include_router(query_router, prefix=API)
app.include_router(job_router, prefix=API)
app.include_router(change_router, prefix=API)
app.include_router(spatial_router, prefix=API)
app.include_router(analysis_router, prefix=API)
app.include_router(report_router, prefix=API)

artifact_store.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=str(artifact_store.ARTIFACTS_DIR)),
          name="artifacts")

# --- minimal Prometheus-compatible metrics (§7.4 P1) ------------------------
_METRICS = {"requests_total": 0, "errors_total": 0, "latency_sum_ms": 0.0}


@app.middleware("http")
async def _metrics_middleware(request: Request, call_next):
    started = time.monotonic()
    try:
        response = await call_next(request)
        return response
    finally:
        _METRICS["requests_total"] += 1
        _METRICS["latency_sum_ms"] += (time.monotonic() - started) * 1000
        if request.url.path.startswith(API) and request.method == "POST":
            pass


@app.get(API + "/health")
def health():
    caps = loaders.capabilities()
    return {"status": "ok", "version": app.version,
            "gpu_available": caps["gpu_available"],
            "capabilities": caps}


@app.get(API + "/metrics")
def metrics():
    lines = [
        "# HELP satquery_requests_total Total API requests.",
        "# TYPE satquery_requests_total counter",
        f"satquery_requests_total {_METRICS['requests_total']}",
        "# HELP satquery_latency_avg_ms Average request latency.",
        "# TYPE satquery_latency_avg_ms gauge",
        f"satquery_latency_avg_ms "
        f"{_METRICS['latency_sum_ms'] / max(1, _METRICS['requests_total']):.1f}",
        "# HELP satquery_jobs_total Jobs by status.",
        "# TYPE satquery_jobs_total gauge",
    ]
    jobs_dir = job_store.JOBS_DIR
    counts: dict[str, int] = {}
    if jobs_dir.exists():
        for p in jobs_dir.glob("*.json"):
            try:
                s = p.read_text(encoding="utf-8")
                status = ("completed" if '"status": "completed"' in s
                          else "failed" if '"status": "failed"' in s
                          else "other")
                counts[status] = counts.get(status, 0) + 1
            except OSError:
                continue
    for status, n in counts.items():
        lines.append(f'satquery_jobs_total{{status="{status}"}} {n}')
    return {"metrics": "\n".join(lines)}


@app.on_event("startup")
def _startup_log():
    caps = loaders.capabilities()
    mode = "GPU" if caps["gpu_available"] else "CPU"
    loaded = [k for k in ("perception_vlm", "grounding_dino",
                          "change_detector", "embedding_model") if caps[k]]
    logging.getLogger("satquery").info(
        "startup: %s mode; models loaded: %s; fallbacks active for: %s",
        mode, loaded or "none",
        [k for k in ("perception_vlm", "grounding_dino", "change_detector",
                     "embedding_model") if k not in loaded])
