"""Centralized model loading — one place to swap models (PRD §13.1).

Every loader probes for its engine and local weights and returns `None`
(with a logged reason) when unavailable; agents then use their documented
deterministic fallbacks. Checkpoints are NEVER downloaded at runtime — they
are fetched by scripts/fetch_models.sh (PRD §7.5/§19).
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

import yaml

log = logging.getLogger("satquery.models")

_REGISTRY_PATH = Path(__file__).resolve().parent / "registry.yaml"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _weights_dir(entry: dict) -> Path:
    base = entry.get("weights", "")
    if os.path.isabs(base):
        return Path(base)
    return _REPO_ROOT / "models" / "checkpoints" / base


def gpu_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


@lru_cache(maxsize=1)
def registry() -> dict:
    with open(_REGISTRY_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=None)
def load_vlm():
    """Single-image VQA/captioning model, or None. Looks for a local
    transformers vision-language checkpoint under checkpoints/vlm/."""
    entry = registry()["models"]["perception_vlm"]
    d = _weights_dir({"weights": "vlm/"})
    if not d.exists() or not any(d.iterdir()):
        return None, f"no local weights at {d}"
    try:
        from transformers import AutoProcessor, AutoModelForVision2Seq  # type: ignore
        processor = AutoProcessor.from_pretrained(d)
        model = AutoModelForVision2Seq.from_pretrained(d)
        model.eval()
        return {"processor": processor, "model": model, "dir": d}, None
    except Exception as exc:  # never crash the backend on model load (§7.2)
        return None, f"vlm_load_failed:{exc}"


@lru_cache(maxsize=None)
def load_detector():
    """Grounding DINO via transformers, or None."""
    entry = registry()["models"]["grounding_dino"]
    d = _weights_dir({"weights": "grounding_dino/"})
    if not d.exists() or not any(d.iterdir()):
        return None, f"no local weights at {d}"
    try:
        from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection  # type: ignore
        processor = AutoProcessor.from_pretrained(d)
        model = AutoModelForZeroShotObjectDetection.from_pretrained(d)
        model.eval()
        return {"processor": processor, "model": model}, None
    except Exception as exc:
        return None, f"detector_load_failed:{exc}"


@lru_cache(maxsize=None)
def load_change_model():
    """In-house Siamese U-Net checkpoint, or None (falls back to index-delta)."""
    d = _weights_dir({"weights": "change_detector/siamese_unet_levircd.pt"})
    if not d.exists():
        return None, f"no checkpoint at {d}"
    try:
        import torch  # type: ignore
        state = torch.load(d, map_location="cpu")
        return {"state_dict": state}, None
    except Exception as exc:
        return None, f"change_model_load_failed:{exc}"


@lru_cache(maxsize=None)
def load_embedding_model():
    """sentence-transformers embedding model, or None (TF-IDF fallback)."""
    d = _weights_dir({"weights": "embeddings/"})
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        source = str(d) if d.exists() and any(d.iterdir()) else "sentence-transformers/all-MiniLM-L6-v2"
        return SentenceTransformer(source), None
    except Exception as exc:
        return None, f"embedding_model_unavailable:{exc}"


def capabilities() -> dict:
    """Startup capability report, surfaced via GET /api/v1/health (§19)."""
    vlm, vlm_reason = load_vlm()
    det, det_reason = load_detector()
    chg, chg_reason = load_change_model()
    emb, emb_reason = load_embedding_model()
    return {
        "gpu_available": gpu_available(),
        "perception_vlm": bool(vlm),
        "grounding_dino": bool(det),
        "change_detector": bool(chg),
        "embedding_model": bool(emb),
        "fallback_reasons": {k: v for k, v in {
            "perception_vlm": vlm_reason, "grounding_dino": det_reason,
            "change_detector": chg_reason, "embedding_model": emb_reason,
        }.items() if v},
    }
