"""Change Agent — Wraps real Siamese Neural Network inference and index-delta fallbacks (FR-5).

Implements real Siamese U-Net neural inference using the local LEVIR-CD checkpoint when available,
and provides transparent, honest heuristic fallback labeling (ndvi_delta_fallback) when unavailable.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import numpy as np
import rasterio

from ..geospatial import change as gchange
from ..geospatial import raster as graster
from ..geospatial import spatial as gspatial
from ..models import loaders


def _detect_change_neural(
    chg_model_bundle: dict,
    image_before: str,
    image_after: str,
    iou: float,
    threshold: float = 0.5,
    out_dir: str | None = None,
) -> dict:
    """Runs actual PyTorch SiameseChangeNet inference on co-registered bi-temporal rasters."""
    from ..geospatial.siamese_change import predict_siamese_change

    before = graster.read_raster(image_before)
    after = graster.read_raster(image_after)
    after_arr, resampling, resampling_reason = gchange.coregister(
        after, before, data_kind="continuous"
    )

    model = chg_model_bundle["model"]
    device = chg_model_bundle["device"]

    # Run genuine neural inference
    binary_mask, prob_np = predict_siamese_change(
        model=model,
        arr_before=before["array"],
        arr_after=after_arr,
        device=device,
        threshold=threshold,
    )

    crs = before["crs"]
    transform = before["transform"]
    valid = np.isfinite(before["array"][0]) & np.isfinite(after_arr[0])
    valid_mask = (binary_mask == 1) & valid
    valid_pixels = int(valid.sum())
    n_changed = int(valid_mask.sum())

    pixel_area_m2 = abs(transform.a * transform.e)
    total_area_km2 = valid_pixels * pixel_area_m2 / 1e6
    changed_km2 = round(n_changed * pixel_area_m2 / 1e6, 6)
    pct_aoi = round(100.0 * n_changed / valid_pixels, 3) if valid_pixels else 0.0

    # Vectorize change mask to GeoJSON polygons
    polys = gspatial.vectorize_mask(valid_mask, transform, crs)
    features = [
        {
            "type": "Feature",
            "properties": {
                "change_class": "detected_change",
                "pixel_count": None,
                "confidence": round(float(np.mean(prob_np[valid_mask])), 3) if n_changed > 0 else 0.0,
            },
            "geometry": g,
        }
        for g in polys
    ]
    change_geojson = {"type": "FeatureCollection", "features": features}

    statistics = {
        "area_km2": changed_km2,
        "percent_of_aoi": pct_aoi,
        "class_breakdown": {
            "changed_area_km2": changed_km2,
            "unchanged_area_km2": round((valid_pixels - n_changed) * pixel_area_m2 / 1e6, 6),
            "vegetation_loss_km2": changed_km2,
            "vegetation_gain_km2": 0.0,
            "total_compared_km2": round(total_area_km2, 6),
        },
        "resampling_method": resampling.lower(),
        "resampling_reason": resampling_reason,
        "mean_change_probability": round(float(np.mean(prob_np)), 4),
    }

    metadata = {
        "model": "siamese_unet_levircd",
        "mode": "neural_siamese",
        "checkpoint": chg_model_bundle.get("path"),
        "version": "1.2.0-levircd",
        "threshold": threshold,
        "crs": str(crs),
        "footprint_iou": round(iou, 4),
        "mean_probability": round(float(np.mean(prob_np)), 4),
        "inference_engine": "PyTorch",
    }

    change_mask_path = None
    if out_dir is not None:
        p_dir = Path(out_dir)
        p_dir.mkdir(parents=True, exist_ok=True)
        change_mask_path = str(p_dir / "change_mask.tif")
        profile = before["profile"].copy()
        for k in ("blockxsize", "blockysize", "tiled", "interleave"):
            profile.pop(k, None)
        profile.update(driver="GTiff", dtype="uint8", count=1, nodata=0, compress="deflate")
        with rasterio.open(change_mask_path, "w", **profile) as dst:
            dst.write(valid_mask.astype("uint8"), 1)
        with open(p_dir / "change_map.geojson", "w", encoding="utf-8") as fh:
            json.dump(change_geojson, fh)

    confidence = round(min(0.95, 0.72 + 0.23 * iou), 3)
    summary = (
        f"Neural Siamese change detection (SiameseChangeNet on LEVIR-CD checkpoint, threshold {threshold:.2f}): "
        f"{pct_aoi}% of the compared area ({changed_km2} km²) shows structural change. "
        f"Resampling: {statistics['resampling_method']} ({statistics['resampling_reason']})."
    )

    return {
        "change_mask_path": change_mask_path,
        "change_geojson": change_geojson,
        "statistics": statistics,
        "metadata": metadata,
        "change_classes": {"changed": n_changed, "unchanged": valid_pixels - n_changed, "compared": valid_pixels},
        "summary": summary,
        "confidence": confidence,
        "uncertainty": [],
    }


def detect_change(
    image_before: str,
    image_after: str,
    band_mapping_before: dict | None = None,
    band_mapping_after: dict | None = None,
    threshold_pct: float = -20.0,
    out_dir: str | None = None,
) -> dict:
    """Exact §13.4 contract:
    detect_change(image_before: str, image_after: str) -> dict
    Executes real neural Siamese inference when checkpoint is loaded; otherwise falls back to
    transparent index-delta heuristic labeled as ndvi_delta_fallback.
    """
    vb = graster.validate_raster(image_before, sensor_type="optical")
    va = graster.validate_raster(image_after, sensor_type="optical")
    iou = gchange.footprint_overlap_iou(image_before, image_after)
    chg_model_bundle, chg_reason = loaders.load_change_model()

    # 1. Primary Neural Path
    if chg_model_bundle is not None:
        try:
            return _detect_change_neural(
                chg_model_bundle=chg_model_bundle,
                image_before=image_before,
                image_after=image_after,
                iou=iou,
                threshold=0.5,
                out_dir=out_dir,
            )
        except Exception as exc:
            # Degrade gracefully to fallback if neural inference hits tensor mismatch or memory issue
            chg_reason = f"neural_inference_exception: {exc}"

    # 2. Honest Fallback Path
    result = gchange.detect_change(
        image_before,
        image_after,
        band_mapping_before=band_mapping_before or vb.get("band_mapping_guess"),
        band_mapping_after=band_mapping_after or va.get("band_mapping_guess"),
        threshold_pct=threshold_pct,
        out_dir=out_dir,
    )
    stats = result["statistics"]
    loss_km2 = stats["class_breakdown"]["vegetation_loss_km2"]
    gain_km2 = stats["class_breakdown"]["vegetation_gain_km2"]

    result["metadata"]["model"] = "ndvi_delta_fallback"
    result["metadata"]["mode"] = "heuristic_fallback"
    result["metadata"]["reason"] = chg_reason or "neural checkpoint unavailable"
    result["metadata"]["fallback"] = True

    result["summary"] = (
        f"Index-delta change detection fallback (threshold {threshold_pct:+.0f}%): "
        f"{stats['percent_of_aoi']}% of the compared area ({loss_km2} km²) shows "
        f"vegetation loss; {gain_km2} km² shows vegetation gain. "
        f"Reason: {result['metadata']['reason']}. "
        f"Resampling: {stats['resampling_method']} ({stats['resampling_reason']})."
    )
    result["confidence"] = round(min(0.85, 0.50 + 0.30 * iou), 3)
    result["uncertainty"] = [
        {
            "signal": "heuristic_fallback_engaged",
            "severity": "medium",
            "explanation": f"Neural change model unavailable ({result['metadata']['reason']}); index-delta fallback used.",
        }
    ]
    return result
