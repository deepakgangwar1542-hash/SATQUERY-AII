"""Vegetation/water indices — implements PRD §10.2 canonical formulas.

NDVI  = (NIR - Red) / (NIR + Red + eps),  NIR = B08, Red = B04
NDWI  = (Green - NIR) / (Green + NIR + eps), Green = B03 (McFeeters)

Band positions are ALWAYS resolved through an explicit band mapping (from
validation metadata or user input) — never a hardcoded positional index.
"""
from __future__ import annotations

import numpy as np

EPS = 1e-8

REQUIRED_BANDS = {
    "ndvi": ("B08", "B04"),
    "ndwi": ("B03", "B08"),
}


def resolve_band(band_mapping: dict | None, name: str) -> int:
    """Resolve a canonical band name (B02..B12/VV/VH) to a 1-based index."""
    if not band_mapping:
        raise ValueError(
            f"No band mapping available; cannot resolve '{name}'. Provide an "
            "explicit mapping (PRD §10.2 forbids hardcoded band positions)."
        )
    if name in band_mapping:
        return int(band_mapping[name])
    raise KeyError(
        f"Band '{name}' not in mapping {band_mapping}. The raster must be "
        "validated with a band_mapping_guess or the caller must supply one."
    )


def _normalized_difference(arr: np.ndarray, idx_a: int, idx_b: int) -> np.ndarray:
    a = arr[idx_a - 1].astype("float32")  # 1-based index → array position
    b = arr[idx_b - 1].astype("float32")
    return (a - b) / (a + b + EPS)


def compute_index(arr: np.ndarray, band_mapping: dict, index_name: str) -> np.ndarray:
    """Compute NDVI or NDWI for a (bands, H, W) array using §10.2 formulas."""
    name = index_name.lower()
    if name not in REQUIRED_BANDS:
        raise ValueError(f"Unsupported index '{index_name}'. Supported: {list(REQUIRED_BANDS)}")
    pos, neg = (resolve_band(band_mapping, b) for b in REQUIRED_BANDS[name])
    return _normalized_difference(arr, pos, neg)


# Backwards-friendly aliases used across agents.
compute_ndvi = lambda arr, mapping: compute_index(arr, mapping, "ndvi")   # noqa: E731
compute_ndwi = lambda arr, mapping: compute_index(arr, mapping, "ndwi")   # noqa: E731


def relative_decrease_mask(before: np.ndarray, after: np.ndarray,
                           threshold_fraction: float = 0.20,
                           min_magnitude: float = 0.05) -> np.ndarray:
    """Pixel-wise relative decrease mask per §10.2:

        ((before - after) / (abs(before) + eps)) > threshold_fraction

    Pixels where |before| < min_magnitude are excluded (divide-by-near-zero
    guard); both guard and threshold must surface in generated-code docstrings.
    """
    b = before.astype("float32")
    a = after.astype("float32")
    rel = (b - a) / (np.abs(b) + EPS)
    return (rel > threshold_fraction) & (np.abs(b) >= min_magnitude)


def relative_increase_mask(before: np.ndarray, after: np.ndarray,
                           threshold_fraction: float = 0.20,
                           min_magnitude: float = 0.05) -> np.ndarray:
    rel = (after.astype("float32") - before.astype("float32")) / (np.abs(before.astype("float32")) + EPS)
    return (rel > threshold_fraction) & (np.abs(before.astype("float32")) >= min_magnitude)


def index_delta(before: np.ndarray, after: np.ndarray) -> np.ndarray:
    """delta = index_after - index_before (§10.2)."""
    return after.astype("float32") - before.astype("float32")
