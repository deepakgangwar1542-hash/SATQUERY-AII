"""§10.4 spatial predicate tests — metric CRS, never raw degrees."""
from shapely.geometry import Point, Polygon

from backend.geospatial import spatial as gspatial


def test_within_distance_is_metric_not_degrees():
    a = Point(77.59, 12.97)   # Bengaluru-ish
    b = Point(77.60, 12.97)   # ~1.1 km away at this latitude
    assert gspatial.within_distance(a, b, 2000.0)
    assert not gspatial.within_distance(a, b, 500.0)
    # 0.01 degrees ≈ 1.1 km; a degree-based buffer would wildly disagree
    assert not gspatial.within_distance(a, b, 100.0)


def test_area_km2_sane():
    poly = Polygon([(77.55, 12.95), (77.65, 12.95), (77.65, 13.05), (77.55, 13.05)])
    area = gspatial.area_km2(poly)
    assert 100 < area < 130   # ~0.1° x 0.1° near the equator ≈ 123 km²


def test_adjacent_epsilon():
    a = Point(0, 0)
    b = Point(0.00002, 0)  # ~2 m at the equator
    assert gspatial.adjacent(a, b, epsilon_m=10.0)
    assert not gspatial.adjacent(a, Point(0.001, 0), epsilon_m=10.0)
