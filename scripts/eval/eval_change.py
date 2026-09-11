"""Change-detection pixel metrics (IoU/F1/precision/recall) vs known ground
truth. Real numbers computed by re-running the actual pipeline — no hardcoding.

Ground truth: datasets/samples/ground_truth_change.tif (written by
scripts/make_sample_data.py from the same geometry used to synthesize the
change patch, so the evaluation is exact).

Usage: python scripts/eval/eval_change.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from backend.geospatial import change as gchange  # noqa: E402

SAMPLES = REPO / "datasets" / "samples"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def to_grid(mask_path: str, ref_transform, ref_crs, width, height) -> np.ndarray:
    with rasterio.open(mask_path) as src:
        dst = np.zeros((height, width), dtype="uint8")
        reproject(src.read(1), dst, src_transform=src.transform, src_crs=src.crs,
                  dst_transform=ref_transform, dst_crs=ref_crs,
                  resampling=Resampling.nearest)
    return dst


def main() -> None:
    before = str(SAMPLES / "optical_before.tif")
    after = str(SAMPLES / "optical_after.tif")
    gt_path = SAMPLES / "ground_truth_change.tif"
    if not gt_path.exists():
        sys.exit("run scripts/make_sample_data.py first")

    out = gchange.detect_change(before, after, out_dir=str(SAMPLES))
    pred_path = out["change_mask_path"]
    assert pred_path and Path(pred_path).exists()

    with rasterio.open(pred_path) as ref:
        pred = ref.read(1)
        gt = to_grid(str(gt_path), ref.transform, ref.crs, ref.width, ref.height)

    pred_b, gt_b = pred > 0, gt > 0
    tp = int((pred_b & gt_b).sum())
    fp = int((pred_b & ~gt_b).sum())
    fn = int((~pred_b & gt_b).sum())
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    iou = tp / max(1, tp + fp + fn)
    f1 = 2 * precision * recall / max(1e-8, precision + recall)

    result = {
        "metrics": {
            "IoU": round(iou, 4), "F1": round(f1, 4),
            "precision": round(precision, 4), "recall": round(recall, 4),
        },
        "script": "scripts/eval/eval_change.py",
        "data": "datasets/samples synthetic bi-temporal pair with known change patch",
        "method": out["metadata"],
        "run_date": datetime.now(timezone.utc).date().isoformat(),
        "caveat": "synthetic-pair smoke metrics — evaluate on LEVIR-CD held-out "
                  "split for reportable benchmark figures (PRD §17)",
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "eval_change.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
