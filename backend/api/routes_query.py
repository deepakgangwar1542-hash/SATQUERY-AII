"""POST /api/v1/query + GET /api/v1/result/{job_id} (FR-9, FR-11, §9.2)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..agents import orchestrator
from ..services import job_store
from .errors import problem

router = APIRouter(tags=["query"])


def _execute_job(job_id: str, request: dict) -> None:
    try:
        orchestrator.run_query(request)
    except Exception:
        pass  # already recorded on the job by run_query (§7.2)


@router.post("/query", status_code=202)
def submit_query(req: dict, background: BackgroundTasks):
    """Accepts the §9.1 query body (question, region, assets[]). Validated via
    the Pydantic model in schemas when used with typed clients; here we do the
    minimal structural checks and hand off to the orchestrator as a job."""
    question = req.get("question")
    assets = req.get("assets") or []
    if not question or len(str(question)) < 3:
        return problem(422, "Validation Error", "question must be >= 3 chars")
    if not assets:
        return problem(422, "Validation Error", "at least one asset is required")
    job = job_store.create_job({"question": question, "region": req.get("region"),
                                "assets": assets})
    job_store.set_agent_status(job["job_id"], "orchestrator", "pending")
    background.add_task(_execute_job, job["job_id"],
                        {**req, "job_id": job["job_id"]})
    return {"job_id": job["job_id"], "status": "queued"}


@router.post("/query/compile")
def compile_query_preview(req: dict):
    """Compiles natural language into an EarthQuery specification and investigation plan preview."""
    question = req.get("question")
    if not question or len(str(question)) < 3:
        return problem(422, "Validation Error", "question must be >= 3 chars")
    from ..agents.planner import build_investigation_plan
    plan_obj, spec, understanding = build_investigation_plan(
        query=question,
        assets=req.get("assets", []),
        spatial_scope=req.get("region"),
    )
    from ..services.earthquery.sensor_selector import AutonomousSensorSelector
    sensor_sel = AutonomousSensorSelector.select_sensors(spec, req.get("assets", []))
    return {
        "earthquery_spec": spec.model_dump(),
        "query_understanding": understanding.model_dump(),
        "investigation_plan": plan_obj.model_dump(),
        "sensor_selection": sensor_sel.model_dump(),
    }


@router.get("/result/{job_id}")
def get_result(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        return problem(404, "Not Found", f"unknown job {job_id}")
    if job["status"] != "completed":
        return problem(409, "Job Not Completed",
                       f"job {job_id} is {job['status']}")
    return job["result"]

