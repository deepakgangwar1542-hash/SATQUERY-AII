# BigEarthNet Multimodal Module — README (PRD §13.3, FR-8)

Status: **runnable end-to-end in synthetic-subset mode** (no download needed);
real-BigEarthNet mode is wired but requires the dataset download below.

## What this module is

The optical+SAR fusion specialist, owned independently of `backend/`
(§13.2). The ONLY integration surface is:

```python
predict_multimodal(optical_image: str, sar_image: str) -> dict
# -> {prediction, confidence, evidence: {optical, sar}, metadata}
```

defined in `src/inference.py`, backed by the checkpoint in `checkpoints/`.
The backend never imports anything else from here (§13.2 module boundary).

## Dataset

- **Name/version:** BigEarthNet v2.0 (Sentinel-2 + Sentinel-1 reprocessed
  patches, 19-class nomenclature from CORINE).
- **License:** CDLA-Permissive-2.0 family — **verify the current terms at the
  official BigEarthNet site before redistributing anything derived from it.**
- **Subset used (real mode):** user-selected, `--n` patches; documented in
  `outputs/metrics.json` on every run.
- **Subset used (synthetic smoke mode):** 900 deterministic locally generated
  patches (no license constraints, NOT benchmark data).

### Downloading the real archive (optional, ~700 GB full / take a slice)

1. Register at the official BigEarthNet site (bigearth.net) for the S1+S2 v2
   archive links (hosted on blob storage).
2. Place under `bigearthnet_module/data/bigearthnet/`:
   - `BigEarthNet-v1.0/` — Sentinel-2 patch tifs
   - `s1/` — Sentinel-1 `*_VV.tif` / `*_VH.tif`
   - `labels/` — `<patch_id>.json` label files
3. Train: `python bigearthnet_module/src/train.py --source bigearthnet --n 500`

## Preprocessing

- Optical: DN/10000 → reflectance [0,1]; 4-band (B,G,R,NIR) feature view.
- SAR: dB clip to [−35, 5]; features = (VV mean, VH mean, VV−VH).
- Standardization stats stored inside the checkpoint.

## Training

```bash
# smoke (works offline, seconds):
python bigearthnet_module/src/train.py --source synthetic --n 900
# real subset (after download):
python bigearthnet_module/src/train.py --source bigearthnet --n 500
```

Artifacts: `checkpoints/fusion_model.joblib`, `outputs/metrics.json`.

## Adaptation results (FR-8 AC2 — real measured numbers, synthetic smoke subset)

Run of 2026-09-11 (`--source synthetic --n 900`, 675 train / 225 val):

| Mode | Val accuracy |
|---|---|
| Zero-shot NDVI-threshold heuristic (reference) | 1.0000 * |
| Adapted, optical only | 1.0000 |
| Adapted, SAR only | 0.6400 |
| Adapted, fusion | 1.0000 |

\* the synthetic classes are noise-separable in the optical features, so the
heuristic ceiling is also 1.0 — these numbers validate the PLUMBING, not the
science. They are smoke metrics under PRD §17's hard rule: do not quote them
as capability figures. Re-run on a real BigEarthNet subset for reportable
numbers (SAR-only landing far below optical/fusion is, however, directionally
consistent with real-data behavior).

## Backend wiring (optional)

To serve this module's predictions from the multimodal agent, the loader in
`backend/models/loaders.py` can point at this checkpoint; by default the
backend uses its own transparent reliability-fusion implementation (§10.5)
and reports the mode in `/api/v1/health` capabilities.
