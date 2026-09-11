"""Unit tests for EarthQuery Compiler and Intent Taxonomy."""
import pytest
from backend.services.earthquery.compiler import EarthQueryCompiler
from backend.services.earthquery.schema import EarthQuerySpec

def test_compiler_demo1_flood_buildings():
    compiler = EarthQueryCompiler()
    query = "Between June and August, identify areas where flooding increased and tell me how many buildings were affected."
    spec, understanding = compiler.compile(query)
    
    assert isinstance(spec, EarthQuerySpec)
    assert spec.intent in ["flood_impact_change", "flood_detection", "temporal_change"]
    assert spec.temporal.enabled is True
    assert spec.temporal.start.lower() in ["june", "jun"]
    assert spec.temporal.end.lower() in ["august", "aug"]
    assert spec.phenomenon == "flooding"
    assert "buildings" in spec.target_objects or "building" in spec.target_objects
    assert "change_detection" in spec.required_operations or "flood_detection" in spec.required_operations
    assert spec.requires_numeric_result is True
    assert "sar" in spec.preferred_modalities

def test_compiler_demo2_hypothesis_cause():
    compiler = EarthQueryCompiler()
    query = "What caused the major change in this region?"
    spec, understanding = compiler.compile(query)
    
    assert isinstance(spec, EarthQuerySpec)
    assert spec.intent in ["hypothesis_investigation", "change_explanation"]
    assert "hypothesis_generation" in spec.required_operations
    assert "multimodal" in spec.preferred_modalities or "optical" in spec.preferred_modalities

def test_compiler_demo3_anomaly_hunter():
    compiler = EarthQueryCompiler()
    query = "Find anything unusual in this region."
    spec, understanding = compiler.compile(query)
    
    assert isinstance(spec, EarthQuerySpec)
    assert spec.intent == "anomaly_detection"
    assert "anomaly_scan" in spec.required_operations

def test_compiler_building_count():
    compiler = EarthQueryCompiler()
    query = "Count the total number of buildings in this scene."
    spec, understanding = compiler.compile(query)
    
    assert isinstance(spec, EarthQuerySpec)
    assert spec.intent == "building_count"
    assert spec.requires_numeric_result is True
    assert "building_detection" in spec.required_operations

def test_compiler_object_grounding():
    compiler = EarthQueryCompiler()
    query = "Locate all storage tanks in the image."
    spec, understanding = compiler.compile(query)
    
    assert isinstance(spec, EarthQuerySpec)
    assert spec.intent in ["object_grounding", "object_detection"]
    assert "storage tanks" in spec.target_objects or "storage" in spec.target_objects
