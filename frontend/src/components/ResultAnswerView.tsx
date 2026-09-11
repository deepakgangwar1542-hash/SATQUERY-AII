/**
 * ResultAnswerView — RESULT state right panel
 *
 * Visual hierarchy (reference philosophy):
 *   STATUS STRIP  ← "Investigation Complete" + sensor badge
 *   ANSWER        ← hero text, confidence score
 *   TEMPORAL      ← Before→After chips (when temporal query)
 *   KEY METRICS   ← 2–3 real numbers from geospatial_results
 *   EVIDENCE CTA  ← "Evidence Lens" + "Globe" buttons
 *   SECONDARY     ← Claims / Uncertainty / SOPs / GIS Code (collapsible)
 *   FOLLOW-UPS    ← Suggested next questions
 *
 * RULES:
 * - NO hardcoded/fake values. ALL values from the `result` prop.
 * - Temporal section rendered ONLY when query_understanding.temporal === true.
 * - Metrics section rendered ONLY when geospatial_results has actual data.
 */
import React, { useState } from "react";
import type { QueryResult, Claim } from "../services/types";
import { CodePanel } from "./CodePanel";
import { ConfidencePanel } from "./ConfidencePanel";
import { EvidenceProvenanceGraph } from "./EvidenceProvenanceGraph";
import * as api from "../services/api";

interface Props {
  result: QueryResult;
  question: string;
  onOpenEvidenceLens?: (claim?: Claim | null) => void;
  onSelectQuestion?: (q: string) => void;
  onHighlightEvidence?: () => void;
}

// ── Helpers ────────────────────────────────────────────────────
function confColor(v: number): string {
  if (v >= 0.8) return "#34d399";
  if (v >= 0.55) return "#38bdf8";
  return "#fbbf24";
}
function confLabel(v: number): string {
  if (v >= 0.8) return "High Confidence";
  if (v >= 0.55) return "Moderate Confidence";
  return "Low Confidence";
}
const SEV: Record<string, string> = {
  high: "text-rose-400 bg-rose-950/60 border-rose-700/50",
  medium: "text-amber-400 bg-amber-950/60 border-amber-700/50",
  low: "text-slate-400 bg-slate-800/60 border-slate-700/50",
};

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">
      {children}
    </p>
  );
}

function MetricCard({
  label,
  value,
  unit,
  highlight,
}: {
  label: string;
  value: string | number;
  unit?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`flex flex-col rounded-xl border p-3 ${
        highlight
          ? "border-sky-500/40 bg-gradient-to-br from-sky-950/60 to-indigo-950/40"
          : "border-slate-700/60 bg-slate-800/40"
      }`}
    >
      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
        {label}
      </span>
      <span className="text-xl font-bold font-mono text-slate-100 leading-tight">
        {value}
        {unit && (
          <span className="text-xs font-normal text-slate-400 ml-1">{unit}</span>
        )}
      </span>
    </div>
  );
}

function TemporalChip({
  label,
  date,
  accent,
}: {
  label: string;
  date: string;
  accent: "blue" | "amber";
}) {
  const cls =
    accent === "blue"
      ? "border-sky-500/50 bg-sky-950/50 text-sky-300"
      : "border-amber-500/50 bg-amber-950/50 text-amber-300";
  return (
    <div className={`flex flex-col items-center rounded-xl border px-4 py-2.5 min-w-[90px] ${cls}`}>
      <span className="text-[9px] font-bold uppercase tracking-widest opacity-70 mb-1">
        {label}
      </span>
      <span className="text-sm font-mono font-bold">{date}</span>
    </div>
  );
}

