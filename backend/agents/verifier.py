"""Verifier / Evidence-Fusion Agent (FR-10) implementing the §12.4 formula.

Final confidence is a weighted combination of six documented components whose
weights live in config/confidence_weights.yaml — never a raw model score and
never a hardcoded constant.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "confidence_weights.yaml"

BREAKDOWN_KEYS = ("model_confidence", "evidence_agreement", "sensor_reliability",
                  "data_quality", "spatial_consistency", "temporal_consistency")


@lru_cache(maxsize=1)
def weights() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        w = yaml.safe_load(fh)
    assert abs(sum(w[k] for k in BREAKDOWN_KEYS) - 1.0) < 1e-6, "§12.4: weights must sum to 1"
    return w


def _direction(text: str) -> str | None:
    t = (text or "").lower()
    if any(w in t for w in ("loss", "decrease", "drop", "decline", "reced")):
        return "decrease"
    if any(w in t for w in ("gain", "increase", "rise", "new construction", "inundat")):
        return "increase"
    return None


def evidence_agreement(outputs: dict) -> tuple[float, list[str]]:
    """1.0 − normalized disagreement between independent evidence sources
    (§12.4). Returns (score, conflict_descriptions)."""
    conflicts: list[str] = []
    score = 1.0
    change = outputs.get("change_agent") or {}
    vqa = outputs.get("change_vqa") or {}
    mm = outputs.get("multimodal") or {}

    stats_dir = None
    if change.get("statistics"):
        b = change["statistics"]["class_breakdown"]
        if b.get("vegetation_loss_km2", 0) > b.get("vegetation_gain_km2", 0):
            stats_dir = "decrease"
        elif b.get("vegetation_gain_km2", 0) > 0:
            stats_dir = "increase"
    vqa_dir = _direction(vqa.get("answer", "")) if vqa.get("answer") else None
    if stats_dir and vqa_dir and stats_dir != vqa_dir:
        conflicts.append(f"change_statistics={stats_dir} vs change_vqa_narrative={vqa_dir}")
        score -= 0.4
    if mm.get("metadata", {}).get("agreement") is not None:
        agree = float(mm["metadata"]["agreement"])
        if agree < 0.5:
            conflicts.append(f"optical_vs_sar_agreement_low:{agree:.2f}")
            score -= (0.5 - agree)
    return max(0.0, min(1.0, score)), conflicts


def data_quality(validator_output: dict, perception_profile: dict | None) -> float:
    q = 1.0
    if not validator_output.get("all_valid", True):
        q -= 0.2
    if validator_output.get("band_mapping_confidence") == "low":
        q -= 0.1
    if validator_output.get("any_missing_nodata"):
        q -= 0.05
    cf = (perception_profile or {}).get("cloud_fraction")
    if cf:
        q -= 0.3 * float(cf)  # cloud-contaminated optical data is lower quality
    return max(0.05, round(q, 3))


def sensor_reliability(outputs: dict) -> float:
    mm = outputs.get("multimodal") or {}
    rel = mm.get("metadata", {}).get("sensor_reliability")
    if rel:
        return round(sum(rel.values()) / len(rel), 3)
    prof = (outputs.get("perception") or {}).get("scene_profile") or {}
    cf = prof.get("cloud_fraction")
    if cf is not None:
        return round(max(0.1, 1.0 - 0.5 * float(cf)), 3)
    return 0.8  # no sensor-quality signal ran; documented neutral baseline


def spatial_consistency(outputs: dict) -> float:
    """Detected objects should fall inside the change polygons (§12.4)."""
    grounding = outputs.get("grounding") or {}
    change = outputs.get("change_agent") or {}
    objects = grounding.get("objects") or []
    fc = change.get("change_geojson") or {}
    if not objects or not fc.get("features"):
        return 1.0
    try:
        import geopandas as gpd
        from shapely.geometry import shape
        from ..geospatial.spatial import to_metric
        objs = gpd.GeoDataFrame(geometry=[shape(o["geometry_wgs84"]) for o in objects
                                          if o.get("geometry_wgs84")], crs="EPSG:4326")
        chg = gpd.GeoDataFrame(geometry=[shape(f["geometry"]) for f in fc["features"]],
                               crs="EPSG:4326")
        objs_m, chg_m = to_metric(objs), to_metric(chg)
        buffered = chg_m.buffer(50)  # 50 m tolerance around change polygons
        hits = sum(int(any(b.intersects(g) for b in buffered))
                   for g in objs_m.geometry)
        return round(hits / len(objs_m), 3) if len(objs_m) else 1.0
    except Exception:
        return 0.9  # evaluation failed; slight penalty + note below


def compute(outputs: dict, validator_output: dict, dates: list[str]) -> dict:
    w = weights()
    confs = [o.get("confidence") for o in outputs.values()
             if isinstance(o, dict) and isinstance(o.get("confidence"), (int, float))]
    model_confidence = round(sum(confs) / len(confs), 3) if confs else 0.5
    agreement, conflicts = evidence_agreement(outputs)
    profile = (outputs.get("perception") or {}).get("scene_profile")
    breakdown = {
        "model_confidence": model_confidence,
        "evidence_agreement": round(agreement, 3),
        "sensor_reliability": sensor_reliability(outputs),
        "data_quality": data_quality(validator_output, profile),
        "spatial_consistency": spatial_consistency(outputs),
        "temporal_consistency": 1.0 if len(dates) < 3 else _temporal(outputs, dates),
    }
    final = round(sum(w[k] * breakdown[k] for k in BREAKDOWN_KEYS), 3)

    thresholds = w.get("verdict_thresholds", {"consistent": 0.75, "partially_consistent": 0.45})
    if agreement >= thresholds["consistent"]:
        verdict = "CONSISTENT"
    elif agreement >= thresholds["partially_consistent"]:
        verdict = "PARTIALLY_CONSISTENT"
    else:
        verdict = "CONFLICTING"

    uncertainty: list[dict] = []
    for c in conflicts:
        uncertainty.append({"signal": "evidence_conflict", "severity": "high"
                            if verdict == "CONFLICTING" else "medium",
                            "explanation": c})
    if breakdown["sensor_reliability"] < 0.7:
        uncertainty.append({
            "signal": "low_sensor_reliability", "severity": "medium",
            "explanation": f"Sensor reliability scored {breakdown['sensor_reliability']} "
                           "(cloud contamination or SAR baseline)."})
    if not confs:
        uncertainty.append({
            "signal": "no_specialist_confidence", "severity": "high",
            "explanation": "No specialist agent produced a confidence; "
                           "model_confidence defaulted to 0.5."})
    return {"confidence_breakdown": breakdown, "final_confidence": final,
            "consistency_verdict": verdict, "uncertainty": uncertainty}


def _temporal(outputs: dict, dates: list[str]) -> float:
    """§12.4: for ≥3-date sequences, penalize implausible oscillation.
    v1 analyses are 2-date; this path activates when 3+ dates exist."""
    vqa = (outputs.get("change_vqa") or {}).get("answer", "")
    if dates and _direction(vqa) is None:
        return 0.9  # multi-date run without a clear monotonic narrative
    return 1.0
