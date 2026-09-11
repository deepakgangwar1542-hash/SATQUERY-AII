"""Unit tests for MobileSAM / edge-refined contour segmenter."""
import numpy as np
from affine import Affine
from rasterio.crs import CRS

from backend.geospatial.sam_segmenter import segment_boxes


def test_segment_boxes_generates_valid_wgs84_polygons():
    # Synthetic 100x100 RGB image
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    # Draw a bright circular/square object in the center
    img[30:70, 30:70] = 220

    transform = Affine(10.0, 0.0, 310000.0, 0.0, -10.0, 4100000.0)
    crs = CRS.from_epsg(32643)

    boxes = [[25.0, 25.0, 75.0, 75.0]]
    results = segment_boxes(img, boxes, transform, crs)

    assert len(results) == 1
    res = results[0]
    assert "geometry_wgs84" in res
    geom = res["geometry_wgs84"]
    assert geom["type"] in ("Polygon", "MultiPolygon")
    coords = geom["coordinates"]
    assert len(coords) > 0
    assert res["area_px"] > 0
    assert res["mask_type"] in ("contour", "bbox", "sam_neural")
