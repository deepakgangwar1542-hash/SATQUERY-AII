"""§10.2 canonical index formula tests."""
import numpy as np
import pytest

from backend.geospatial import ndvi as gndvi


def test_ndvi_canonical_formula():
    arr = np.array([
        [[100.0]],   # B02 blue
        [[200.0]],   # B03 green
        [[400.0]],   # B04 red
        [[1600.0]],  # B08 nir
    ])
    mapping = {"B02": 1, "B03": 2, "B04": 3, "B08": 4}
    ndvi = gndvi.compute_ndvi(arr, mapping)
    expected = (1600.0 - 400.0) / (1600.0 + 400.0 + 1e-8)
    assert ndvi.shape == (1, 1)
    assert abs(ndvi[0, 0] - expected) < 1e-6


def test_ndwi_uses_green_and_nir():
    arr = np.array([[[100.0]], [[600.0]], [[400.0]], [[200.0]]])
    mapping = {"B02": 1, "B03": 2, "B04": 3, "B08": 4}
    ndwi = gndvi.compute_ndwi(arr, mapping)
    expected = (600.0 - 200.0) / (600.0 + 200.0 + 1e-8)
    assert abs(ndwi[0, 0] - expected) < 1e-6


def test_no_hardcoded_band_positions():
    # A 12-band stack where B08 sits at index 7 must be honored (§10.2).
    arr = np.zeros((12, 2, 2), dtype="float32")
    arr[6] = 1600.0  # B08 at position 7
    arr[3] = 400.0   # B04 at position 4
    mapping = {"B04": 4, "B08": 7}
    ndvi = gndvi.compute_ndvi(arr, mapping)
    assert abs(ndvi[0, 0] - (1600.0 - 400.0) / (2000.0 + 1e-8)) < 1e-6


def test_missing_mapping_raises():
    with pytest.raises(ValueError):
        gndvi.resolve_band(None, "B08")


def test_relative_decrease_guard():
    before = np.array([[0.8, 0.01, 0.5]])
    after = np.array([[0.4, 0.0, 0.2]])
    mask = gndvi.relative_decrease_mask(before, after, 0.2, min_magnitude=0.05)
    assert mask[0, 0]        # 50% relative drop, magnitude ok
    assert not mask[0, 1]    # near-zero magnitude excluded by the guard
    assert mask[0, 2]        # 60% drop
