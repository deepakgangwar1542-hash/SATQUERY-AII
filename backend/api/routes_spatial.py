"""POST /api/v1/spatial-query — direct spatial predicate query (§9.1, §10.4)."""
from __future__ import annotations

from fastapi import APIRouter
from shapely.geometry import shape

from ..agents import grounding as grounding_agent
from ..geospatial import spatial as gspatial
from ..utils.assets import resolve_asset_paths
from .errors import problem

router = APIRouter(tags=["spatial"])


@router.post("/spatial-query")
def spatial_query(req: dict):
    predicate = req.get("predicate")
    target = req.get("target_asset_id")
    ref_geom = req.get("reference_geometry")
    distance_m = float(req.get("distance_m", 100.0))
    paths = resolve_asset_paths([{"asset_id": target}])
    if target not in paths:
        return problem(404, "Not Found", f"unknown asset {target}")
    if not ref_geom:
        return problem(422, "Validation Error", "reference_geometry is required")

    out = grounding_agent.ground_objects(paths[target],
                                         req.get("object_class") or "objects")
    ref = shape(ref_geom)
    matched = []
    for obj in out.get("objects", []):
        if not obj.get("geometry_wgs84"):
            continue
        g = shape(obj["geometry_wgs84"])
        keep = {
            "within_distance": lambda: gspatial.within_distance(g, ref, distance_m),
            "contains": lambda: gspatial.contains(ref, g),
            "intersects": lambda: gspatial.intersects(g, ref),
            "adjacent": lambda: gspatial.adjacent(g, ref),
        }[predicate]()
        if keep:
            matched.append({
                "type": "Feature",
                "properties": {"id": obj["id"], "class_label": obj["class_label"],
                               "confidence": obj["confidence"],
                               "mode": out.get("mode")},
                "geometry": obj["geometry_wgs84"]})
    return {"type": "FeatureCollection", "features": matched,
            "note": out.get("note"), "detection_mode": out.get("mode")}
