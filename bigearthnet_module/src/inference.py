"""Inference entrypoint — the ONLY surface the backend may call (§13.2/§13.4).

Exact contract (PRD §13.4):
    predict_multimodal(optical_image: str, sar_image: str) -> dict
Returns {prediction, confidence, evidence: {optical, sar}, metadata}.

Reads GeoTIFFs with rasterio, extracts the preprocessing features, and runs
the trained checkpoint. Confidence is the softmax probability of the winning
class (used as this specialist's model_confidence input to the §12.4 formula,
not as the final system confidence).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

MODULE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CKPT = MODULE_DIR / "checkpoints" / "fusion_model.joblib"

_model = None


def _load_model():
    global _model
    if _model is None:
        if not DEFAULT_CKPT.exists():
            raise FileNotFoundError(
                f"no fusion checkpoint at {DEFAULT_CKPT}; run "
                "bigearthnet_module/src/train.py first")
        from .model import FusionModel
        _model = FusionModel.load(str(DEFAULT_CKPT))
    return _model


def _read_optical(path: str) -> np.ndarray | None:
    if not path:
        return None
    with rasterio.open(path) as src:
        arr = src.read().astype("float32")
    arr = arr / 10000.0 if float(np.nanmax(arr)) > 1.5 else arr
    # map onto the 4-band (B, G, R, NIR) feature convention
    if arr.shape[0] >= 4:
        arr = arr[[1, 2, 3, arr.shape[0] - 1]] if arr.shape[0] > 4 else arr
    return np.clip(arr, 0, 1)


def _read_sar(path: str) -> np.ndarray | None:
    if not path:
        return None
    with rasterio.open(path) as src:
        arr = src.read().astype("float32")
    if arr.shape[0] == 1:
        arr = np.concatenate([arr, arr - 7.5], 0)  # synthesize VH if missing
    return np.clip(arr, -35, 5)


def predict_multimodal(optical_image: str, sar_image: str) -> dict:
    from .preprocessing import features
    model = _load_model()
    optical = _read_optical(optical_image) if optical_image else None
    sar = _read_sar(sar_image) if sar_image else None
    if optical is None and sar is None:
        raise ValueError("at least one sensor path is required")

    patch = {"optical": optical, "sar": sar, "label": 0}
    X = features(patch, "fusion" if (optical is not None and sar is not None)
                 else ("optical" if optical is not None else "sar"))[None, :]
    proba = model.predict_proba(X)[0]
    best = int(proba.argmax())
    fusion = optical is not None and sar is not None
    return {
        "prediction": {"class": model.classes[best],
                       "probabilities": {c: round(float(p), 4)
                                         for c, p in zip(model.classes, proba)}},
        "confidence": round(float(proba[best]), 4),
        "evidence": {
            "optical": {"present": optical is not None},
            "sar": {"present": sar is not None},
        },
        "metadata": {"model": "bigearthnet_adapted_lr",
                     "checkpoint": str(DEFAULT_CKPT),
                     "fusion_performed": fusion,
                     "note": "" if fusion else "single-sensor mode: fusion not performed"},
    }
