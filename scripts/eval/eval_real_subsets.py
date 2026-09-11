"""Evaluate the pipeline on the SMALL real benchmark subsets pulled by
`fetch_real_subsets.py` (PRD §46 — no invented benchmark numbers).

Two honest caveats up front, written into every result file so nobody
mistakes these for full-benchmark SOTA numbers:

1. Sample size is intentionally small (~12 examples per dataset) — these are
   directional smoke numbers on real data, not statistically powered
   benchmark results. Re-run with the full split for a reportable figure.
2. LEVIR-CD/LEVIR-CD+ is a *building* change-detection benchmark, but this
   repo's production `detect_change()` (backend/geospatial/change.py) is an
   NDVI *vegetation* loss/gain detector by design (PRD §10.2) and expects
   georeferenced multi-band rasters, not plain RGB PNGs. Running that
   function on LEVIR-CD would silently misapply a vegetation index to
   building imagery. Instead we evaluate a domain-appropriate generic
   grayscale-magnitude-diff baseline directly against the LEVIR-CD change
   masks, and report it as a generic baseline — not as production pipeline
   accuracy on a benchmark it isn't built for.

RSVQA/VRSBench: run through `backend/agents/perception.answer_question`
(the same single-image VQA path the app uses) and score exact/partial
string match against the ground-truth answers, which is the standard
RSVQA metric for short categorical answers.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from backend.agents import perception  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"
DATASETS = REPO / "datasets"


def eval_levir_cd(n_limit: int | None = None) -> dict:
    d = DATASETS / "levir-cd" / "real_subset"
    manifest = json.loads((d / "manifest.json").read_text())
    if n_limit:
        manifest = manifest[:n_limit]

    ious, f1s, precisions, recalls = [], [], [], []
    for row in manifest:
        img1 = np.asarray(Image.open(d / row["image1"]).convert("L"), dtype="float32")
        img2 = np.asarray(Image.open(d / row["image2"]).convert("L"), dtype="float32")
        mask = np.asarray(Image.open(d / row["mask"]).convert("L")) > 0

        diff = np.abs(img2 - img1)
        # Otsu-ish simple threshold: mean + 1 std, generic magnitude-diff baseline
        thresh = diff.mean() + diff.std()
        pred = diff > thresh

        tp = int((pred & mask).sum())
        fp = int((pred & ~mask).sum())
        fn = int((~pred & mask).sum())
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        iou = tp / max(1, tp + fp + fn)
        f1 = 2 * precision * recall / max(1e-8, precision + recall)
        ious.append(iou); f1s.append(f1); precisions.append(precision); recalls.append(recall)

    return {
        "dataset": "LEVIR-CD+ (blanchon/LEVIR_CDPlus)",
        "n_examples": len(manifest),
        "metrics_mean": {
            "IoU": round(float(np.mean(ious)), 4),
            "F1": round(float(np.mean(f1s)), 4),
            "precision": round(float(np.mean(precisions)), 4),
            "recall": round(float(np.mean(recalls)), 4),
        },
        "method": "generic grayscale mean+1std magnitude-diff baseline "
                   "(NOT the production NDVI vegetation change.detect_change — "
                   "domain mismatch: LEVIR-CD is building change, production "
                   "pipeline targets vegetation index change per PRD §10.2)",
        "license_note": "LEVIR-CD/LEVIR-CD+ — research/academic use only",
    }


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower().strip() if ch.isalnum() or ch.isspace())


def eval_rsvqa(n_limit: int | None = None) -> dict:
    d = DATASETS / "rsvqa" / "real_subset"
    manifest = json.loads((d / "manifest.json").read_text())
    if n_limit:
        manifest = manifest[:n_limit]

    correct, results = 0, []
    for row in manifest:
        img_path = str(d / row["image"])
        try:
            out = perception.answer_question(img_path, row["question"])
            pred = str(out.get("answer", "")).strip()
        except Exception as exc:  # noqa: BLE001
            pred = f"<error: {exc}>"
        gt = str(row["answer"]).strip()
        is_correct = _norm(gt) in _norm(pred) or _norm(pred) in _norm(gt)
        correct += int(is_correct)
        results.append({"question": row["question"], "gt": gt, "pred": pred, "correct": is_correct})

    n = len(manifest)
    return {
        "dataset": "RSVQA-LR (dmarsili/RSVQA-LR-2k, unofficial mirror)",
        "n_examples": n,
        "accuracy_percent": round(100.0 * correct / max(1, n), 2),
        "method": "backend.agents.perception.answer_question (same VQA path used in production)",
        "per_example": results,
        "license_note": "Unofficial mirror of RSVQA-LR — research/academic use; "
                         "verify against original RSVQA Zenodo terms",
    }


def eval_vrsbench(n_limit: int | None = None) -> dict:
    d = DATASETS / "vrsbench" / "real_subset"
    manifest = json.loads((d / "manifest.json").read_text())
    if n_limit:
        manifest = manifest[:n_limit]

    correct, total, results = 0, 0, []
    for row in manifest:
        img_path = str(d / row["image"])
        try:
            qa_pairs = eval(row["qa_pairs"])  # noqa: S307 — trusted local dataset dump, python-repr literal
        except Exception:
            qa_pairs = []
        for qa in qa_pairs[:3]:  # cap per-image questions to keep this a smoke pass
            try:
                out = perception.answer_question(img_path, qa["question"])
                pred = str(out.get("answer", "")).strip()
            except Exception as exc:  # noqa: BLE001
                pred = f"<error: {exc}>"
            gt = str(qa["answer"]).strip()
            is_correct = _norm(gt) in _norm(pred) or _norm(pred) in _norm(gt)
            correct += int(is_correct)
            total += 1
            results.append({"question": qa["question"], "gt": gt, "pred": pred, "correct": is_correct})

    return {
        "dataset": "VRSBench (xiang709/VRSBench, validation split)",
        "n_images": len(manifest),
        "n_qa_evaluated": total,
        "accuracy_percent": round(100.0 * correct / max(1, total), 2),
        "method": "backend.agents.perception.answer_question (same VQA path used in production)",
        "per_example": results,
        "license_note": "VRSBench release terms — verify before commercial use",
    }


def main() -> None:
    run_date = datetime.now(timezone.utc).date().isoformat()
    caveat = (
        "SMALL real-data smoke pass (~12 examples) — directional signal only, "
        "not a statistically powered benchmark result. See module docstring "
        "for the LEVIR-CD domain-mismatch caveat. PRD §46: real data, honestly scoped."
    )

    levir = eval_levir_cd()
    rsvqa = eval_rsvqa()
    vrsbench = eval_vrsbench()

    for name, result in [("eval_levir_cd_real", levir),
                          ("eval_rsvqa_real", rsvqa),
                          ("eval_vrsbench_real", vrsbench)]:
        result["run_date"] = run_date
        result["caveat"] = caveat
        RESULTS_DIR.mkdir(exist_ok=True)
        (RESULTS_DIR / f"{name}.json").write_text(json.dumps(result, indent=2))
        print(f"\n=== {name} ===")
        printable = {k: v for k, v in result.items() if k != "per_example"}
        print(json.dumps(printable, indent=2))


if __name__ == "__main__":
    main()
