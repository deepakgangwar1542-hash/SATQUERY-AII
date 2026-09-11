"""Preprocessing: patches → feature vectors / tensors (§13.3).

Feature design is shared by both model backends so checkpoints stay comparable:
  optical: [mean B, G, R, NIR, ndvi_proxy, std NIR]
  sar:     [mean VV, mean VH, vv_vh_ratio]
The sklearn backend consumes the concatenation; the torch backend consumes
4-ch (optical-derived) + 3-ch (SAR + ratio) tensors at 32×32.
"""
from __future__ import annotations

import numpy as np

from .dataset import synthetic_patch


def optical_features(optical: np.ndarray) -> np.ndarray:
    """(4, H, W) reflectance → 6-dim vector."""
    b, g, r, nir = (np.nanmean(optical[i]) for i in range(min(4, optical.shape[0])))
    nir_std = float(np.nanstd(optical[3])) if optical.shape[0] > 3 else 0.0
    ndvi_proxy = (nir - r) / (nir + r + 1e-8)
    return np.array([b, g, r, nir, ndvi_proxy, nir_std], dtype="float32")


def sar_features(sar: np.ndarray) -> np.ndarray:
    """(2, H, W) dB → 3-dim vector."""
    vv, vh = (np.nanmean(sar[i]) for i in range(min(2, sar.shape[0])))
    return np.array([vv, vh, vv - vh], dtype="float32")


def features(patch: dict, mode: str = "fusion") -> np.ndarray:
    """mode: 'optical' | 'sar' | 'fusion' — used by the §17.1 ablation."""
    o = optical_features(patch["optical"]) if patch.get("optical") is not None else None
    s = sar_features(patch["sar"]) if patch.get("sar") is not None else None
    zeros_o = np.zeros(6, "float32")
    zeros_s = np.zeros(3, "float32")
    if mode == "optical":
        return np.concatenate([o if o is not None else zeros_o, zeros_s])
    if mode == "sar":
        return np.concatenate([zeros_o, s if s is not None else zeros_s])
    return np.concatenate([o if o is not None else zeros_o,
                           s if s is not None else zeros_s])


def dataset_matrix(patches: list[dict], mode: str = "fusion"):
    X = np.stack([features(p, mode) for p in patches])
    y = np.array([p["label"] for p in patches])
    return X, y


def standardize(X: np.ndarray, mean=None, std=None):
    if mean is None:
        mean, std = X.mean(0), X.std(0) + 1e-8
    return (X - mean) / std, mean, std


def make_example_patch(seed: int = 7) -> dict:
    """One synthetic patch for contract tests / docs examples."""
    return synthetic_patch(seed)
