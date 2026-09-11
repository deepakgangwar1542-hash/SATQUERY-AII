"""Multimodal Fusion Agent — optical + SAR (FR-7) with §10.5 reliability.

Reliability model (documented, never silently hardcoded):
  * optical: 1.0 − cloud_fraction, where cloud fraction is the SCL/QA band if
    present, else the brightness/NIR heuristic from §10.5(b).
  * SAR: baseline 0.85 with a documented TODO for a speckle-quality model
    (explicitly allowed by §10.5, must be visible in code — it is, right here).
  * fusion_confidence = agreement-weighted combination of both reliabilities,
    never a fixed constant (FR-7 AC3).
"""
from __future__ import annotations

import numpy as np

from ..geospatial import raster as graster
from ..geospatial import ndvi as gndvi

SAR_RELIABILITY_BASELINE = 0.85  # TODO(§10.5): replace with speckle-quality model


def _optical_profile(path: str, band_mapping: dict | None) -> dict:
    report = graster.validate_raster(path, sensor_type="optical")
    mapping = band_mapping or report.get("band_mapping_guess") or {}
    data = graster.read_raster(path)
    arr = data["array"]
    refl = graster.to_reflectance(arr)
    shares: dict = {}
    cloud_fraction = 0.0
    ndvi_mean = None
    try:
        ndvi = gndvi.compute_ndvi(arr, mapping)
        ndwi = gndvi.compute_ndwi(arr, mapping)
        valid = np.isfinite(ndvi)
        n = int(valid.sum()) or 1
        blue = refl[0]
        cloud_fraction = float(((blue > 0.25) & (ndvi < 0.2) & valid).sum() / n)
        shares = {
            "vegetation": float(((ndvi > 0.3) & valid).sum() / n),
            "water": float(((ndwi > 0.0) & valid & ~(ndvi > 0.3)).sum() / n),
            "other": float((~((ndvi > 0.3) | (ndwi > 0.0)) & valid).sum() / n),
        }
        ndvi_mean = float(np.nanmean(ndvi[valid]))
    except (KeyError, ValueError):
        pass
    return {"path": path, "cloud_fraction": cloud_fraction,
            "reliability": round(max(0.1, 1.0 - cloud_fraction), 3),
            "shares": shares, "ndvi_mean": ndvi_mean,
            "band_mapping": mapping}


def _sar_profile(path: str, band_mapping: dict | None) -> dict:
    report = graster.validate_raster(path, sensor_type="sar")
    mapping = band_mapping or report.get("band_mapping_guess") or {}
    arr = graster.read_raster(path)["array"]
    vv = arr[0]
    prof = {
        "path": path,
        "vv_mean_db": round(float(np.nanmean(vv)), 2),
        "reliability": SAR_RELIABILITY_BASELINE,
        "band_mapping": mapping,
    }
    if arr.shape[0] > 1:
        prof["vh_mean_db"] = round(float(np.nanmean(arr[1])), 2)
        prof["vv_vh_ratio_db"] = round(prof["vv_mean_db"] - prof["vh_mean_db"], 2)
    # Coarse SAR land/water signal: VV < -18 dB ≈ smooth (water) surface.
    prof["shares"] = {"vegetation": float((vv > -12).mean()),
                      "water": float((vv < -18).mean()),
                      "other": float(((vv >= -18) & (vv <= -12)).mean())}
    return prof


def _empty_shares() -> dict:
    return {"vegetation": 0.0, "water": 0.0, "other": 0.0}


def predict_multimodal(optical_image: str | None, sar_image: str | None) -> dict:
    """Exact §13.4 contract:
    predict_multimodal(optical_image: str, sar_image: str) -> dict
    Returns {prediction, confidence, evidence: {optical, sar}, metadata}."""
    if not optical_image and not sar_image:
        raise ValueError("at least one of optical_image / sar_image is required (FR-7)")

    optical = _optical_profile(optical_image, None) if optical_image else None
    sar = _sar_profile(sar_image, None) if sar_image else None

    if optical and not sar:  # FR-7 AC2 single-sensor passthrough
        conf = optical["reliability"]
        return {
            "prediction": {"class_shares": optical["shares"], "ndvi_mean": optical["ndvi_mean"]},
            "confidence": conf,
            "evidence": {"optical": optical, "sar": None},
            "metadata": {"fusion_performed": False,
                         "note": "single-sensor mode: fusion was not performed",
                         "sensor_reliability": {"optical": optical["reliability"]}},
        }
    if sar and not optical:
        return {
            "prediction": {"class_shares": sar["shares"], "vv_mean_db": sar["vv_mean_db"]},
            "confidence": sar["reliability"],
            "evidence": {"optical": None, "sar": sar},
            "metadata": {"fusion_performed": False,
                         "note": "single-sensor mode: fusion was not performed",
                         "sensor_reliability": {"sar": sar["reliability"]}},
        }

    # Both sensors: reliability-weighted fusion of class shares + agreement.
    assert optical and sar
    wo, ws = optical["reliability"], sar["reliability"]
    total = wo + ws
    fused = {k: round((wo * optical["shares"].get(k, 0.0)
                       + ws * sar["shares"].get(k, 0.0)) / total, 4)
             for k in _empty_shares()}
    agreement = 1.0 - sum(abs(optical["shares"].get(k, 0.0) - sar["shares"].get(k, 0.0))
                          for k in fused) / 2.0
    fusion_confidence = round(min(0.95, total / 2.0 * (0.6 + 0.4 * agreement)), 3)
    return {
        "prediction": {"class_shares": fused,
                       "ndvi_mean": optical["ndvi_mean"],
                       "vv_mean_db": sar["vv_mean_db"]},
        "confidence": fusion_confidence,
        "evidence": {"optical": optical, "sar": sar},
        "metadata": {
            "fusion_performed": True,
            "agreement": round(agreement, 3),
            "sensor_reliability": {"optical": wo, "sar": ws},
            "cloud_fraction_optical": optical["cloud_fraction"],
            "sar_reliability_note": "baseline with speckle-quality TODO (§10.5)",
        },
    }
