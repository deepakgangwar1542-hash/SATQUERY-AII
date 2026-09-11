# SatQuery AI

Autonomous multimodal geospatial intelligence: ask a natural-language question
about satellite imagery (single-date or bi-temporal, optical and/or SAR) and
get a **grounded answer + confidence breakdown + spatial evidence on a 3D
globe + the generated GIS code + a full execution trace**.

Built to the spec in `SatQuery_AI_PRD.md` (v1.0). 100% permissive-licensed
runtime; heavy ML models are optional and every agent degrades gracefully
when they are absent.

---

## Quickstart (local, 5 minutes)

```bash
# 1. backend
python -m venv .venv
.venv/Scripts/activate            # Windows   (source .venv/bin/activate on POSIX)
pip install -r backend/requirements.txt

# 2. demo data (synthetic bi-temporal scene pair + ground truth)
python scripts/make_sample_data.py

# 3. run
uvicorn backend.main:app --port 8000        # terminal 1
cd frontend && npm install && npm run dev   # terminal 2 → http://localhost:5173
```

In the UI: upload `datasets/samples/optical_before.tif` (date 2025-06-01) and
`optical_after.tif` (date 2025-09-01), keep the default question, hit
**Analyze**, watch the agent pipeline run, and inspect the Evidence / Code /
Export tabs.

Headless check instead of the UI:

```bash
python scripts/e2e_smoke.py        # against the running server
python -m pytest tests/ -q         # 47 tests: unit + contract + integration + sandbox-security
```

Docker: `docker-compose up --build` → frontend at :5173, API at :8000.

## What's implemented (FR coverage)

| Area | FRs | State |
|---|---|---|
| GeoTIFF validation, band-mapping resolution (§10.6) | FR-1 | ✅ rasterio-only, metadata-driven |
| VQA + captioning | FR-2/3 | ✅ VLM path when a checkpoint exists; deterministic scene-analyzer fallback with explicit uncertainty note |
| Grounding/detection/segmentation | FR-4 | ✅ Grounding-DINO path when fetched; index-threshold segmenter fallback; pixel→WGS84 enforced |
| Bi-temporal change detection (§10.3 co-registration) | FR-5 | ✅ index-delta method; AOI-IoU guard; resampling documented |
| Change-VQA | FR-6 | ✅ composed from change stats + object corroboration |
| Optical+SAR fusion w/ §10.5 reliability | FR-7 | ✅ cloud-penalized optical reliability, agreement-weighted fusion |
| Model adaptation (BigEarthNet module) | FR-8 | ✅ trained sklearn fusion model (torch path documented); before/after metrics in `bigearthnet_module/outputs/metrics.json` |
| Agentic orchestration (explicit state graph, deterministic plans) | FR-9 | ✅ `backend/agents/graph.py` (LangGraph swap point), §12.2 rules |
| Verifier + §12.4 confidence formula | FR-10 | ✅ weights in `config/confidence_weights.yaml` |
| Execution trace | FR-11 | ✅ persisted per job, in result payload |
| GIS code generation + AST-validated sandbox | FR-12 | ✅ template intents (`ndvi_delta_threshold`, `ndwi_change`, `area_stats`); subprocess isolation, resource limits (POSIX), timeout |
| RAG knowledge agent | FR-13 | ✅ local curated corpus + TF-IDF (embeddings when fetched) |
| Cesium globe UI, AOI draw↔query | FR-14 | ✅ self-hosted Cesium, no ion dependency |
| Temporal replay | FR-15 | ✅ timeline scrub + replay (2–3 dates demoed, N supported in model) |
| Evidence/confidence/code panels, live SSE | FR-16 | ✅ |
| Benchmark/ablation scripts | FR-17 | ✅ `scripts/eval/*` — real measured numbers only (synthetic smoke caveats attached) |
| Report export (PDF/GeoJSON/CSV/code/trace ZIP) | FR-18 | ✅ from persisted data only |

Eval numbers actually measured on the shipped synthetic data (see
`scripts/eval/results/*.json` for the exact provenance): change detection
IoU 0.379 / F1 0.550 / recall 1.0 against the known ground-truth patch;
fusion ablation optical 100% / SAR-only 66.7% / fusion 100% (synthetic-subset
smoke metrics — plumbing validation, not capability claims).

## Architecture

```
UI (React+TS+Tailwind+CesiumJS, §15)
  ↕ /api/v1 (FastAPI, §9)
Input Validator → Orchestrator state graph (§12)
  ├─ Perception (VQA/caption)      ├─ Grounding (detect/segment)
  ├─ Change Agent (+co-register)   ├─ Change-VQA
  ├─ Multimodal Fusion (opt+SAR)   ├─ GIS Code Agent → AST sandbox (§11.3)
  └─ RAG (knowledge/)
→ Evidence Aggregator → Verifier (§12.4) → Result + trace + artifacts
```

Module boundaries (§13.2): `bigearthnet_module/` integrates ONLY through
`predict_multimodal()`; change integrates through `detect_change()`; VQA
through `answer_question()` — enforced by `tests/contract/`.

## Optional: real model weights

```bash
pip install huggingface_hub
bash scripts/fetch_models.sh     # grounding-dino-tiny, sam2, MiniLM embeddings, VLM
```
Afterwards `/api/v1/health` shows which engines loaded. Verify licenses and
flip `license_verified` in `backend/models/registry.yaml` (gate: §14.4).

## Honest limitations (what v1 does NOT do)

- **No LLM in the loop yet.** Planning, answers, and code generation are
  deterministic (rules/templates). The contracts are LLM-ready: swap the
  planner's intent step, the perception fallback, and the code-agent template
  generator for a temperature-0 LLM call — everything downstream (verifier,
  confidence, sandbox) is unchanged.
- Perception/grounding quality without downloaded checkpoints is *coarse by
  design* (index statistics, not semantics) — always disclosed in evidence.
- Benchmarks on real datasets (VRSBench/LEVIR-CD/RSVQA) are wired as scripts
  but the datasets are not downloaded (licenses + size — see
  `datasets/README.md`).
- Sandbox resource limits (RLIMIT_*) apply on POSIX/Docker; on Windows dev
  only wall-clock timeout + sanitized env are enforced. Docker is the
  security boundary (§11.3).
- Windows `spawn`-based sandbox subprocess adds ~2–4 s overhead per analysis.

## Repository map

See PRD §13.1 for the authoritative layout. Highlights:
`backend/` (api, agents, geospatial, sandbox, models, services, schemas) ·
`frontend/` · `bigearthnet_module/` · `datasets/` · `knowledge/` ·
`scripts/` (samples, fetch_models, eval, e2e) · `tests/` ·
`docker-compose.yml` · `.github/workflows/ci.yml`

License posture: runtime stack fully permissive (MIT/BSD/Apache-2.0);
Cesium ion NOT used; audit gate in `LICENSE_AUDIT.md` before any deployment.
