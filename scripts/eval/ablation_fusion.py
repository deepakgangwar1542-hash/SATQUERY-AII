"""§17.1 mandatory ablation: Optical vs SAR vs Fusion accuracy.

Writes scripts/eval/results/ablation_fusion.json with the exact table, script,
data source, and run date — no fabricated numbers (PRD §17 hard rule).

Usage:
  python scripts/eval/ablation_fusion.py --source synthetic --n 900
  python scripts/eval/ablation_fusion.py --source bigearthnet --n 500
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bigearthnet_module"))

from src.dataset import load_bigearthnet, synthetic_split  # noqa: E402
from src.model import FusionModel  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["synthetic", "bigearthnet"], default="synthetic")
    ap.add_argument("--n", type=int, default=900)
    args = ap.parse_args()

    patches = (load_bigearthnet(args.n) if args.source == "bigearthnet"
               else synthetic_split(args.n))
    model = FusionModel()
    model.fit(patches[: int(len(patches) * 0.75)])
    held_out = patches[int(len(patches) * 0.75):] or patches

    table = {
        "optical_only": round(100 * model.evaluate(held_out, "optical"), 2),
        "sar_only": round(100 * model.evaluate(held_out, "sar"), 2),
        "fusion": round(100 * model.evaluate(held_out, "fusion"), 2),
    }
    out = {
        "accuracy_percent": table,
        "script": "scripts/eval/ablation_fusion.py",
        "data_split": f"{args.source}: {len(held_out)} held-out patches of {len(patches)}",
        "run_date": datetime.now(timezone.utc).date().isoformat(),
        "caveat": ("synthetic-subset smoke metrics — NOT benchmark figures; "
                   "re-run with --source bigearthnet on a real download before "
                   "quoting any number (PRD §17)")
        if args.source == "synthetic" else "BigEarthNet-subset ablation",
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "ablation_fusion.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
