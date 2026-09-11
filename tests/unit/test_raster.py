"""FR-1 / §10.1 raster validation tests."""
from backend.geospatial import raster as graster


def test_valid_geotiff_report(optical_pair):
    report = graster.validate_raster(optical_pair["optical_before"], "optical")
    assert report["valid"], report
    assert report["bands"] == 4
    assert report["crs"] == "EPSG:32643"
    assert report["resolution_m"] == [10.0, 10.0]
    # descriptions were written → high-confidence mapping with B08 resolved
    assert report["band_mapping_guess"]["B08"] == 4
    assert report["band_mapping_confidence"] == "high"
    assert report["bounds_wgs84"] is not None


def test_missing_crs_rejected(tmp_path):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    p = tmp_path / "nocrs.tif"
    with rasterio.open(p, "w", driver="GTiff", height=8, width=8, count=1,
                       dtype="uint8", transform=from_origin(0, 8, 1, 1)) as dst:
        dst.write(np.ones((1, 8, 8), dtype="uint8"))
    report = graster.validate_raster(p)
    assert not report["valid"]
    assert "missing_crs" in report["errors"]


def test_corrupt_file_rejected(tmp_path):
    p = tmp_path / "corrupt.tif"
    p.write_bytes(b"this is not a tiff at all" * 10)
    report = graster.validate_raster(p)
    assert not report["valid"]
    assert report["errors"]


def test_to_reflectance_scaling():
    import numpy as np
    dn = np.array([[[2000.0]]])
    assert abs(graster.to_reflectance(dn)[0, 0, 0] - 0.2) < 1e-6
    frac = np.array([[[0.4]]])
    assert abs(graster.to_reflectance(frac)[0, 0, 0] - 0.4) < 1e-6
