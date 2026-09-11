"""Pull SMALL real subsets of LEVIR-CD, VRSBench, and RSVQA for evaluation
(PRD §46 — never invent benchmark numbers; use real data even if small).

This intentionally does NOT download the full archives (LEVIR-CD alone is
~6.3GB and research-license-only). It streams a handful of examples from
each dataset's Hugging Face Hub mirror and writes them to
`datasets/<name>/real_subset/` alongside a `SOURCE.json` provenance record.

Usage:
    .venv/bin/python scripts/eval/fetch_real_subsets.py --n 12
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = REPO_ROOT / "datasets"

# (local_dir_name, HF dataset repo id, split, license note)
SOURCES = [
    ("levir-cd", "blanchon/LEVIR_CDPlus", "test",
     "Research/academic use only — LEVIR-CD/LEVIR-CD+ original terms. Do not "
     "use these images/labels in a commercial deployment."),
    ("vrsbench", "xiang709/VRSBench", "validation",
     "VRSBench release terms — verify current license before commercial use."),
    ("rsvqa", "dmarsili/RSVQA-LR-2k", "validation",
     "Unofficial 2k-sample mirror of RSVQA-LR validation split — "
     "research/academic use; verify against the original RSVQA Zenodo terms."),
]


def fetch_one(name: str, repo_id: str, split: str, license_note: str, n: int) -> dict:
    from datasets import load_dataset

    out_dir = DATASETS_DIR / name / "real_subset"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []

    print(f"[fetch] streaming {n} examples from {repo_id} ({split}) ...")
    try:
        ds = load_dataset(repo_id, split=split, streaming=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[fetch] FAILED for {repo_id}: {exc}", file=sys.stderr)
        return {"repo_id": repo_id, "status": "failed", "error": str(exc)}

    count = 0
    try:
        for row in ds:
            if count >= n:
                break
            record = {"index": count}
            for key, val in row.items():
                if hasattr(val, "save"):  # PIL Image
                    fname = f"{count:03d}_{key}.png"
                    val.convert("RGB").save(out_dir / fname)
                    record[key] = fname
                elif isinstance(val, (str, int, float, bool)) or val is None:
                    record[key] = val
                else:
                    record[key] = str(val)[:200]
            manifest.append(record)
            count += 1
    except Exception as exc:  # noqa: BLE001 — malformed upstream mirror, don't fabricate data
        print(f"[fetch] FAILED mid-stream for {repo_id} after {count} examples: {exc}", file=sys.stderr)
        if count == 0:
            return {"repo_id": repo_id, "status": "failed", "error": str(exc)}
        # keep whatever we got before the mirror broke

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[fetch] wrote {count} examples -> {out_dir}")
    return {"repo_id": repo_id, "split": split, "status": "ok",
            "n_fetched": count, "license_note": license_note,
            "local_dir": str(out_dir.relative_to(REPO_ROOT))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=12,
                         help="examples per dataset (keep small — real subset, not full archive)")
    parser.add_argument("--only", choices=[s[0] for s in SOURCES], default=None)
    args = parser.parse_args()

    results = []
    for name, repo_id, split, note in SOURCES:
        if args.only and name != args.only:
            continue
        results.append(fetch_one(name, repo_id, split, note, args.n))

    summary_path = DATASETS_DIR / "REAL_SUBSET_PROVENANCE.json"
    summary_path.write_text(json.dumps(results, indent=2))
    print(f"\n[fetch] provenance written -> {summary_path}")
    for r in results:
        status = r.get("status")
        print(f"  - {r['repo_id']}: {status} ({r.get('n_fetched', 0)} examples)")


if __name__ == "__main__":
    main()
