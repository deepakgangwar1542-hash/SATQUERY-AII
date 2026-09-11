"""Raster validation and I/O — implements PRD FR-1 and §10.1.

All raster I/O goes through rasterio exclusively (FR-1 AC4). Band semantics
are resolved from metadata (descriptions / tags) first, then from a documented
convention table (§10.6) — never from a hardcoded positional index (§10.2).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform_bounds

MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB

# §10.6 — Sensor band convention table (fallback when metadata tags are absent).
# Only applied when the band count matches the convention exactly. For 12-band
# Sentinel-2 stacks the B08 position genuinely varies between products, so the
# guess is flagged low-confidence and callers may override it (§10.2/§10.6).
CONVENTION_TABLE: dict[tuple[str, int], dict[str, int]] = {
    ("optical", 4): {"B02": 1, "B03": 2, "B04": 3, "B08": 4},
    ("optical", 2): {"B02": 1, "B08": 2},          # minimal NIR stack
    ("sar", 2): {"VV": 1, "VH": 2},
    ("sar", 1): {"VV": 1},
    # PRD §9.2 example convention for a 12-band L2A stack (low confidence).
    ("optical", 12): {"B01": 1, "B02": 2, "B03": 3, "B04": 4, "B05": 5,
                      "B06": 6, "B07": 7, "B08": 8, "B8A": 9, "B09": 10,
                      "B11": 11, "B12": 12},
}
LOW_CONFIDENCE_COUNTS = {12}  # B08 position varies by product for these


def _band_mapping_guess(descriptions: list[str | None], tags: dict,
                        sensor_type: str | None, bands: int) -> tuple[dict | None, str]:
    """Return (mapping|None, confidence). Mapping values are 1-based indexes."""
    # 1) explicit band descriptions (most reliable)
    named = {d.strip(): i + 1 for i, d in enumerate(descriptions) if d}
    if len(named) >= 2:
        return named, "high"
    # 2) dataset-level tags, e.g. BAND1=B02 ... or a JSON-ish tags blob
    if tags:
        tagged = {}
        for k, v in tags.items():
            ku = k.upper()
            if ku.startswith("BAND") and v:
                try:
                    tagged[str(v).strip().upper()] = int(ku.replace("BAND", ""))
                except ValueError:
                    continue
        if len(tagged) >= 2:
            return tagged, "high"
    # 3) convention table fallback for known sensor/band-count combos
    for sensor in filter(None, [sensor_type, "optical", "sar"]):
        conv = CONVENTION_TABLE.get((sensor, bands))
        if conv:
            conf = "low" if bands in LOW_CONFIDENCE_COUNTS else "medium"
            return dict(conv), conf
    return None, "none"


def validate_raster(path: str | os.PathLike, sensor_type: str | None = None) -> dict:
    """Validate a raster per FR-1 and return a §9.3.1 ValidationReport dict."""
    path = str(path)
    errors: list[str] = []
    size_ok = os.path.getsize(path) <= MAX_UPLOAD_BYTES if os.path.exists(path) else False
    if not os.path.exists(path):
        return {"valid": False, "errors": ["file_not_found"]}
    if not size_ok:
        errors.append("file_too_large")

    try:
        with rasterio.open(path) as src:
            driver = src.driver
            crs = src.crs
            bands = src.count
            width, height = src.width, src.height
            res = [float(v) for v in src.res]
            bounds = [float(v) for v in src.bounds]
            nodata = src.nodata
            descriptions = list(src.descriptions)
            tags = src.tags()
            valid_shapes = width > 0 and height > 0
            if driver not in ("GTiff", "TIFF"):
                errors.append(f"unsupported_format:{driver}")
            if crs is None:
                errors.append("missing_crs")  # FR-1 AC2
            if not valid_shapes:
                errors.append("invalid_dimensions")
            mapping, mapping_conf = _band_mapping_guess(descriptions, tags, sensor_type, bands)
            report = {
                "format": "GeoTIFF" if driver == "GTiff" else driver,
                "width": width,
                "height": height,
                "bands": bands,
                "crs": str(crs) if crs else None,
                "resolution_m": res,
                "bounds": bounds,
                "nodata": nodata,
                "sensor_type": sensor_type,
                "band_mapping_guess": mapping,
                "band_mapping_confidence": mapping_conf,
                "bounds_wgs84": [float(v) for v in transform_bounds(crs, "EPSG:4326", *bounds)]
                if crs else None,  # §10.1: bounds additionally reported in EPSG:4326
                "descriptions": descriptions,
                "valid": not errors,
                "errors": errors,
            }
            return report
    except rasterio.errors.RasterioIOError as exc:  # corrupt / non-raster file
        return {"valid": False, "errors": [f"unreadable_raster:{exc}"]}
    except Exception as exc:  # never leak a stack trace to the client (FR-1 AC1)
        return {"valid": False, "errors": [f"validation_failed:{exc}"]}


def read_raster(path: str | os.PathLike, indexes: list[int] | None = None) -> dict:
    """Read a raster into a numpy array plus its georeferencing metadata."""
    with rasterio.open(str(path)) as src:
        arr = src.read(indexes=indexes).astype("float32")
        return {
            "array": arr,
            "transform": src.transform,
            "crs": src.crs,
            "bounds": tuple(src.bounds),
            "res": tuple(src.res),
            "nodata": src.nodata,
            "descriptions": list(src.descriptions),
            "profile": src.profile.copy(),
        }


def to_reflectance(arr: np.ndarray) -> np.ndarray:
    """Scale DN to 0..1 reflectance. Sentinel-2 L2A DNs (~0..10000) are divided
    by 10000; data already in 0..1 is passed through. Needed only for absolute
    thresholds (e.g. cloud brightness), not for normalized-difference indices."""
    a = np.asarray(arr, dtype="float32")
    if a.size and float(np.nanmax(a)) > 1.5:
        a = a / 10000.0
    return np.clip(a, 0.0, 1.5)
