"""Train the fusion model (FR-8 AC1).

Usage (from repo root, with the backend venv active):
  python bigearthnet_module/src/train.py --source synthetic --n 900
  python bigearthnet_module/src/train.py --source bigearthnet --n 500

Writes checkpoints/fusion_model.joblib + outputs/metrics.json. Before/after
adaptation comparison (FR-8 AC2): metrics.json always contains the zero-shot
baseline (majority-class + single-band NDVI-proxy heuristic) next to the
trained model's accuracy.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from src.dataset import CLASSES, load_bigearthnet, synthetic_split  # noqa: E402
from src.model import FusionModel  # noqa: E402
from src.preprocessing import dataset_matrix  # noqa: E402


def zero_shot_baseline(patches: list[dict], mode: str) -> float:
    """Honest zero-shot reference: threshold heuristic on band means —
    'NDVI-proxy > 0.25 → vegetation; NIR < 0.07 → water; else other'.
    No training; documents the lift adaptation actually buys."""
    correct = 0
    for p in patches:
        o = p["optical"]
        ndvi_proxy = (o[3].mean() - o[2].mean()) / (o[3].mean() + o[2].mean() + 1e-8)
        if mode == "sar":
            pred = 0  # SAR-only zero-shot: no reliable class rule → majority
        elif ndvi_proxy > 0.25:
            pred = CLASSES.index("vegetation")
        elif o[3].mean() < 0.07:
            pred = CLASSES.index("water")
        else:
            pred = CLASSES.index("other")
        correct += int(pred == p["label"])
    return correct / max(1, len(patches))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["synthetic", "bigearthnet"], default="synthetic")
    ap.add_argument("--n", type=int, default=900)
    ap.add_argument("--val-frac", type=float, default=0.25)
    args = ap.parse_args()

    patches = (load_bigearthnet(args.n) if args.source == "bigearthnet"
               else synthetic_split(args.n))
    if not patches:
        print("no patches loaded"); sys.exit(1)
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(patches))
    n_val = max(1, int(len(patches) * args.val_frac))
    val = [patches[i] for i in idx[:n_val]]
    train = [patches[i] for i in idx[n_val:]]

    model = FusionModel()
    train_metrics = model.fit(train)
    model.meta = {
        "source": args.source, "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_train": len(train), "n_val": len(val),
        "license_note": "synthetic data (no dataset license constraints)"
        if args.source == "synthetic"
        else "BigEarthNet v2.0 — CDLA-Permissive (verify current terms)",
    }

    ckpt_dir = MODULE_DIR / "checkpoints"
    ckpt_dir.mkdir(exist_ok=True)
    ckpt = ckpt_dir / "fusion_model.joblib"
    model.save(str(ckpt))

    metrics = {
        "run_at": model.meta["trained_at"],
        "source": args.source,
        "train": train_metrics,
        "val": {
            "zero_shot_ndvi_heuristic": round(zero_shot_baseline(val, "optical"), 4),
            "adapted_optical_only": round(model.evaluate(val, "optical"), 4),
            "adapted_sar_only": round(model.evaluate(val, "sar"), 4),
            "adapted_fusion": round(model.evaluate(val, "fusion"), 4),
        },
        "checkpoint": str(ckpt),
        "note": ("synthetic-subset smoke metrics — NOT benchmark numbers; "
                 "re-run with --source bigearthnet on a real download for "
                 "reportable figures (PRD §17)")
        if args.source == "synthetic" else "BigEarthNet-subset run",
    }
    out_dir = MODULE_DIR / "outputs"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
