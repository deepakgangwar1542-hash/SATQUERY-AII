"""FR-5 / §10.3 change-detection tests (synthetic pair has a known change)."""
import pytest

from backend.geospatial import change as gchange
from backend.geospatial.change import ChangeInputError


def test_detect_change_finds_known_loss(optical_pair, tmp_path):
    out = gchange.detect_change(optical_pair["optical_before"],
                                optical_pair["optical_after"],
                                out_dir=str(tmp_path))
    stats = out["statistics"]
    # the synthetic change patch is 0.25 * (0.4 * size) * (0.15 * size) ≈ big
    assert stats["area_km2"] > 0.05
    assert stats["class_breakdown"]["vegetation_loss_km2"] > 0.05
    assert stats["percent_of_aoi"] > 1.0
    assert stats["resampling_method"] == "bilinear"
    assert "bilinear" in stats["resampling_reason"]          # FR-5 AC3
    feats = out["change_geojson"]["features"]
    assert feats and all(f["geometry"]["type"] in ("Polygon", "MultiPolygon")
                         for f in feats)
    assert all(f["geometry"]["coordinates"] for f in feats)   # WGS84 delivered
    assert (tmp_path / "change_mask.tif").exists()
    assert out["metadata"]["footprint_iou"] > 0.99


def test_disjoint_aoi_rejected(tmp_path, optical_pair):
    import numpy as np
    import rasterio
    src = optical_pair["optical_before"]
    with rasterio.open(src) as s:
        profile = s.profile.copy()
        data = s.read()
    # shift 200 km east → footprints no longer overlap ≥50%
    profile["transform"] = rasterio.Affine(10, 0, profile["transform"].c + 200_000,
                                           0, profile["transform"].e, profile["transform"].f)
    p2 = tmp_path / "shifted.tif"
    with rasterio.open(p2, "w", **profile) as d:
        d.write(data)
    with pytest.raises(ChangeInputError):
        gchange.detect_change(src, str(p2))
