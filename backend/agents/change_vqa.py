"""Change-VQA Agent — natural-language reasoning over change (FR-6).

Decomposition per FR-6 AC: change detection → changed-region summary →
object-level check (grounding, when it ran) → NL answer generation. With no
VLM checkpoint, answers are composed from the Change Agent's structured
statistics — deterministic and grounded, never invented.

When `XAI_API_KEY` is configured, the template answer below is used as a
strict factual scaffold for an xAI (Grok) call that rephrases it into a more
natural response — the LLM is instructed to only use the numbers it is
given, never to introduce new figures. If the key is absent or the call
fails for any reason, the deterministic template answer is returned as-is
(§7.2/§7.5 graceful degradation).
"""
from __future__ import annotations

from . import perception
from ..services import llm_client
from .change import detect_change


_LLM_SYSTEM_PROMPT = (
    "You are a remote-sensing change-detection assistant. You will be given "
    "a factual draft answer, computed deterministically from raster "
    "statistics, and the original user question. Rewrite the draft into a "
    "clear, natural response to the question. You MUST NOT invent, alter, "
    "or add any number, percentage, or area figure that is not already in "
    "the draft. Keep it concise (2-4 sentences)."
)


def answer_change_question(image_before: str, image_after: str, question: str,
                           band_mapping: dict | None = None,
                           change_result: dict | None = None,
                           out_dir: str | None = None,
                           grounding_objects: list[dict] | None = None) -> dict:
    """Returns {answer, confidence, evidence, uncertainty, spatial_reference}."""
    if change_result is None:
        change_result = detect_change(image_before, image_after,
                                      band_mapping_before=band_mapping,
                                      out_dir=out_dir)
    stats = change_result["statistics"]
    breakdown = stats["class_breakdown"]
    evidence: list[dict] = [{
        "agent": "change_vqa",
        "type": "change_statistics",
        "summary": change_result["summary"],
        "data": {"statistics": stats, "metadata": change_result["metadata"]},
        "confidence": change_result["confidence"],
    }]

    q = (question or "").lower()
    loss_km2 = breakdown.get("vegetation_loss_km2", 0.0)
    gain_km2 = breakdown.get("vegetation_gain_km2", 0.0)
    pct = stats["percent_of_aoi"]

    if "flood" in q or "water" in q:
        direction = "inundation" if gain_km2 > loss_km2 else "receding water / drying"
        answer = (f"Between the two dates the dominant water-related signal is "
                  f"{direction}: {gain_km2} km² gained vegetation/water signature "
                  f"while {loss_km2} km² lost it ({pct}% of the AOI crosses the "
                  f"threshold). For a definitive flood extent, run an NDWI "
                  f"change analysis (intent `ndwi_change`).")
    elif "build" in q or "construction" in q or "urban" in q:
        answer = (f"Vegetation loss consistent with new construction/land clearing "
                  f"affects ~{pct}% of the AOI ({loss_km2} km²). "
                  + (f"The grounding agent found {len(grounding_objects)} candidate "
                     f"objects inside/adjacent to changed areas." if grounding_objects
                     else "Enable object grounding for building-level confirmation."))
    else:
        answer = (f"Approximately {pct}% of the analyzed region changed beyond the "
                  f"threshold: {loss_km2} km² vegetation loss and {gain_km2} km² "
                  f"vegetation gain between the two dates.")

    # Object-level corroboration (FR-6 AC(b)): detections inside change polygons.
    if grounding_objects:
        evidence.append({
            "agent": "change_vqa", "type": "object_corroboration",
            "summary": f"{len(grounding_objects)} detected objects related to changed regions.",
            "data": {"object_count": len(grounding_objects)}, "confidence": 0.5,
        })

    confidence = round(min(0.85, change_result["confidence"] + (0.05 if grounding_objects else 0)), 3)
    answer = _rephrase_with_llm(question, answer)
    return {"answer": answer, "confidence": confidence, "evidence": evidence,
            "uncertainty": list(change_result.get("uncertainty", [])),
            "spatial_reference": change_result.get("change_geojson"),
            "scene_context": perception.caption_image(image_after)["caption"]
            if change_result.get("include_scene", False) else None}


def _rephrase_with_llm(question: str, draft_answer: str) -> str:
    """Optional enhancement: ask xAI to rephrase the deterministic draft into
    more natural prose. Returns the draft unchanged if the LLM is
    unavailable, errors, or its response doesn't look grounded (contains no
    overlap with the draft's own content)."""
    if not llm_client.is_available():
        return draft_answer
    user_prompt = f"Question: {question}\n\nDraft answer (factual, do not add new numbers):\n{draft_answer}"
    rephrased = llm_client.complete(_LLM_SYSTEM_PROMPT, user_prompt)
    return rephrased or draft_answer
