"""POST /api/v1/execute-analysis — sandboxed GIS code generation (FR-12)."""
from __future__ import annotations

import os

from fastapi import APIRouter

from ..agents import code_agent as code_agent_mod
from ..utils.assets import get_asset, resolve_asset_paths
from .errors import problem

router = APIRouter(tags=["analysis"])


@router.post("/execute-analysis")
def execute_analysis(req: dict):
    intent = req.get("intent")
    asset_ids = req.get("asset_ids") or []
    paths = resolve_asset_paths([{"asset_id": a} for a in asset_ids])
    if not intent:
        return problem(422, "Validation Error", "intent is required")
    missing = [a for a in asset_ids if a not in paths]
    if missing:
        return problem(404, "Not Found", f"unknown assets: {missing}")

    params = dict(req.get("params") or {})
    # Wire asset paths + band mapping into template params (sandbox 'input/').
    ordered = [paths[a] for a in asset_ids]
    if len(ordered) >= 2:
        params.setdefault("optical_before", "input/" + os.path.basename(ordered[0]))
        params.setdefault("optical_after", "input/" + os.path.basename(ordered[-1]))
    elif ordered:
        params.setdefault("optical", "input/" + os.path.basename(ordered[0]))
    if "band_mapping" not in params or not params["band_mapping"]:
        rec = get_asset(asset_ids[0])
        params["band_mapping"] = (rec or {}).get("validation", {}).get("band_mapping_guess") or {}
    params.setdefault("threshold_pct", -20.0)

    try:
        out = code_agent_mod.execute_analysis(intent, params, ordered)
    except ValueError as exc:
        return problem(422, "Analysis Not Supported", str(exc))
    return {"generated_code": out["generated_code"], "result": out["result"],
            "sandbox_log": out["sandbox_log"], "ok": out["ok"]}
