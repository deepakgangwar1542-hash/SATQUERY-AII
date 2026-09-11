"""Spatial predicates and geometry helpers — implements PRD §10.4.

All predicates operate on WGS84 geometries that are reprojected to a metric
CRS (auto-selected local UTM) before any buffer/area computation — areas are
never computed in raw degrees.
"""
from __future__ import annotations

import numpy as np
import geopandas as gpd
from rasterio import features
from shapely.geometry import shape, mapping

WGS84 = "EPSG:4326"


def to_geodataframe(geojson: dict | list) -> gpd.GeoDataFrame:
    """GeoJSON FeatureCollection / geometry / list-of-features → GeoDataFrame."""
    if isinstance(geojson, dict) and geojson.get("type") == "FeatureCollection":
        feats = geojson.get("features", [])
    elif isinstance(geojson, dict) and geojson.get("type") == "Feature":
        feats = [geojson]
    elif isinstance(geojson, list):
        feats = geojson
    else:
        feats = [{"type": "Feature", "properties": {}, "geometry": geojson}]
    if not feats:
        return gpd.GeoDataFrame(columns=["geometry"], geometry=[], crs=WGS84)
    geoms = [f["geometry"] if "geometry" in f else f for f in feats]
    props = [f.get("properties", {}) if "type" in f and f.get("type") == "Feature" else {}
             for f in feats]
    return gpd.GeoDataFrame(props, geometry=[shape(g) for g in geoms], crs=WGS84)


def to_metric(gdf: gpd.GeoDataFrame):
    """Reproject to a local metric CRS (auto UTM). Returns a new GeoDataFrame."""
    if gdf.empty:
        return gdf
    utm = gdf.estimate_utm_crs()
    return gdf.to_crs(utm) if utm else gdf


def area_km2(geom) -> float:
    """Area of a WGS84 geometry in km², computed in a local UTM projection."""
    gdf = to_metric(gpd.GeoDataFrame(geometry=[geom], crs=WGS84))
    return float(abs(gdf.geometry.area.iloc[0]) / 1e6)


def _buffer_metric(geom, distance_m: float):
    gdf = to_metric(gpd.GeoDataFrame(geometry=[geom], crs=WGS84))
    buf = gdf.geometry.iloc[0].buffer(distance_m)
    return gpd.GeoSeries([buf], crs=gdf.crs).to_crs(WGS84).iloc[0]


def within_distance(geom_a, geom_b, distance_m: float) -> bool:
    """True if geom_a intersects geom_b buffered by distance_m in metric CRS."""
    return geom_a.intersects(_buffer_metric(geom_b, distance_m))


def contains(geom_a, geom_b) -> bool:
    return geom_a.contains(geom_b)


def intersects(geom_a, geom_b) -> bool:
    return geom_a.intersects(geom_b)


def adjacent(geom_a, geom_b, epsilon_m: float = 1.0) -> bool:
    """Touches, or within a small metric epsilon buffer (§10.4)."""
    return geom_a.intersects(_buffer_metric(geom_b, epsilon_m))


def vectorize_mask(mask: np.ndarray, transform, crs) -> list[dict]:
    """Binary mask (H, W) → list of GeoJSON Polygon geometries in `crs`,
    converted to WGS84 for client delivery (FR-4 AC1 / FR-5)."""
    geoms = []
    mask_u8 = (np.asarray(mask) > 0).astype("uint8")
    for geom, _val in features.shapes(mask_u8, mask=mask_u8.astype(bool),
                                      transform=transform):
        geoms.append(shape(geom))
    if not geoms:
        return []
    gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs).to_crs(WGS84)
    return [mapping(g) for g in gdf.geometry]
