# Changelog

All notable changes to SatQuery AI are documented here.

## [Unaudited → Audited] — Compliance & wiring pass

### Added
- `AUDIT.md` — requirement-by-requirement traceability table produced by tracing
  imports from the live backend and frontend entry points (not the prior mapping doc).
- `SIH26167_Judges_Presentation.md` — judges' presentation and live demo script.
- **Voice query input** in `QueryComposer` via the browser Web Speech API, with a
  live "Listening…" indicator and a "Heard" confirmation toast. Transcripts flow
  through the same analyze path as typed text and the control is hidden on
  unsupported browsers.
- **Reasoning & Confidence** section in `ResultAnswerView` that surfaces how the
  query was understood (compiled `earthquery_spec`, intent, sensor reason), the
  6-component confidence breakdown (`ConfidencePanel`), and the execution
  provenance chain (`EvidenceProvenanceGraph`).
- Integration test asserting the result exposes `earthquery_spec` and
  `query_understanding`.

### Changed
- Backend `composer_node` now returns `earthquery_spec` in the query result, and the
  frontend `QueryResult` type includes it, so the UI can display the compiled query
  interpretation.
- `EvidenceProvenanceGraph` rewritten to render the real `execution_trace` as a
  generic clickable chain. Removed all hardcoded fallbacks (e.g. fabricated building
  counts and flood-specific tiers) so the graph never invents steps or numbers for
  non-flood queries.

### Removed
- Orphaned/duplicate frontend components never imported from the live path:
  `HeroQueryCenterpiece`, `QueryBar`, `AICopilotPanel`, `AIAnswerPanel`,
  `AgentStatusPanel`, `DataContextPanel`, `EvidencePanel`, `AgentExecutionTrace`,
  `TimelineControl`.