// ── Main ───────────────────────────────────────────────────────
export function ResultAnswerView({
  result,
  onOpenEvidenceLens,
  onSelectQuestion,
  onHighlightEvidence,
}: Props) {
  type Sec = "claims" | "uncertainty" | "sops" | "code" | "reasoning" | "reason" | null;
  const [openSec, setOpenSec] = useState<Sec>(null);
  const [activeTab, setActiveTab] = useState<"answer" | "export">("answer");
  const toggle = (s: Sec) => setOpenSec((p) => (p === s ? null : s));

  const pct = Math.round(result.confidence * 100);
  const geo = result.geospatial_results;
  const temporal = result.query_understanding?.temporal;
  const claims = result.claims || [];
  const sops = result.rag_sops || [];
  const followUps = result.follow_up_questions || [];
  const totalAgents = result.agents_used?.length ?? 0;
  const totalMs = result.execution_trace.reduce((acc, t) => acc + (t.duration_ms || 0), 0);
  const totalSec = (totalMs / 1000).toFixed(1);

  // Temporal dates from evidence
  const evidenceDates = result.evidence
    .filter((e) => e.type === "scene_date" || e.agent.toLowerCase().includes("change"))
    .map((e) => e.summary)
    .slice(0, 2);

  // Build metrics from real geo results
  const metrics: Array<{ label: string; value: string | number; unit?: string; highlight?: boolean }> = [];
  if (geo?.affected_building_count !== undefined)
    metrics.push({ label: "Buildings Affected", value: geo.affected_building_count.toLocaleString(), highlight: true });
  if (geo?.affected_percentage !== undefined)
    metrics.push({ label: "Impact Coverage", value: geo.affected_percentage.toFixed(1), unit: "%" });
  if (geo?.affected_area_m2 !== undefined)
    metrics.push({ label: "Affected Area", value: (geo.affected_area_m2 / 10000).toFixed(1), unit: "ha" });
  if (geo?.total_buildings_detected !== undefined)
    metrics.push({ label: "Total Buildings", value: geo.total_buildings_detected.toLocaleString() });

  // Fallback: confidence breakdown scores when no geo data
  if (metrics.length === 0) {
    const bd = result.confidence_breakdown;
    if (bd.evidence_agreement !== undefined)
      metrics.push({ label: "Evidence Agreement", value: Math.round(bd.evidence_agreement * 100), unit: "%", highlight: true });
    if (bd.spatial_consistency !== undefined)
      metrics.push({ label: "Spatial Consistency", value: Math.round(bd.spatial_consistency * 100), unit: "%" });
  }
  const visibleMetrics = metrics.slice(0, 3);

  return (
    <div className="flex flex-col h-full bg-slate-900/75 border-l border-slate-800/80 overflow-hidden animate-slide-right">
      {/* Tabs */}
      <div className="shrink-0 flex border-b border-slate-800/60 bg-slate-950/40">
        {(["answer", "export"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            className={`px-5 py-3 text-xs font-bold uppercase tracking-wider transition-colors cursor-pointer border-b-2 ${
              activeTab === t
                ? "border-sky-500 text-sky-400 bg-sky-950/20"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            {t === "answer" ? "Answer" : "Export"}
          </button>
        ))}
      </div>

      {/* ══ ANSWER TAB ══ */}
      {activeTab === "answer" && (
        <div className="flex-1 overflow-y-auto">

          {/* 1. Status strip */}
          <div className="flex items-center justify-between px-4 py-2 bg-emerald-950/30 border-b border-emerald-800/30">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-400">
                Investigation Complete
              </span>
            </div>
            <div className="flex items-center gap-2">
              {result.sensor_selection?.primary && (
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-sky-950 border border-sky-700/60 text-sky-300">
                  {result.sensor_selection.primary.toUpperCase()}
                </span>
              )}
              <span className="text-[9px] font-mono text-slate-500">
                {totalAgents}a · {totalSec}s
              </span>
            </div>
          </div>

          {/* 2. Answer */}
          <div className="px-4 pt-4 pb-3 border-b border-slate-800/50">
            <SectionLabel>Answer</SectionLabel>
            <div className="flex items-center gap-2 mb-3">
              <span
                className="text-2xl font-bold font-mono tabular-nums leading-none"
                style={{ color: confColor(result.confidence) }}
              >
                {pct}%
              </span>
              <span className="text-xs font-semibold" style={{ color: confColor(result.confidence) }}>
                {confLabel(result.confidence)}
              </span>
            </div>
            <p className="text-sm text-slate-100 leading-relaxed whitespace-pre-line">
              {result.answer}
            </p>
          </div>

          {/* 3. Temporal comparison */}
          {temporal && (
            <div className="px-4 py-3 border-b border-slate-800/50">
              <SectionLabel>Temporal Comparison</SectionLabel>
              <div className="flex items-center gap-3 flex-wrap">
                <TemporalChip
                  label="Before"
                  date={evidenceDates[0] || (result.evidence[0]?.agent ?? "T1")}
                  accent="blue"
                />
                <span className="text-slate-500 text-lg font-bold">→</span>
                <TemporalChip
                  label="After"
                  date={evidenceDates[1] || (result.evidence[1]?.agent ?? "T2")}
                  accent="amber"
                />
              </div>
              <p className="text-[10px] text-slate-500 mt-2">
                Bi-temporal change detection ·{" "}
                {result.sensor_selection?.primary?.toUpperCase() || "multi-sensor"}
              </p>
            </div>
          )}

          {/* 4. Key metrics */}
          {visibleMetrics.length > 0 && (
            <div className="px-4 py-3 border-b border-slate-800/50">
              <SectionLabel>Key Results</SectionLabel>
              <div className={`grid gap-2 ${visibleMetrics.length === 1 ? "grid-cols-1" : "grid-cols-2"}`}>
                {visibleMetrics.map((m, i) => (
                  <MetricCard key={i} label={m.label} value={m.value} unit={m.unit} highlight={m.highlight} />
                ))}
              </div>
              {geo?.formula && (
                <p className="text-[10px] font-mono text-slate-500 mt-2 leading-relaxed">
                  Formula: {geo.formula}
                </p>
              )}
            </div>
          )}

          {/* 5. Evidence CTA */}
          <div className="px-4 py-3 border-b border-slate-800/50">
            <div className="rounded-xl bg-gradient-to-br from-sky-950/50 to-indigo-950/50 border border-sky-500/30 p-3.5 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-sky-300">
                  View Evidence
                </span>
                <div className="flex gap-2">
                  <span className="text-[9px] font-mono text-emerald-400">
                    {result.evidence.length} entries
                  </span>
                  {result.artifacts.length > 0 && (
                    <span className="text-[9px] font-mono text-slate-400">
                      · {result.artifacts.length} artifacts
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => onOpenEvidenceLens && onOpenEvidenceLens(null)}
                  className="flex-1 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs shadow-md transition-all cursor-pointer flex items-center justify-center gap-1.5"
                >
                  🔍 Evidence Lens
                </button>
                {result.location.features.length > 0 && (
                  <button
                    onClick={onHighlightEvidence}
                    className="flex-1 py-2 rounded-lg border border-slate-600 bg-slate-800/60 hover:bg-slate-700/60 text-slate-200 font-semibold text-xs transition-all cursor-pointer flex items-center justify-center gap-1.5"
                  >
                    🌐 Globe
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* 5b. Reasoning: how the query was understood + confidence + provenance */}
          <div className="px-4 py-2 border-b border-slate-800/40">
            <button
              onClick={() => toggle("reason")}
              className="w-full flex items-center justify-between py-1.5 text-left cursor-pointer group"
            >
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 group-hover:text-slate-200 transition-colors">
                Reasoning &amp; Confidence
              </span>
              <span className="text-slate-500 text-xs">{openSec === "reason" ? "▴" : "▾"}</span>
            </button>
            {openSec === "reason" && (
              <div className="space-y-3 pb-2 animate-slide-up">
                {/* How the query was understood */}
                {result.query_understanding && (
                  <div className="rounded-xl border border-slate-800/80 bg-slate-900/50 p-3.5 space-y-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                      How the query was understood
                    </span>
                    <p className="text-xs text-slate-200 leading-relaxed">
                      {result.query_understanding.summary}
                    </p>
                    <div className="flex flex-wrap gap-1.5 pt-0.5">
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-sky-950 border border-sky-700/60 text-sky-300">
                        intent: {result.query_understanding.intent}
                      </span>
                      {result.query_understanding.phenomenon && (
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300">
                          phenomenon: {result.query_understanding.phenomenon}
                        </span>
                      )}
                      {result.query_understanding.temporal && (
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300">
                          temporal
                        </span>
                      )}
                      {result.query_understanding.requires_sar && (
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300">
                          SAR
                        </span>
                      )}
                      {result.query_understanding.requires_change_detection && (
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300">
                          change-detection
                        </span>
                      )}
                    </div>
                    {result.sensor_selection?.reason && (
                      <p className="text-[10px] text-slate-500 leading-relaxed pt-1">
                        Sensor choice: {result.sensor_selection.reason}
                      </p>
                    )}
                  </div>
                )}

                {/* 6-component confidence breakdown */}
                {result.confidence_breakdown &&
                  Object.keys(result.confidence_breakdown).length > 0 && (
                    <ConfidencePanel
                      confidence={result.confidence}
                      breakdown={result.confidence_breakdown}
                      verdict={result.consistency_verdict}
                    />
                  )}

                {/* Clickable execution provenance chain */}
                {result.execution_trace.length > 0 && (
                  <EvidenceProvenanceGraph result={result} />
                )}
              </div>
            )}
          </div>

          {/* 6. Claims (collapsible) */}
          {claims.length > 0 && (
            <div className="px-4 py-2 border-b border-slate-800/40">
              <button
                onClick={() => toggle("claims")}
                className="w-full flex items-center justify-between py-1.5 text-left cursor-pointer group"
              >
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 group-hover:text-slate-200 transition-colors">
                  Traceable Claims ({claims.length})
                </span>
                <span className="text-slate-500 text-xs">{openSec === "claims" ? "▴" : "▾"}</span>
              </button>
              {openSec === "claims" && (
                <div className="space-y-1.5 pb-2 animate-slide-up">
                  {claims.map((c) => (
                    <div key={c.id} className="p-2 rounded-lg border border-slate-800 bg-slate-900/70 flex items-center justify-between">
                      <span className="text-xs text-slate-200 pr-2 leading-relaxed">{c.text}</span>
                      <button
                        onClick={() => onOpenEvidenceLens && onOpenEvidenceLens(c)}
                        className="shrink-0 px-2 py-0.5 rounded bg-sky-950 border border-sky-700 text-[10px] font-mono text-sky-300 hover:bg-sky-900 cursor-pointer"
                      >
                        Inspect ↗
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 7. Uncertainty (collapsible) */}
          {result.uncertainty.length > 0 && (
            <div className="px-4 py-2 border-b border-slate-800/40">
              <button
                onClick={() => toggle("uncertainty")}
                className="w-full flex items-center justify-between py-1.5 text-left cursor-pointer group"
              >
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-500/80 group-hover:text-amber-400 transition-colors">
                  Uncertainty Flags ({result.uncertainty.length})
                </span>
                <span className="text-slate-500 text-xs">{openSec === "uncertainty" ? "▴" : "▾"}</span>
              </button>
              {openSec === "uncertainty" && (
                <div className="space-y-1.5 pb-2 animate-slide-up">
                  {result.uncertainty.map((u, i) => (
                    <div key={i} className={`text-xs rounded-lg border p-2.5 ${SEV[u.severity] ?? "text-slate-400 bg-slate-800/40 border-slate-700/40"}`}>
                      <span className="font-semibold font-mono block">[{u.severity.toUpperCase()}] {u.signal}</span>
                      <p className="opacity-80 mt-0.5">{u.explanation}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 8. SOPs (collapsible) */}
          {sops.length > 0 && (
            <div className="px-4 py-2 border-b border-slate-800/40">
              <button
                onClick={() => toggle("sops")}
                className="w-full flex items-center justify-between py-1.5 text-left cursor-pointer group"
              >
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 group-hover:text-slate-200 transition-colors">
                  Response Protocols ({sops.length})
                </span>
                <span className="text-slate-500 text-xs">{openSec === "sops" ? "▴" : "▾"}</span>
              </button>
              {openSec === "sops" && (
                <div className="space-y-2 pb-2 animate-slide-up">
                  {sops.map((sop) => (
                    <div key={sop.sop_id} className="rounded-xl bg-sky-950/30 border border-sky-800/40 p-3 text-xs space-y-1.5">
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-semibold text-sky-200 leading-tight">{sop.title}</span>
                        <span className="shrink-0 text-[9px] font-mono text-sky-400 bg-sky-950/60 border border-sky-800 px-1.5 py-0.5 rounded">{sop.sop_id}</span>
                      </div>
                      <p className="text-slate-400 text-[10px]">Authority: <span className="text-slate-300">{sop.authority}</span></p>
                      <ul className="list-disc list-inside space-y-0.5 text-slate-300 text-[10px]">
                        {sop.action_protocols.map((act, i) => <li key={i}>{act}</li>)}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 9. GIS Code (collapsible) */}
          {result.generated_code.length > 0 && (
            <div className="px-4 py-2 border-b border-slate-800/40">
              <button
                onClick={() => toggle("code")}
                className="w-full flex items-center justify-between py-1.5 text-left cursor-pointer group"
              >
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-500/80 group-hover:text-emerald-400 transition-colors">
                  GIS Code <span className="text-emerald-400 font-mono">✓ AST Validated</span>
                </span>
                <span className="text-slate-500 text-xs">{openSec === "code" ? "▴" : "▾"}</span>
              </button>
              {openSec === "code" && (
                <div className="pb-2 animate-slide-up">
                  <CodePanel code={result.generated_code} />
                </div>
              )}
            </div>
          )}

          {/* 10. Follow-up questions */}
          {followUps.length > 0 && (
            <div className="px-4 py-3">
              <SectionLabel>Follow-up Investigations</SectionLabel>
              <div className="space-y-1.5">
                {followUps.slice(0, 3).map((q, i) => (
                  <button
                    key={i}
                    onClick={() => onSelectQuestion && onSelectQuestion(q)}
                    className="w-full text-left rounded-xl border border-slate-700/60 bg-slate-800/30 hover:bg-slate-800/70 hover:border-sky-500/40 px-3 py-2 text-xs text-slate-300 hover:text-white transition-all cursor-pointer"
                  >
                    <span className="text-sky-400 mr-1.5">↪</span>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══ EXPORT TAB ══ */}
      {activeTab === "export" && (
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <SectionLabel>Export Intelligence Dossier</SectionLabel>
          <p className="text-sm text-slate-300 leading-relaxed">
            Download the full analytical package including GeoJSON vector masks,
            GeoTIFF change rasters, uncertainty breakdown, and execution logs.
          </p>
          {result.artifacts.length > 0 && (
            <div className="space-y-1.5">
              <SectionLabel>Generated Files</SectionLabel>
              {result.artifacts.map((a) => (
                <a
                  key={a.url}
                  href={a.url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between rounded-lg bg-slate-800/40 border border-slate-700/50 px-3 py-2.5 text-xs hover:bg-slate-800/60 transition-colors group"
                >
                  <span className="text-sky-400 group-hover:text-sky-300 font-medium truncate">{a.name}</span>
                  <span className="text-[10px] font-mono text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded shrink-0 ml-2">{a.type}</span>
                </a>
              ))}
            </div>
          )}
          <a
            href={api.reportUrl(result.job_id)}
            download
            className="block w-full rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 py-3 text-center text-sm font-bold text-white transition-all shadow-lg shadow-emerald-600/20"
          >
            📥 Download Report Bundle
          </a>
          <div>
            <button
              onClick={() => toggle("reasoning")}
              className="w-full flex items-center justify-between py-1.5 text-left cursor-pointer group"
            >
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 group-hover:text-slate-200 transition-colors">
                Execution Telemetry
              </span>
              <span className="text-slate-500 text-xs">{openSec === "reasoning" ? "▴" : "▾"}</span>
            </button>
            {openSec === "reasoning" && (
              <div className="rounded-xl border border-slate-800 overflow-hidden animate-slide-up">
                <div className="p-3 space-y-0">
                  {result.execution_trace.map((t, i) => (
                    <div key={i} className="flex items-center justify-between py-1.5 border-b border-slate-800/40 last:border-0">
                      <div>
                        <span className="text-xs font-mono text-sky-300">{t.agent}</span>
                        <span className="text-xs text-slate-500 ml-2">{t.action}</span>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] font-mono">
                        <span className={t.status === "ok" ? "text-emerald-400" : "text-amber-400"}>
                          {t.status === "ok" ? "✓" : "!"}
                        </span>
                        <span className="text-slate-400">{t.duration_ms}ms</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
