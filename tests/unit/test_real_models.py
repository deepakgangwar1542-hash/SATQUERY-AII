"""Tests for real Computer Vision & Remote Sensing model inference."""
from __future__ import annotations

import pytest
from backend.models import loaders
from backend.agents import grounding, change, multimodal, rag


def test_model_capabilities():
    caps = loaders.capabilities()
    assert isinstance(caps, dict)
    assert "gpu_available" in caps
    # All models should now be loaded with zero fallbacks
    assert caps["perception_vlm"] is True
    assert caps["grounding_dino"] is True
    assert caps["change_detector"] is True
    assert caps["embedding_model"] is True
    assert len(caps.get("fallback_reasons", {})) == 0


def test_real_perception_vlm(optical_pair):
    from backend.agents import perception
    res = perception.answer_question(optical_pair["optical_before"], "Is there vegetation in this scene?")
    assert res["evidence"][0]["data"]["mode"] == "vlm"
    assert res["confidence"] >= 0.8
    assert len(res["answer"]) > 0


def test_real_grounding_dino(optical_pair):
    res = grounding.ground_objects(optical_pair["optical_before"], "vegetation")
    assert res["mode"] == "grounding_dino"
    assert res["confidence"] >= 0.7
    assert len(res["objects"]) > 0
    # Check first detected object
    first = res["objects"][0]
    assert "bbox_pixel" in first
    assert len(first["bbox_pixel"]) == 4
    assert first["geometry_wgs84"] is not None
    assert first["geometry_wgs84"]["type"] in ("Polygon", "MultiPolygon")


def test_real_siamese_change_detection(optical_pair):
    res = change.detect_change(
        optical_pair["optical_before"],
        optical_pair["optical_after"],
    )
    assert res["metadata"]["model"] == "siamese_unet_levircd"
    assert res["metadata"]["mode"] == "neural_siamese"
    assert res["confidence"] >= 0.7
    assert "statistics" in res
    assert "class_breakdown" in res["statistics"]


def test_real_bigearthnet_multimodal_fusion(optical_pair):
    res = multimodal.predict_multimodal(
        optical_pair["optical_before"],
        optical_pair["sar_after"],
    )
    assert res["metadata"]["fusion_performed"] is True
    assert "ml_classification" in res["prediction"]
    assert res["prediction"]["ml_classification"] is not None
    assert "probabilities" in res["prediction"]["ml_classification"]


def test_real_dense_embedding_retrieval():
    res = rag.retrieve("vegetation index NDVI calculation", k=3)
    assert res["mode"] == "embeddings"
    assert len(res["passages"]) > 0
    assert res["passages"][0]["score"] > 0.3
