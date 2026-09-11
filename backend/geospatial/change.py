"""Bi-temporal change detection — implements PRD FR-5 and §10.3.

Before any pixel-wise comparison, the later image is reprojected onto the
earlier image's grid. Resampling is `bilinear` for continuous data and
`nearest` for categorical data; the choice and reason are reported in the
output metadata (FR-5 AC3). Only overlapping footprints are compared.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from shapely.geometry import box, mapping as geom_mapping

from . import raster as graster
from . import ndvi as gndvi
from . import spatial as gspatial


class ChangeInputError(ValueError):
    """Raised for invalid change-detection inputs (FR-5 AC2)."""


def footprint_overlap_iou(path_a: str, path_b: str) -> float:
    """IoU of the two rasters' WGS84 footprints (FR-5 AC2 AOI check)."""
    ra, rb = graster.read_raster(path_a), graster.read_raster(path_b)
    if ra["crs"] is None or rb["crs"] is None:
        raise ChangeInputError("missing_crs")
    ba = box(*transform_bounds(ra["crs"], "EPSG:4326", *ra["bounds"]))
    bb = box(*transform_bounds(rb["crs"], "EPSG:4326", *rb["bounds"]))
    inter = ba.intersection(bb).area
    union = ba.union(bb).area
    return inter / union if union > 0 else 0.0


def coregister(after: dict, ref: dict, data_kind: str = "continuous") -> tuple[np.ndarray, str, str]:
    """Reproject the `after` raster onto the `ref` (earlier) grid. §10.3."""
    method = Resampling.bilinear if data_kind == "continuous" else Resampling.nearest
    reason = (
        f"{'bilinear' if data_kind == 'continuous' else 'nearest'} resampling: "
        f"{'continuous reflectance data' if data_kind == 'continuous' else 'categorical data'} "
        "(PRD §10.3)"
    )
    dst = np.zeros((after["array"].shape[0], ref["array"].shape[1], ref["array"].shape[2]),
                   dtype="float32")
    for i in range(dst.shape[0]):
        reproject(
            source=after["array"][i],
            destination=dst[i],
            src_transform=after["transform"],
            src_crs=after["crs"],
            src_nodata=after["nodata"],
            dst_transform=ref["transform"],
            dst_crs=ref["crs"],
            dst_nodata=np.nan,
            resampling=method,
        )
    return dst, method.name, reason


def detect_change(image_before: str, image_after: str,
                  band_mapping_before: dict | None = None,
                  band_mapping_after: dict | None = None,
                  threshold_pct: float = -20.0,
                  min_iou: float = 0.5,
                  out_dir: str | os.PathLike | None = None,
                  data_kind: str = "continuous") -> dict:
    """Index-delta change detection. Returns dict matching the §13.4
    `detect_change` contract: {change_mask_path, change_geojson, statistics,
    metadata}. Falls back to this deterministic method whenever no trained
    change-detection checkpoint is registered (registry.yaml)."""
    iou = footprint_overlap_iou(image_before, image_after)
    if iou < min_iou:
        raise ChangeInputError(
            f"aoi_overlap_below_threshold: IoU={iou:.2f} < {min_iou} (FR-5 AC2)"
        )

    before = graster.read_raster(image_before)
    after_arr, resampling, resampling_reason = coregister(
        graster.read_raster(image_after), before, data_kind)

    mapping_b = band_mapping_before
    mapping_a = band_mapping_after or band_mapping_before
    if mapping_b is None or mapping_a is None:
        vb = graster.validate_raster(image_before)
        va = graster.validate_raster(image_after)
        mapping_b = mapping_b or vb.get("band_mapping_guess")
        mapping_a = mapping_a or va.get("band_mapping_guess")

    ndvi_before = gndvi.compute_ndvi(before["array"], mapping_b)
    ndvi_after = gndvi.compute_ndvi(after_arr, mapping_a)

    threshold_fraction = abs(threshold_pct) / 100.0
    loss = gndvi.relative_decrease_mask(ndvi_before, ndvi_after, threshold_fraction)
    gain = gndvi.relative_increase_mask(ndvi_before, ndvi_after, threshold_fraction)

    valid = np.isfinite(ndvi_before) & np.isfinite(ndvi_after)
    valid_pixels = int(valid.sum())
    n_loss = int((loss & valid).sum())
    n_gain = int((gain & valid).sum())

    # Change polygons → GeoJSON in WGS84 (FR-4 AC1 applies to all deliveries).
    crs = before["crs"]
    transform = before["transform"]
    loss_polys = gspatial.vectorize_mask(loss & valid, transform, crs)
    gain_polys = gspatial.vectorize_mask(gain & valid, transform, crs)
    features = [
        {"type": "Feature",
         "properties": {"change_class": "vegetation_loss", "pixel_count": None},
         "geometry": g}
        for g in loss_polys
    ] + [
        {"type": "Feature",
         "properties": {"change_class": "vegetation_gain", "pixel_count": None},
         "geometry": g}
        for g in gain_polys
    ]
    change_geojson = {"type": "FeatureCollection", "features": features}

    # Areas computed in metric CRS (§10.4), never raw degrees.
    pixel_area_m2 = abs(transform.a * transform.e)
    total_area_km2 = valid_pixels * pixel_area_m2 / 1e6
    statistics = {
        "area_km2": round(n_loss * pixel_area_m2 / 1e6, 6),
        "percent_of_aoi": round(100.0 * n_loss / valid_pixels, 3) if valid_pixels else 0.0,
        "class_breakdown": {
            "vegetation_loss_km2": round(n_loss * pixel_area_m2 / 1e6, 6),
            "vegetation_gain_km2": round(n_gain * pixel_area_m2 / 1e6, 6),
            "total_compared_km2": round(total_area_km2, 6),
        },
        "resampling_method": resampling.lower(),
        "resampling_reason": resampling_reason,
    }
    metadata = {
        "threshold_pct": threshold_pct,
        "min_magnitude_guard": 0.05,
        "formula": "relative decrease = (before - after) / (|before| + eps) (PRD §10.2)",
        "crs": str(crs),
        "footprint_iou": round(iou, 4),
    }

    change_mask_path = None
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        change_mask_path = str(out_dir / "change_mask.tif")
        profile = before["profile"].copy()
        for k in ("blockxsize", "blockysize", "tiled", "interleave"):
            profile.pop(k, None)
        profile.update(driver="GTiff", dtype="uint8", count=1, nodata=0,
                       compress="deflate")
        with rasterio.open(change_mask_path, "w", **profile) as dst:
            dst.write(((loss | gain) & valid).astype("uint8"), 1)
        with open(out_dir / "change_map.geojson", "w", encoding="utf-8") as fh:
            json.dump(change_geojson, fh)

    return {
        "change_mask_path": change_mask_path,
        "change_geojson": change_geojson,
        "statistics": statistics,
        "metadata": metadata,
        "change_classes": {"vegetation_loss": n_loss, "vegetation_gain": n_gain,
                           "compared": valid_pixels},
    }


def geometry_to_geojson(geom) -> dict:
    return geom_mapping(geom)
