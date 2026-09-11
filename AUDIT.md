# SatQuery AI — Compliance & Wiring Audit (SIH26167)

This audit was produced by tracing imports from the two live entry points:

- **Backend live path:** `backend/api/routes_query.py` → `backend/agents/orchestrator.py` (`GRAPH.run`) → specialist agents → `verifier` → `composer` → `GET /result/{job_id}`.
- **Frontend live path:** `frontend/src/main.tsx` → `pages/MissionControl.tsx` → `QueryComposer` → `services/api.ts` (`submitQuery`/`getResult`) → `ResultAnswerView` / `AgentPipelineBar` / `EvidenceLens` / `AnalysisOverlay`.

Verified by reading actual import statements, not the prior mapping doc.

## Mandatory PS functional checklist

| # | PS requirement | Implemented in | Wired into live path? |
|---|----------------|----------------|-----------------------|
| 1 | Single-image VQA / captioning | `backend/agents/perception.py` → `perception_node` | Yes — routed via `plan` for `image_question`/`image_caption` intents; answer surfaced in `ResultAnswerView`. |
| 2 | Object detection / grounding | `backend/agents/grounding.py` → `grounding_node` | Yes — `object_grounding`/`building_count` intents; polygons rendered as map features. |
| 3 | Bi-temporal change detection | `backend/agents/change.py` → `change_node` (+ `backend/geospatial/siamese_change.py`) | Yes — `temporal_change` intent; `change_map.geojson` artifact + map features. |
| 4 | Change-VQA (explain the change) | `backend/agents/change_vqa.py` → `change_vqa_node` | Yes — chained after change detection; narrative answer. |
| 5 | Optical ↔ SAR joint analysis | `backend/agents/sar.py` → `sar_node`, `backend/agents/multimodal.py` → `multimodal_node` | Yes — `optical_sar_comparison`/`flood_detection`; SAR water GeoJSON + fusion output. |
| 6 | Query interpretation → task classification | `backend/services/earthquery/compiler.py` (`EarthQueryCompiler`) | Yes — `planner_node` compiles spec + `QueryUnderstanding`; **now also returned as `earthquery_spec` in the result (Phase 2).** |
| 7 | Input compatibility check | `input_validator_node` (+ `backend/geospatial/raster.py`) | Yes — validates rasters/band mappings before specialists run. |
| 8 | Autonomous model / sensor selection | `backend/services/earthquery/sensor_selector.py`, `backend/models/loaders.py` | Yes — `sensor_selection` (with `reason`) + `model_selection` in result. |
| 9 | Configured execution of specialist tools | `orchestrator.py` graph nodes + `backend/agents/code_agent.py` (`gis_code_node`) + `backend/sandbox/` | Yes — router dispatches `plan` steps; generated code returned in `generated_code`. |
| 10 | Output combination | `composer_node` | Yes — merges agent outputs → answer, claims, feature collection. |
| 11 | Confidence estimation (6-component) | `backend/agents/verifier.py` → `verifier_node` | Yes — `confidence_breakdown` in result; **now rendered as a visible breakdown via `ConfidencePanel` (Phase 2).** |
| 12 | Self-correcting verification / re-plan | `verifier.py` (`needs_replan`, conflict trace) | Yes — conflict emits SSE + trace entry; visible in provenance/trace. |
| 13 | Auditable execution summary | `backend/agents/trace.py` (`traced`) → `execution_trace` | Yes — **now rendered as a clickable provenance graph via `EvidenceProvenanceGraph` (Phase 2).** |
| 14 | GUI / web app | `frontend/` (React + Vite + Cesium) | Yes. |
| 15 | Visual evidence + confidence + execution summary + downloadable report | `EvidenceLens`, `ConfidencePanel`, `EvidenceProvenanceGraph`, `routes_report.py` (ZIP) | Yes — report ZIP via `GET /report/{job_id}`. |
| 16 | Knowledge retrieval / SOPs | `backend/agents/rag.py` → `rag_node`, `backend/rag/sop_store.py` | Yes — `rag_sops` in result and answer guidance. |
| 17 | Hypothesis reasoning | `backend/agents/hypothesis_engine.py` → `hypothesis_node` | Yes — `hypothesis_investigation`/`change_explanation`; hypotheses in result. |
| 18 | Voice query input | `frontend/src/components/QueryComposer.tsx` (Web Speech API) | Yes — **added in Phase 3**; submits through the same `onAnalyze` path as typed text. |

## Backend agents — all invoked

Every module under `backend/agents/` is reachable from `build_graph()` in `orchestrator.py`:

`perception`, `grounding`, `change`, `change_vqa`, `sar`, `multimodal`, `code_agent` (as `gis_code`), `hypothesis_engine`, `rag`, `verifier`, `composer`, plus infrastructure `graph.py` (state graph) and `trace.py` (`traced`) and `planner.py`. **No orphaned agents.**

## Frontend components — orphans removed (Phase 1)

Live components (kept): `MissionControl`, `DataDrawer`, `GlobeWorkspace`, `CesiumGlobe`, `QueryComposer`, `AnalysisOverlay`, `ResultAnswerView`, `AgentPipelineBar`, `EvidenceLens`, `CodePanel`, `ConfidencePanel` (newly wired), `EvidenceProvenanceGraph` (newly wired), plus `services/api.ts`, `services/types.ts`, `services/mapProvider.ts`.

Deleted orphans (defined but never imported from the live path, verified by grep):

- `HeroQueryCenterpiece.tsx` — duplicate of `QueryComposer`; unique ideas (temporal/single mode toggle) not part of the live data model and not migrated.
- `QueryBar.tsx`
- `AICopilotPanel.tsx`
- `AIAnswerPanel.tsx`
- `AgentStatusPanel.tsx`
- `DataContextPanel.tsx`
- `EvidencePanel.tsx`
- `AgentExecutionTrace.tsx`
- `TimelineControl.tsx`

## Gaps flagged honestly

- Specialist models run in a synthetic/degraded mode when heavy ML weights are absent; the pipeline, orchestration, and GIS reasoning are real, but detection quality on ISRO held-out data depends on the configured model weights in `backend/models/registry.yaml`.
- Voice input relies on the browser Web Speech API (Chromium); it degrades gracefully (button hidden) on unsupported browsers.
