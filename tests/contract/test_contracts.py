"""§13.5 contract tests — §13.4 signatures and schema-valid outputs."""
import inspect

from backend.agents import change as change_mod
from backend.agents import multimodal as mm_mod
from backend.agents import perception as perc_mod


def test_answer_question_signature():
    sig = inspect.signature(perc_mod.answer_question)
    params = list(sig.parameters)
    assert params[0] == "image" and params[1] == "question"


def test_detect_change_signature():
    sig = inspect.signature(change_mod.detect_change)
    params = list(sig.parameters)
    assert params[0] == "image_before" and params[1] == "image_after"


def test_predict_multimodal_signature():
    sig = inspect.signature(mm_mod.predict_multimodal)
    params = list(sig.parameters)
    assert params[0] == "optical_image" and params[1] == "sar_image"


def test_answer_question_output_schema(optical_pair):
    out = perc_mod.answer_question(optical_pair["optical_before"],
                                   "What is visible in this image?")
    assert {"answer", "confidence", "evidence", "spatial_reference"} <= set(out)
    assert 0.0 <= out["confidence"] <= 1.0


def test_detect_change_output_schema(optical_pair):
    out = change_mod.detect_change(optical_pair["optical_before"],
                                   optical_pair["optical_after"])
    assert {"change_mask_path", "change_geojson", "statistics", "metadata"} <= set(out)


def test_predict_multimodal_single_sensor_passthrough(optical_pair):
    out = mm_mod.predict_multimodal(optical_pair["optical_before"], None)
    assert out["metadata"]["fusion_performed"] is False
    assert out["confidence"] == out["evidence"]["optical"]["reliability"]
    both = mm_mod.predict_multimodal(optical_pair["optical_before"],
                                     optical_pair["sar_after"])
    assert both["metadata"]["fusion_performed"] is True
    assert {"prediction", "confidence", "evidence", "metadata"} <= set(both)
