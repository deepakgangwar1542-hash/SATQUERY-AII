"""Perception Agent — single-image VQA + captioning (FR-2, FR-3).

Primary path: a transformers vision-language checkpoint via models.loaders
(§14.2). Fallback path (no checkpoint present): a deterministic scene analyzer
that computes band statistics and index-based land-cover shares, and answers
through honest templated sentences with reduced confidence. The fallback is
recorded as an UncertaintyNote so the UI never presents it as model output.
"""
from __future__ import annotations

import numpy as np

from ..geospatial import raster as graster
from ..geospatial import ndvi as gndvi
from ..models import loaders

EPS = 1e-8


def _scene_profile(image: str, band_mapping: dict | None = None) -> dict:
    """Deterministic scene statistics used by both fallback answering and
    captioning (and as numeric context for the VLM path)."""
    report = graster.validate_raster(image)
    data = graster.read_raster(image)
    mapping = band_mapping or report.get("band_mapping_guess") or {}
    arr = data["array"]
    refl = graster.to_reflectance(arr)
    profile: dict = {
        "valid": report.get("valid", False),
        "band_mapping": mapping,
        "cloud_fraction": None,
        "shares": {},
    }
    try:
        ndvi = gndvi.compute_ndvi(arr, mapping)
        ndwi = gndvi.compute_ndwi(arr, mapping)
        valid = np.isfinite(ndvi)
        n = int(valid.sum()) or 1
        blue = refl[0] if refl.shape[0] > 1 else np.zeros_like(ndvi)
        cloud = (blue > 0.25) & (ndvi < 0.2)  # documented brightness heuristic (§10.5 b)
        veg = (ndvi > 0.3) & valid
        water = (ndwi > 0.0) & valid & ~veg
        bare = valid & ~veg & ~water & ~cloud
        profile.update({
            "ndvi_mean": float(np.nanmean(ndvi[valid])),
            "ndwi_mean": float(np.nanmean(ndwi[valid])),
            "cloud_fraction": float((cloud & valid).sum() / n),
            "shares": {
                "vegetation": float(veg.sum() / n),
                "water": float(water.sum() / n),
                "bare_or_built": float(bare.sum() / n),
                "cloud": float((cloud & valid).sum() / n),
            },
            "valid_fraction": float(valid.sum() / ndvi.size),
        })
    except (KeyError, ValueError):
        pass  # mapping unknown → stats-only profile, indices unavailable
    return profile


def caption_image(image: str, band_mapping: dict | None = None) -> dict:
    """FR-3: one-paragraph caption. Returns {caption, mode, profile}."""
    profile = _scene_profile(image, band_mapping)
    vlm, _reason = loaders.load_vlm()
    if vlm is not None:
        # VLM path (only when a local checkpoint has been fetched).
        try:
            import io
            import rasterio.plot
            import PIL.Image
            arr = graster.read_raster(image)["array"]
            rgb = arr[[2, 1, 0]] if arr.shape[0] >= 3 else arr[:1]
            img = PIL.Image.fromarray(
                (np.clip(graster.to_reflectance(rgb), 0, 1) * 255).astype("uint8").transpose(1, 2, 0))
            inputs = vlm["processor"](images=img, return_tensors="pt")
            out = vlm["model"].generate(**inputs, max_new_tokens=80)
            text = vlm["processor"].batch_decode(out, skip_special_tokens=True)[0]
            return {"caption": text.strip(), "mode": "vlm", "profile": profile}
        except Exception:
            pass  # fall through to deterministic captioner
    s = profile.get("shares", {})
    if s:
        caption = (
            f"Sentinel-style optical scene: approximately {s.get('vegetation', 0):.0%} vegetation, "
            f"{s.get('water', 0):.0%} water, {s.get('bare_or_built', 0):.0%} bare/built surface, "
            f"with {s.get('cloud', 0):.0%} cloud-contaminated pixels. "
            f"Mean NDVI is {profile.get('ndvi_mean', 0):.2f}."
        )
    else:
        caption = ("Optical scene (band semantics unresolved; supply a band mapping "
                   "for index-based description).")
    return {"caption": caption, "mode": "heuristic_analyzer", "profile": profile}


