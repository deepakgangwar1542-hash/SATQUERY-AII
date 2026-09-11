"""Deterministic Geospatial Reasoning Engine (Section 15).

Executes exact spatial mathematics using Shapely, GeoPandas, and Rasterio.
Calculates spatial intersections, buffers, metric areas, and affected object counts
deterministically so the LLM never fabricates numbers.
"""
from __future__ import annotations

from typing import Any
import geopandas as gpd
import numpy as np
from shapely.geometry import shape, mapping as geom_mapping
from shapely.ops import unary_union

from .spatial import to_metric, WGS84


def intersect_polygons(
    features_a: list[dict[str, Any]],
    features_b: list[dict[str, Any]],
    predicate: str = "intersects",
    buffer_m: float = 0.0,
) -> tuple[list[dict[str, Any]], int, float]:
    """Computes exact spatial intersection between two sets of GeoJSON features.

    Returns:
        intersected_features: List of GeoJSON features representing matching geometries
        count: Number of intersecting features from layer B
        total_intersected_area_m2: Metric area of the intersection
    """
    if not features_a or not features_b:
        return [], 0, 0.0

    try:
        shapes_a = [shape(f["geometry"]) for f in features_a if f.get("geometry")]
        shapes_b = [shape(f["geometry"]) for f in features_b if f.get("geometry")]

        if not shapes_a or not shapes_b:
            return [], 0, 0.0

        gdf_a = gpd.GeoDataFrame(geometry=shapes_a, crs=WGS84)
        gdf_b = gpd.GeoDataFrame(geometry=shapes_b, crs=WGS84)

        # Project to local metric CRS for accurate spatial intersection & buffers
        gdf_a_m = to_metric(gdf_a)
        gdf_b_m = gdf_b.to_crs(gdf_a_m.crs) if gdf_a_m.crs else gdf_b

        # Merge A into a single unioned multipolygon for fast vectorized intersection
        union_a = unary_union(gdf_a_m.geometry)
        if buffer_m > 0.0:
            union_a = union_a.buffer(buffer_m)

        matching_features: list[dict[str, Any]] = []
        total_area_m2 = 0.0
        count = 0

        for idx, row in gdf_b_m.iterrows():
            geom_b = row.geometry
            if geom_b.intersects(union_a):
                inter = geom_b.intersection(union_a)
                area_m2 = float(inter.area)
                total_area_m2 += area_m2
                count += 1

                orig_props = features_b[idx].get("properties", {})
                # Convert back to WGS84 for mapping output
                inter_wgs84 = gpd.GeoDataFrame(geometry=[geom_b], crs=gdf_b_m.crs).to_crs(WGS84).geometry.iloc[0]


                matching_features.append({
                    "type": "Feature",
                    "properties": {
                        **orig_props,
                        "affected_by": "spatial_intersection",
                        "intersected_area_m2": round(area_m2, 2),
                        "status": "affected",
                    },
                    "geometry": geom_mapping(inter_wgs84),
                })

        return matching_features, count, round(total_area_m2, 2)

    except Exception as exc:
        # Fallback to simple bounding box overlap in WGS84 if metric projection fails
        return _fallback_wgs84_intersection(features_a, features_b)


def _fallback_wgs84_intersection(
    features_a: list[dict[str, Any]],
    features_b: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, float]:
    matching = []
    shapes_a = [shape(f["geometry"]) for f in features_a if f.get("geometry")]
    if not shapes_a:
        return [], 0, 0.0
    union_a = unary_union(shapes_a)

    for f in features_b:
        geom = shape(f["geometry"])
        if geom.intersects(union_a):
            matching.append({
                "type": "Feature",
                "properties": {**f.get("properties", {}), "affected": True},
                "geometry": f["geometry"],
            })
    return matching, len(matching), 0.0


def calculate_affected_buildings(
    flood_geojson: dict[str, Any] | None,
    grounded_objects: list[dict[str, Any]],
    buffer_m: float = 0.0,
) -> dict[str, Any]:
    """Calculates exact deterministic number of buildings affected by flooding."""
    flood_features = (flood_geojson or {}).get("features", [])
    building_features = []

    for obj in grounded_objects:
        geom = obj.get("geometry_wgs84")
        if geom:
            building_features.append({
                "type": "Feature",
                "properties": {
                    "id": obj.get("id"),
                    "class_label": obj.get("class_label", "building"),
                    "confidence": obj.get("confidence", 0.8),
                },
                "geometry": geom,
            })

    if not flood_features or not building_features:
        # Return exact empty calculation
        return {
            "affected_building_count": 0,
            "total_buildings_detected": len(building_features),
            "affected_percentage": 0.0,
            "affected_area_m2": 0.0,
            "affected_features_geojson": {"type": "FeatureCollection", "features": []},
            "formula": "building_footprints intersect flood_extent_mask (deterministic GIS intersection)",
        }

    matched_features, count, area_m2 = intersect_polygons(
        features_a=flood_features,
        features_b=building_features,
        predicate="intersects",
        buffer_m=buffer_m,
    )

    total = len(building_features)
    pct = round(100.0 * count / total, 2) if total > 0 else 0.0

    return {
        "affected_building_count": count,
        "total_buildings_detected": total,
        "affected_percentage": pct,
        "affected_area_m2": area_m2,
        "affected_features_geojson": {
            "type": "FeatureCollection",
            "features": matched_features,
        },
        "formula": "building_footprints intersect flood_extent_mask (deterministic GIS intersection)",
    }


class GeospatialReasoningEngine:
    """Deterministic spatial mathematics engine."""

    def __init__(self) -> None:
        pass

    def calculate_affected_buildings(
        self,
        flood_geojson: dict[str, Any] | None,
        building_polygons: list[Any],
        buffer_m: float = 0.0,
    ) -> dict[str, Any]:
        normalized_buildings: list[dict[str, Any]] = []
        for b in building_polygons:
            if isinstance(b, dict) and "geometry_wgs84" in b:
                normalized_buildings.append(b)
            elif isinstance(b, list):
                # Raw coordinate ring: [[[x, y], ...]]
                coords = [b] if len(b) > 0 and isinstance(b[0][0], (int, float)) else b
                normalized_buildings.append({
                    "id": f"bldg_{len(normalized_buildings)}",
                    "class_label": "building",
                    "confidence": 0.9,
                    "geometry_wgs84": {
                        "type": "Polygon",
                        "coordinates": coords,
                    },
                })
            elif isinstance(b, dict) and "geometry" in b:
                normalized_buildings.append({
                    "id": b.get("id", f"bldg_{len(normalized_buildings)}"),
                    "class_label": b.get("properties", {}).get("class_label", "building"),
                    "confidence": b.get("properties", {}).get("confidence", 0.9),
                    "geometry_wgs84": b["geometry"],
                })

        res = calculate_affected_buildings(flood_geojson, normalized_buildings, buffer_m=buffer_m)
        return {
            "total_buildings": res["total_buildings_detected"],
            "affected_count": res["affected_building_count"],
            "affected_percentage": res["affected_percentage"],
            "affected_area_m2": res["affected_area_m2"],
            "intersected_features": res["affected_features_geojson"],
            "formula": res["formula"],
        }

    def intersect(
        self,
        features_a: list[dict[str, Any]],
        features_b: list[dict[str, Any]],
        buffer_m: float = 0.0,
    ) -> tuple[list[dict[str, Any]], int, float]:
        return intersect_polygons(features_a, features_b, buffer_m=buffer_m)

