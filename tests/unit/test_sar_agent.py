"""Unit tests for SAR Intelligence Agent."""
import os
import pytest
import numpy as np
from pathlib import Path
from backend.agents.sar import SARIntelligenceAgent

SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "datasets" / "samples"
SAR_BEFORE = SAMPLES_DIR / "sar_before.tif"
SAR_AFTER = SAMPLES_DIR / "sar_after.tif"

def test_sar_agent_bitemporal():
    if not SAR_BEFORE.exists() or not SAR_AFTER.exists():
        pytest.skip("SAR sample GeoTIFFs not found")
        
    agent = SARIntelligenceAgent()
    evidence = agent.analyze(
        image_path=str(SAR_AFTER),
        reference_image_path=str(SAR_BEFORE),
        operation="temporal_flood"
    )
    
    assert evidence.modality == "sar"
    assert evidence.confidence > 0.6
    assert "flood_change_percent" in evidence.metrics or "water_change_percent" in evidence.metrics
    assert len(evidence.limitations) > 0
    assert evidence.artifact_path is not None
    assert os.path.exists(evidence.artifact_path)

def test_sar_agent_single_scene():
    if not SAR_AFTER.exists():
        pytest.skip("SAR sample GeoTIFF not found")
        
    agent = SARIntelligenceAgent()
    evidence = agent.analyze(
        image_path=str(SAR_AFTER),
        operation="water_detection"
    )
    
    assert evidence.modality == "sar"
    assert "mean_backscatter_db" in evidence.metrics
    assert "enl" in evidence.metrics
    assert "water_pixel_fraction" in evidence.metrics
