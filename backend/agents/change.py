"""Change Agent — wraps geospatial.change for the orchestrator (FR-5)."""
from __future__ import annotations

from ..geospatial import change as gchange
from ..geospatial import raster as graster


def detect_change(image_before: str, image_after: str,
                  band_mapping_before: dict | None = None,
                  band_mapping_after: dict | None = None,
                  threshold_pct: float = -20.0,
                  out_dir: str | None = None) -> dict:
    """Exact §13.4 contract:
    detect_change(image_before: str, image_after: str) -> dict
    Returns {change_mask_path, change_geojson, statistics, metadata} plus
    a narrative `summary` and `confidence` for the verifier."""
    vb = graster.validate_raster(image_before, sensor_type="optical")
    va = graster.validate_raster(image_after, sensor_type="optical")
    result = gchange.detect_change(
        image_before, image_after,
        band_mapping_before=band_mapping_before or vb.get("band_mapping_guess"),
        band_mapping_after=band_mapping_after or va.get("band_mapping_guess"),
        threshold_pct=threshold_pct, out_dir=out_dir,
    )
    stats = result["statistics"]
    loss_km2 = stats["class_breakdown"]["vegetation_loss_km2"]
    gain_km2 = stats["class_breakdown"]["vegetation_gain_km2"]
    result["summary"] = (
        f"Index-delta change detection (threshold {threshold_pct:+.0f}%): "
        f"{stats['percent_of_aoi']}% of the compared area ({loss_km2} km²) shows "
        f"vegetation loss; {gain_km2} km² shows vegetation gain. "
        f"Resampling: {stats['resampling_method']} ({stats['resampling_reason']})."
    )
    # Deterministic data-quality-based confidence for the specialist itself.
    iou = result["metadata"]["footprint_iou"]
    result["confidence"] = round(min(0.9, 0.55 + 0.35 * iou), 3)
    result["uncertainty"] = []
    return result
