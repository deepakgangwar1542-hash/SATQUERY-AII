"""Write demo/sample data: a bi-temporal optical+SAR synthetic scene pair with
a known vegetation-loss patch, plus its ground-truth change mask.

Usage: python scripts/make_sample_data.py [--size 512]
Output: datasets/samples/{optical_before,optical_after,sar_before,sar_after,
ground_truth_change}.tif
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from backend.utils import synth  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=512)
    args = ap.parse_args()

    out_dir = REPO / "datasets" / "samples"
    paths = synth.write_pair(str(out_dir), size=args.size)

    # Ground-truth change mask from the same geometry synth.write_pair uses.
    size = args.size
    changed_frac = 0.25
    h0, h1 = int(size * 0.1), int(size * (0.1 + changed_frac))
    w0, w1 = int(size * 0.05), int(size * 0.45)
    gt = np.zeros((size, size), dtype="uint8")
    gt[h0:h1, w0:w1] = 1
    gt_path = out_dir / "ground_truth_change.tif"
    with rasterio.open(paths["optical_before"]) as src:
        profile = src.profile.copy()
        for k in ("blockxsize", "blockysize", "tiled", "interleave", "count"):
            profile.pop(k, None)
        profile.update(driver="GTiff", dtype="uint8", count=1, nodata=0,
                       compress="deflate")
    with rasterio.open(gt_path, "w", **profile) as dst:
        dst.write(gt, 1)

    print("wrote:")
    for k, v in {**paths, "ground_truth": str(gt_path)}.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
