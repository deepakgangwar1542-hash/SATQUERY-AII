"""Deterministic planner — implements the §12.2 branch-selection rules (FR-9 AC2).

Same query → same plan, always: keyword rules first; no LLM in the planning
path so demos cannot be flaky.
"""
from __future__ import annotations

CHANGE_TERMS = ("change", "between", "difference", "compare", "decrease",
                "increase", "drop", "gain", "loss", "flood", "new", "built",
                "construction", "deforest", "expand", "urban", "before", "after")
GROUNDING_TERMS = ("how many", "where", "find", "locate", "detect", "show me",
                   "count", "buildings", "building", "roads", "road", "ships",
                   "vehicles", "objects", "trees")
NUMERIC_TERMS = ("percent", "%", "area", "km2", "km²", "how much", "threshold",
                 "more than", "less than", "greater", "statistics", "quantity")
RAG_TERMS = ("ndvi", "ndwi", "sar", "backscatter", "sentinel", "geotiff",
             "crs", "ndbi", "remote sensing", "multispectral", "co-registration")


def _dates(assets: list[dict]) -> list[str]:
    return sorted({a.get("capture_date") for a in assets if a.get("capture_date")})


def _sensors(assets: list[dict]) -> set[str]:
    return {a.get("sensor_type", "optical") for a in assets}


def build_plan(query: str, assets: list[dict]) -> list[str]:
    """Return the ordered agent list per §12.2. Deterministic."""
    q = (query or "").lower()
    dates = _dates(assets)
    sensors = _sensors(assets)
    plan: list[str] = []

    # Perception always runs first: caption/scene understanding grounds the rest.
    plan.append("perception")
    if len(dates) >= 2:
        plan.append("change_agent")
        plan.append("change_vqa")  # a bi-temporal query implies change reasoning (§12.2)
    if any(t in q for t in GROUNDING_TERMS):
        plan.append("grounding")
    if "optical" in sensors and "sar" in sensors:
        plan.append("multimodal")
    if any(t in q for t in NUMERIC_TERMS) and len(dates) >= 2:
        plan.append("gis_code")
    elif any(t in q for t in NUMERIC_TERMS):
        plan.append("gis_code")
    if any(t in q for t in RAG_TERMS):
        plan.append("rag")
    return plan


def plan_rationale(query: str, assets: list[dict]) -> dict:
    """Why each agent was included — surfaced in the UI's plan display."""
    q = (query or "").lower()
    dates = _dates(assets)
    return {
        "dates": dates,
        "sensors": sorted(_sensors(assets)),
        "bi_temporal": len(dates) >= 2,
        "grounding_terms": [t for t in GROUNDING_TERMS if t in q],
        "numeric_terms": [t for t in NUMERIC_TERMS if t in q],
        "domain_terms": [t for t in RAG_TERMS if t in q],
    }
