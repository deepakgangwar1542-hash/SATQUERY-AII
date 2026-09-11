"""POST /api/v1/change-detection — direct bi-temporal call (§9.1)."""
from __future__ import annotations

from fastapi import APIRouter

from ..agents import change as change_agent
from ..services import artifact_store
from ..utils.assets import resolve_asset_paths
from .errors import problem

router = APIRouter(tags=["change"])


@router.post("/change-detection")
def change_detection(req: dict):
    before_id = req.get("image_before_asset_id")
    after_id = req.get("image_after_asset_id")
    paths = resolve_asset_paths([{"asset_id": before_id}, {"asset_id": after_id}])
    if before_id not in paths or after_id not in paths:
        return problem(404, "Not Found", "one or both assets are unknown")
    threshold = float(req.get("threshold_pct", -20.0))
    try:
        out = change_agent.detect_change(paths[before_id], paths[after_id],
                                         threshold_pct=threshold,
                                         out_dir=str(artifact_store.ARTIFACTS_DIR / "direct"))
    except Exception as exc:
        return problem(422, "Change Detection Failed", str(exc))
    return {"summary": out["summary"], "statistics": out["statistics"],
            "metadata": out["metadata"], "change_geojson": out["change_geojson"],
            "confidence": out["confidence"]}
