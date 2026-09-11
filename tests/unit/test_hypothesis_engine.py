"""Unit tests for Hypothesis Engine."""
import pytest
from backend.agents.hypothesis_engine import HypothesisEngine
from backend.services.earthquery.schema import HypothesisEvaluation

def test_hypothesis_evaluation_flood():
    engine = HypothesisEngine()
    query = "What caused the major change in this region?"
    
    agent_outputs = {
        "sar_agent": {
            "water_share": 0.18,
            "new_flood_inundation_km2": 1.45,
        },
        "change_agent": {
            "statistics": {
                "percent_of_aoi": 12.5,
            }
        },
        "perception": {
            "scene_profile": {
                "cloud_fraction": 0.02
            }
        }
    }
    
    evidence_list = [
        {"id": "ev_sar_flood", "type": "water_change", "source": "sar", "confidence": 0.92},
        {"id": "ev_chg", "type": "temporal_change", "source": "optical", "confidence": 0.88}
    ]
    
    evaluation = engine.evaluate(query, evidence_list, agent_outputs)
    
    assert isinstance(evaluation, HypothesisEvaluation)
    assert len(evaluation.hypotheses) == 4
    assert "Flood" in evaluation.most_supported
    assert evaluation.hypotheses[0].support > 0.6
    assert "Most observational evidence supports" in evaluation.interpretation
    assert "causal certainty" in evaluation.interpretation.lower()

def test_hypothesis_evaluation_urban():
    engine = HypothesisEngine()
    query = "What caused the landscape transformation?"
    
    agent_outputs = {
        "sar_agent": {
            "water_share": 0.0,
            "new_flood_inundation_km2": 0.0,
        },
        "change_agent": {
            "statistics": {
                "percent_of_aoi": 8.0,
            }
        },
        "grounding": {
            "objects": [{"id": f"b_{i}"} for i in range(12)]
        },
        "perception": {
            "scene_profile": {
                "cloud_fraction": 0.01
            }
        }
    }
    
    evaluation = engine.evaluate(query, [], agent_outputs)
    assert "Urban" in evaluation.most_supported
    assert evaluation.hypotheses[0].support >= 0.70
