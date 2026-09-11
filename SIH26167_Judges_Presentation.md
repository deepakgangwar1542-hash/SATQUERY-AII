# SatQuery AI — Judges' Presentation (SIH26167)

**Autonomous Multimodal Earth-Observation Investigation System**

> "Don't tell SatQuery which tool to use. Tell SatQuery what you want to know."

---

## 1. The problem

ISRO analysts need answers from satellite imagery — *"Which buildings flooded between June and August?"* — not a menu of tools. Conventional dashboards force the operator to pick the model, the sensor, and the GIS operation by hand. SatQuery inverts this: the operator states the question in natural language (typed or spoken) and the system autonomously plans and executes the investigation.

## 2. What we built

A full-stack system with a real agent pipeline:

1. **EarthQuery Compiler** — natural language → validated `EarthQuerySpec` (22+ intent taxonomy, temporal scopes, target objects, verification policy).
2. **Investigation Planner** — builds a dependency graph of evidence steps from the spec.
3. **Autonomous Sensor Selection** — optical / SAR / fusion chosen from cloud contamination and task type, with a stated reason.
4. **Model Registry** — real checkpoints when present; honestly disclosed degraded mode when weights are absent.
5. **Specialist agents** — perception & zero-shot grounding, Siamese U-Net change detection, change-VQA, polarimetric SAR, multimodal fusion, hypothesis reasoning, SOP/knowledge retrieval, and a sandboxed GIS code agent.
6. **Deterministic geospatial reasoning** — exact Shapely/GeoPandas metric intersections; no heuristic approximations for the final numbers.
7. **Verification & conflict loop** — evidence-consistency check that can trigger self-correcting re-planning.
8. **Composer** — merges agent outputs into an answer, traceable claims, and a map feature collection.

## 3. How the PS requirements map to the build

Every functional requirement in the problem statement is implemented and wired into the live path. The full traceability table is in [`AUDIT.md`](./AUDIT.md), produced by tracing imports from the two live entry points — it is not aspirational.

Highlights judges can verify live:

- **Query interpretation** is shown back to the operator: the compiled `earthquery_spec`, classified intent, and query-understanding summary appear in the result's **Reasoning & Confidence** panel.
- **Confidence estimation** is a visible **6-component breakdown** (model, evidence agreement, sensor reliability, data quality, spatial and temporal consistency), not a single opaque number.
- **Auditable execution summary** is a **clickable provenance chain** rendered directly from the real `execution_trace`; every node is an actual agent step with its duration and status.
- **Voice query input** uses the browser Web Speech API, transcribes into the same query field, shows a "Heard" confirmation, and submits through the identical analyze path as typed text.
- **Downloadable dossier** — GeoJSON masks, GeoTIFF rasters, and execution logs bundled as a ZIP via `GET /report/{job_id}`.

## 4. Honesty statement

We do not overclaim. Specialist models run in a disclosed degraded mode when heavy ML weights are absent; the orchestration, GIS reasoning, and evidence pipeline are fully real. Detection quality on ISRO held-out data depends on the configured weights in `backend/models/registry.yaml`. Voice input degrades gracefully — the mic control is hidden on browsers without Web Speech support.

## 5. Live demo script (2 minutes)

1. Load the demo scenes (or upload an optical before/after pair).
2. Speak or type: *"Show areas where vegetation decreased by more than 20% between June and September."*
3. Watch the agent pipeline bar execute the planned steps.
4. Open **Reasoning & Confidence** — show the interpreted spec, the 6-component confidence, and the clickable provenance chain.
5. Open the **Evidence Lens** and the globe overlay to inspect the change polygons.
6. Export the dossier ZIP.

## 6. Architecture at a glance

```
USER QUERY (typed or spoken)
  → EarthQuery Compiler → Investigation Planner → Sensor Selection → Model Registry
  → Specialist Agents (perception / change / SAR / fusion / hypothesis / RAG / GIS code)
  → Deterministic Geospatial Reasoning → Evidence Fusion
  → Verification & Conflict Loop → Composer
  → Evidence-grounded interactive proof (Evidence Lens, Confidence, Provenance Graph, Report ZIP)
```

See [`README.md`](./README.md) for the full technical breakdown and [`AUDIT.md`](./AUDIT.md) for requirement-by-requirement traceability.
