"""BigEarthNet-style multimodal dataset access (training-time only, §13.2/§13.3).

Two sources:
  * "bigearthnet" — real BigEarthNet v2.0 patches from data/bigearthnet/
    (user-downloaded; never committed). Pairs Sentinel-2 + Sentinel-1 patches
    by patch id; labels are the 19-class nomenclature mapped to 3 coarse
    classes (vegetation / water / other) for the fusion smoke task.
  * "synthetic"  — deterministic BigEarthNet-shaped patches generated locally
    (4-band optical reflectance + 2-band SAR dB + coarse label). Used for the
    runnable-without-download path required by FR-8 AC1 and CI smoke tests.
    These are NOT benchmark data; every metric produced from them is labeled
    synthetic-subset smoke metrics (PRD §17 hard rule).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

MODULE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = MODULE_DIR / "data" / "bigearthnet"

CLASSES = ["vegetation", "water", "other"]
N_CLASSES = len(CLASSES)

# BigEarthNet 19-class nomenclature → coarse 3-class mapping (documented
# simplification for the fusion smoke task; keep full labels for real runs).
COARSE_MAP = {
    "Agriculture": "vegetation", "Altitude open cover": "vegetation",
    "Closed forest": "vegetation", "Open forest": "vegetation",
    "Herbaceous vegetation": "vegetation", "Permanent water": "water",
    "Inland wetlands": "water", "Marine coastal waters": "water",
    "Wetlands": "water", "Rivers": "water", "Lakes": "water",
}


def coarse_label(fine_labels: list[str]) -> str:
    for f in fine_labels:
        if f in COARSE_MAP:
            return COARSE_MAP[f]
    return "other"


def synthetic_patch(seed: int, size: int = 64) -> dict:
    """One deterministic labeled patch: optical (4, H, W) reflectance +
    SAR (2, H, W) dB. Signal is consistent across sensors so a fusion model
    can actually learn (optical NDVI-like contrast + SAR VV contrast agree).
    """
    rng = np.random.default_rng(seed)
    cls_idx = seed % N_CLASSES
    h = w = size
    if CLASSES[cls_idx] == "vegetation":
        optical = np.stack([
            rng.normal(0.08, 0.01, (h, w)), rng.normal(0.11, 0.01, (h, w)),
            rng.normal(0.06, 0.008, (h, w)), rng.normal(0.42, 0.03, (h, w)),
        ]).astype("float32")
        vv = rng.normal(-11.0, 1.2, (h, w))
    elif CLASSES[cls_idx] == "water":
        optical = np.stack([
            rng.normal(0.14, 0.01, (h, w)), rng.normal(0.15, 0.01, (h, w)),
            rng.normal(0.08, 0.008, (h, w)), rng.normal(0.04, 0.006, (h, w)),
        ]).astype("float32")
        vv = rng.normal(-21.0, 1.2, (h, w))
    else:  # other: bare / built
        optical = np.stack([
            rng.normal(0.17, 0.015, (h, w)), rng.normal(0.18, 0.015, (h, w)),
            rng.normal(0.19, 0.015, (h, w)), rng.normal(0.20, 0.02, (h, w)),
        ]).astype("float32")
        vv = rng.normal(-15.5, 1.4, (h, w))
    vh = vv - rng.normal(7.5, 0.8, (h, w))
    sar = np.stack([vv, vh]).astype("float32")
    return {"optical": np.clip(optical, 0, 1), "sar": sar, "label": cls_idx,
            "class_name": CLASSES[cls_idx]}


def synthetic_split(n: int, seed0: int = 0) -> list[dict]:
    return [synthetic_patch(seed0 + i) for i in range(n)]


def load_bigearthnet(limit: int = 500) -> list[dict]:
    """Load real BigEarthNet v2 patch pairs from data/bigearthnet/.

    Expects the extracted layout:
      data/bigearthnet/BigEarthNet-v1.0/<patch_id>.tif        (S2, 12 band)
      data/bigearthnet/s1/<patch_id>_VH.tif, _VV.tif          (S1)
      data/bigearthnet/labels/<patch_id>.json                 (labels json)
    Patches missing either sensor are skipped (single-sensor patches cannot
    train the fusion model).
    """
    import rasterio
    patches = []
    s2_dir = DATA_DIR / "BigEarthNet-v1.0"
    s1_dir = DATA_DIR / "s1"
    label_dir = DATA_DIR / "labels"
    if not s2_dir.exists():
        raise FileNotFoundError(
            f"BigEarthNet not found under {DATA_DIR}. Download it per "
            "BIGEARTHNET_README.md first, or use --source synthetic.")
    ids = sorted(p.stem for p in s2_dir.glob("*.tif"))[:limit]
    for pid in ids:
        s1_vh, s1_vv = s1_dir / f"{pid}_VH.tif", s1_dir / f"{pid}_VV.tif"
        lab = label_dir / f"{pid}.json"
        if not (s1_vh.exists() and s1_vv.exists() and lab.exists()):
            continue
        try:
            with rasterio.open(s2_dir / f"{pid}.tif") as s2:
                optical = s2.read().astype("float32") / 10000.0
            sar_parts = []
            for p in (s1_vv, s1_vh):
                with rasterio.open(p) as s1:
                    sar_parts.append(s1.read(1).astype("float32"))
            fine = json.loads(lab.read_text(encoding="utf-8")).get("labels", [])
            patches.append({
                "optical": np.clip(optical, 0, 1),
                "sar": np.stack(sar_parts),
                "label": CLASSES.index(coarse_label(fine)),
                "class_name": coarse_label(fine),
                "patch_id": pid,
            })
        except Exception:
            continue
    return patches
