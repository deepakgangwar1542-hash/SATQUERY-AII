"""§12.4 confidence formula + FR-10 verifier tests."""
from backend.agents import verifier


def test_weights_sum_to_one():
    w = verifier.weights()
    keys = verifier.BREAKDOWN_KEYS
    assert abs(sum(w[k] for k in keys) - 1.0) < 1e-6
    assert all(w[k] >= 0 for k in keys)


def test_default_weights_match_prd():
    w = verifier.weights()
    assert w["model_confidence"] == 0.25
    assert w["evidence_agreement"] == 0.25
    assert w["sensor_reliability"] == 0.15
    assert w["data_quality"] == 0.15
    assert w["spatial_consistency"] == 0.10
    assert w["temporal_consistency"] == 0.10


def test_agreement_penalty_on_conflict():
    outputs = {
        "change_agent": {"statistics": {"class_breakdown": {
            "vegetation_loss_km2": 5.0, "vegetation_gain_km2": 0.0}}},
        "change_vqa": {"answer": "vegetation increased strongly"},
    }
    score, conflicts = verifier.evidence_agreement(outputs)
    assert score < 0.7 and conflicts


def test_compute_bounds_and_verdict():
    outputs = {
        "perception": {"confidence": 0.6, "scene_profile": {"cloud_fraction": 0.1}},
        "change_agent": {"confidence": 0.8, "statistics": {"class_breakdown": {
            "vegetation_loss_km2": 2.0, "vegetation_gain_km2": 0.0}}},
        "change_vqa": {"confidence": 0.7,
                       "answer": "vegetation loss of 2 km2 was detected"},
    }
    val = {"all_valid": True, "band_mapping_confidence": "high",
           "any_missing_nodata": False}
    out = verifier.compute(outputs, val, ["2025-06-01", "2025-09-01"])
    assert 0.0 <= out["final_confidence"] <= 1.0
    assert set(verifier.BREAKDOWN_KEYS) == set(out["confidence_breakdown"])
    assert out["consistency_verdict"] in ("CONSISTENT", "PARTIALLY_CONSISTENT",
                                          "CONFLICTING")
    assert isinstance(out["uncertainty"], list)
