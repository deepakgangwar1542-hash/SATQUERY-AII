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

## Model checkpoints (none currently fetched — fallbacks active)

`scripts/fetch_models.sh` downloads on demand; the repo itself ships NO
third-party weights. If you fetch:

| Checkpoint | Upstream license (at time of writing) | Verified? |
|---|---|---|
| IDEA-Research/grounding-dino-tiny | Apache-2.0 | ☐ re-check model card |
| facebook/sam2-hiera-small | Apache-2.0 | ☐ re-check model card |
| sentence-transformers/all-MiniLM-L6-v2 | Apache-2.0 | ☐ re-check model card |
| Perception VLM (Prithvi-EO family or chosen Apache-2.0 VLM) | Apache-2.0 (claimed) | ☐ re-check model card |
| bigearthnet_module fusion_model.joblik | trained in-house, sklearn | ✓ (no upstream weights) |

In-house checkpoints trained on **synthetic** data carry no upstream license
constraints. Retraining on LEVIR-CD/BigEarthNet inherits the DATASET terms
(below) into the weights — research-only if LEVIR-CD is used.

## Datasets

| Dataset | Terms (at time of writing) | Used in repo? |
|---|---|---|
| Synthetic samples (`datasets/samples/`) | generated locally | ✓ shipped |
| BigEarthNet v2.0 | CDLA-Permissive family — verify current version | optional download |
| VRSBench | research-use leaning (CC-BY/research) — verify | not downloaded |
| RSVQA | research/academic — verify | not downloaded |
| LEVIR-CD | research/academic only — treat as NON-commercial | not downloaded |
| Copernicus Sentinel-1/2 | free/open; ESA attribution required in outputs | n/a until real imagery used |

## Gate checklist before any non-local deployment

1. Re-verify every fetched checkpoint's license; set `license_verified: true`
   in `backend/models/registry.yaml` with the check date.
2. Record dataset licenses in `datasets/LICENSES.md`.
3. Confirm no research-only model (GeoChat, LEVIR-CD-trained weights) is in
   the serving path — replace with permissive fallbacks (§14.2).
4. Add ESA/Copernicus attribution if real Sentinel imagery is served.
5. Re-run CI with the audit check enabled.
