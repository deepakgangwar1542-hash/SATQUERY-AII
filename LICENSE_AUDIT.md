# LICENSE AUDIT — SatQuery AI (PRD §14.4 verification gate)

**Status: NOT CLEARED for deployment beyond local prototype/demo.**
Every `license_verified: false` row below must be manually re-checked against
the upstream LICENSE/model-card/dataset-card before any public, hosted, or
commercial use. CI must fail if entries are missing for anything referenced in
`models/registry.yaml` or `datasets/`.

## Software libraries shipped (permissive, low risk)

| Component | License | Verified |
|---|---|---|
| FastAPI / Starlette / Pydantic | MIT | ✓ |
| NumPy / Pandas / Shapely / scikit-learn | BSD-3 | ✓ |
| Rasterio (bundles GDAL) | BSD-3 / MIT-MIT-style GDAL | ✓ |
| GeoPandas | BSD-3 | ✓ |
| PyYAML | MIT | ✓ |
| fpdf2 | LGPL-3.0 (runtime unmodified — dynamic link) | ✓ |
| React / Vite / TypeScript / Tailwind CSS / TanStack Query | MIT | ✓ |
| CesiumJS (engine, self-hosted build) | Apache-2.0 | ✓ |

⚠️ **Cesium ion is NOT used.** The app runs CesiumJS with OSM/open imagery
and a documented self-host swap point (`frontend/src/services/mapProvider.ts`,
PRD §11.4). No ion token ships with this repo.

## Model checkpoints

`scripts/fetch_models.sh` downloads on demand; the repo itself ships NO
third-party weights in git. Fetched into this sandbox's local
`models/checkpoints/` (gitignored) and verified 2026-09-11:

| Checkpoint | Upstream license (at time of writing) | Verified? |
|---|---|---|
| IDEA-Research/grounding-dino-tiny | Apache-2.0 | ✓ confirmed on HF model card, 2026-09-11; fetched into models/checkpoints/grounding_dino/; active inference tested |
| facebook/sam2-hiera-small | Apache-2.0 | ✓ confirmed on HF model card, 2026-09-11 |
| sentence-transformers/all-MiniLM-L6-v2 | Apache-2.0 | ✓ confirmed on HF model card, 2026-09-11; active inference tested |
| Salesforce/blip-vqa-base (Perception VLM) | BSD-3-Clause | ✓ confirmed on HF model card, 2026-09-11; permissive commercial/research license |
| Siamese Change Detector (siamese_unet_levircd.pt) | Permissive in-house weights | ✓ architecture and calibrated weights created; active inference tested |
| bigearthnet_module fusion_model.joblib | trained in-house, sklearn | ✓ active multimodal inference tested |

In-house checkpoints trained on **synthetic** data carry no upstream license
constraints. Retraining on LEVIR-CD/BigEarthNet inherits the DATASET terms
(below) into the weights — research-only if LEVIR-CD is used.

## Datasets

| Dataset | Terms (at time of writing) | Used in repo? |
|---|---|---|
| Synthetic samples (`datasets/samples/`) | generated locally | ✓ shipped |
| BigEarthNet v2.0 | CDLA-Permissive family — verify current version | optional download |
| VRSBench (`xiang709/VRSBench`, HF mirror) | research-use leaning (CC-BY/research) — verify before commercial use | ✓ 12-example real subset in `datasets/vrsbench/real_subset/` (gitignored), fetched 2026-09-11 for eval only |
| RSVQA (`dmarsili/RSVQA-LR-2k`, unofficial HF mirror) | research/academic — verify against original RSVQA Zenodo terms | ✓ 12-example real subset in `datasets/rsvqa/real_subset/` (gitignored), fetched 2026-09-11 for eval only |
| LEVIR-CD+ (`blanchon/LEVIR_CDPlus`, HF mirror) | research/academic only — treat as NON-commercial | ✓ 12-example real subset in `datasets/levir-cd/real_subset/` (gitignored), fetched 2026-09-11 for eval only. Note: official `satellite-image-deep-learning/LEVIR-CD` HF mirror has a broken/malformed dataset schema as of this date (`ValueError: Invalid string class label`) — used LEVIR-CD+ instead. |
| Copernicus Sentinel-1/2 | free/open; ESA attribution required in outputs | n/a until real imagery used |

**Eval-only usage, not shipped weights.** The three real subsets above are
pulled by `scripts/eval/fetch_real_subsets.py` into `datasets/*/real_subset/`
(gitignored — never committed) purely to produce honest, small, real-data
smoke metrics via `scripts/eval/eval_real_subsets.py`
(`scripts/eval/results/eval_{levir_cd,rsvqa,vrsbench}_real.json`). No model
was trained or fine-tuned on these subsets, and none of this imagery/labels
is served to end users. Before any larger pull of these datasets (full
splits) or any training run on them, re-verify current license terms —
LEVIR-CD/LEVIR-CD+ in particular is research/academic-only and must not back
a commercial deployment.

## Gate checklist before any non-local deployment

1. Re-verify every fetched checkpoint's license; set `license_verified: true`
   in `backend/models/registry.yaml` with the check date.
2. Record dataset licenses in `datasets/LICENSES.md`.
3. Confirm no research-only model (GeoChat, LEVIR-CD-trained weights) is in
   the serving path — replace with permissive fallbacks (§14.2).
4. Add ESA/Copernicus attribution if real Sentinel imagery is served.
5. Re-run CI with the audit check enabled.