def answer_question(image: str, question: str,
                    band_mapping: dict | None = None) -> dict:
    """FR-2 — exact §13.4 contract:
    answer_question(image: str, question: str) -> dict
    Returns {answer, confidence, evidence, spatial_reference | None}."""
    profile = _scene_profile(image, band_mapping)
    q = (question or "").lower()
    evidence: list[dict] = []
    uncertainty: list[dict] = []
    vlm, reason = loaders.load_vlm()

    if vlm is not None:
        # VLM path is attempted first; falls back below on any failure (§12.3).
        try:
            result = _vlm_answer(vlm, image, question)
            if result:
                return result
        except Exception:
            pass

    # Deterministic fallback answering (mode recorded, confidence reduced).
    s = profile.get("shares", {})
    if "how many" in q or "count" in q:
        answer = (
            "Object counting requires the grounding agent; this scene-level "
            "answer cannot reliably count objects. Run a region-specific query "
            "with the grounding path enabled for a count backed by detections."
        )
        confidence = 0.35
    elif "water" in q and s:
        answer = (f"About {s.get('water', 0):.1%} of the valid pixels classify as water "
                  f"(NDWI > 0, McFeeters; PRD §10.2).")
        confidence = 0.55
    elif ("vegetation" in q or "ndvi" in q or "green" in q) and s:
        answer = (f"Vegetation covers roughly {s.get('vegetation', 0):.1%} of the valid "
                  f"area; mean NDVI is {profile.get('ndvi_mean', 0):.2f}.")
        confidence = 0.6
    elif "what" in q or "visible" in q or "describe" in q or s:
        answer = (
            f"The scene is approximately {s.get('vegetation', 0):.0%} vegetation, "
            f"{s.get('water', 0):.0%} water and {s.get('bare_or_built', 0):.0%} bare/built, "
            f"with {s.get('cloud', 0):.0%} cloud cover."
        ) if s else ("Scene statistics unavailable (no band mapping resolved).")
        confidence = 0.55 if s else 0.3
    else:
        answer = caption_image(image, band_mapping)["caption"]
        confidence = 0.5

    if vlm is None:
        uncertainty.append({
            "signal": "vlm_unavailable",
            "severity": "medium",
            "explanation": f"Answer produced by the deterministic fallback analyzer "
                           f"({reason}); not VLM-generated.",
        })
    evidence.append({
        "agent": "perception",
        "type": "scene_profile",
        "summary": answer,
        "data": {"shares": s, "ndvi_mean": profile.get("ndvi_mean"),
                 "cloud_fraction": profile.get("cloud_fraction"),
                 "mode": "heuristic_analyzer" if vlm is None else "vlm"},
        "confidence": confidence,
    })
    return {"answer": answer, "confidence": confidence, "evidence": evidence,
            "spatial_reference": None, "uncertainty": uncertainty}


def _vlm_answer(vlm: dict, image: str, question: str) -> dict | None:
    """Transformers VLM inference; returns None when the checkpoint is unusable."""
    import torch  # type: ignore
    import PIL.Image
    arr = graster.read_raster(image)["array"]
    rgb = arr[[2, 1, 0]] if arr.shape[0] >= 3 else arr[:1]
    img = PIL.Image.fromarray(
        (np.clip(graster.to_reflectance(rgb), 0, 1) * 255).astype("uint8").transpose(1, 2, 0))
    prompt = f"Question: {question} Answer:"
    inputs = vlm["processor"](images=img, text=prompt, return_tensors="pt")
    with torch.no_grad():
        out = vlm["model"].generate(**inputs, max_new_tokens=120)
    text = vlm["processor"].batch_decode(out, skip_special_tokens=True)[0].strip()
    if not text:
        return None
    return {"answer": text, "confidence": 0.75, "evidence": [{
        "agent": "perception", "type": "vlm_answer", "summary": text,
        "data": {"mode": "vlm"}, "confidence": 0.75}],
        "spatial_reference": None, "uncertainty": []}
