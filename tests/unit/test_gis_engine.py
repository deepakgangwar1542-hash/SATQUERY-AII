"""Unit tests for Geospatial Reasoning Engine and DSL."""
import pytest
from backend.geospatial.engine import GeospatialReasoningEngine
from backend.geospatial.dsl import EarthQueryGISDSL, GISOperationIR

def test_gis_engine_calculate_affected_buildings():
    engine = GeospatialReasoningEngine()
    
    # Simple flood box: [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    flood_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]
                },
                "properties": {"change": "flood_increase"}
            }
        ]
    }
    
    # 3 building polygons:
    # 1 inside flood ([2,2] to [4,4])
    # 1 partially inside ([9,9] to [11,11])
    # 1 outside ([20,20] to [22,22])
    building_polygons = [
        [[2, 2], [4, 2], [4, 4], [2, 4], [2, 2]],
        [[9, 9], [11, 9], [11, 11], [9, 11], [9, 9]],
        [[20, 20], [22, 20], [22, 22], [20, 22], [20, 20]],
    ]
    
    res = engine.calculate_affected_buildings(flood_geojson, building_polygons)
    
    assert res["total_buildings"] == 3
    assert res["affected_count"] == 2  # 2 intersect the flood polygon
    assert res["intersected_features"]["type"] == "FeatureCollection"
    assert len(res["intersected_features"]["features"]) == 2

def test_gis_dsl_ir():
    dsl = EarthQueryGISDSL()
    ir = dsl.compile("Find buildings within newly flooded areas.")
    
    assert isinstance(ir, GISOperationIR)
    ops = [node.op.value for node in ir.nodes]
    assert any(op in ["BUILDING_COUNT", "SPATIAL_INTERSECTION", "FLOOD_EXTENT"] for op in ops)
