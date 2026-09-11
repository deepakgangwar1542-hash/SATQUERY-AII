"""Unit tests for the RAG SOP vector store."""
from backend.rag.sop_store import CURATED_SOPS, retrieve_sops


def test_curated_sops_structure():
    assert len(CURATED_SOPS) >= 4
    for sop in CURATED_SOPS:
        assert "sop_id" in sop
        assert "title" in sop
        assert "authority" in sop
        assert len(sop["action_protocols"]) >= 2


def test_retrieve_vegetation_sop():
    results = retrieve_sops("areas where vegetation decreased by more than 20%", top_k=2)
    assert len(results) > 0
    top = results[0]
    assert "VEG" in top["sop_id"]
    assert top["relevance_score"] > 0.3
    assert len(top["action_protocols"]) > 0


def test_retrieve_flood_sop():
    results = retrieve_sops("identify surface water extent and flooded zones", top_k=2)
    assert len(results) > 0
    top = results[0]
    assert "FLD" in top["sop_id"]
    assert "UN-SPIDER" in top["authority"] or "FEMA" in top["authority"]


def test_retrieve_tank_infrastructure_sop():
    results = retrieve_sops("detect industrial storage tanks and facilities", top_k=2)
    assert len(results) > 0
    top = results[0]
    assert "INF" in top["sop_id"]
