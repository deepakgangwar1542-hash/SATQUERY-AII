"""Unit tests for Autonomous Sensor Selector."""
import pytest
from backend.services.earthquery.sensor_selector import AutonomousSensorSelector
from backend.services.earthquery.schema import EarthQuerySpec, TemporalSpec

def test_sensor_selector_cloudy_prefers_sar():
    selector = AutonomousSensorSelector()
    spec = EarthQuerySpec(
        intent="flood_detection",
        phenomenon="flooding",
        target_objects=[],
        required_operations=["water_detection"],
        preferred_modalities=["optical", "sar"]
    )
    # High cloud contamination (45%)
    decision = selector.select_sensor(
        spec,
        optical_available=True,
        sar_available=True,
        optical_cloud_coverage=45.0
    )
    
    assert decision.primary == "sar"
    assert "sar" in decision.selected
    assert "cloud" in decision.reason.lower() or "penetration" in decision.reason.lower()

def test_sensor_selector_clean_optical():
    selector = AutonomousSensorSelector()
    spec = EarthQuerySpec(
        intent="building_count",
        phenomenon=None,
        target_objects=["buildings"],
        required_operations=["building_detection"],
        preferred_modalities=["optical"]
    )
    decision = selector.select_sensor(
        spec,
        optical_available=True,
        sar_available=True,
        optical_cloud_coverage=2.0
    )
    
    assert decision.primary == "optical"
    assert "optical" in decision.selected

def test_sensor_selector_both_for_multimodal_flood():
    selector = AutonomousSensorSelector()
    spec = EarthQuerySpec(
        intent="flood_impact_change",
        phenomenon="flooding",
        target_objects=["buildings"],
        required_operations=["flood_detection", "building_detection", "spatial_intersection"],
        preferred_modalities=["optical", "sar"]
    )
    # Low clouds, but task benefits from both SAR (water) and optical (building context)
    decision = selector.select_sensor(
        spec,
        optical_available=True,
        sar_available=True,
        optical_cloud_coverage=8.0
    )
    
    assert "optical" in decision.selected
    assert "sar" in decision.selected
    assert decision.optical_suitability > 0.5
    assert decision.sar_suitability > 0.5
