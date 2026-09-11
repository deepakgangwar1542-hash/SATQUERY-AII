/**
 * AIAnswerPanel — STATE C (RESULT) right column
 *
 * Visual priority:
 *   1. Answer text (largest)
 *   2. Confidence summary (prominent number)
 *   3. Evidence (expandable)
 *   4. Advanced (SOPs, GIS code, export — behind tab)
 *
 * Uses REAL backend data only. No hardcoded values.
 */
import { useState } from "react";
import type { QueryResult, SopEntry, Claim } from "../services/types";
import { CodePanel } from "./CodePanel";
import * as api from "../services/api";

interface Props {
  result: QueryResult;
  onHighlightEvidence?: () => void;
  onOpenEvidenceLens?: (claim?: Claim | null) => void;
  onSelectQuestion?: (q: string) => void;
}

type Tab = "answer" | "evidence" | "reasoning" | "export";

const CONFIDENCE_LABELS: Record<string, string> = {
  evidence_agreement: "Evidence Agreement",
  sensor_reliability: "Sensor Reliability",
  data_quality: "Data Quality",
  spatial_consistency: "Spatial Consistency",
  temporal_consistency: "Temporal Consistency",
  model_confidence: "Model Baseline",
};

const SEV_COLOR: Record<string, string> = {
  high: "text-rose-400",
  medium: "text-amber-400",
  low: "text-slate-400",
};

export function AIAnswerPanel({
  result,
  onHighlightEvidence,
  onOpenEvidenceLens,
  onSelectQuestion,
}: Props) {
  const [tab, setTab] = useState<Tab>("answer");
  const [showConfidenceBreakdown, setShowConfidenceBreakdown] = useState(false);
  const [showPipeline, setShowPipeline] = useState(false);

  const pct = Math.round(result.confidence * 100);
  const verdict = result.consistency_verdict;
  const isHighConf = pct >= 80;
  const isMedConf = pct >= 55 && pct < 80;
  const sops: SopEntry[] = result.rag_sops ?? [];
  const totalAgents = result.agents_used?.length ?? 0;
  const claims = result.claims || [];
  const hypotheses = result.hypotheses || [];
  const followUps = result.follow_up_questions || [];
  const sensorDecision = result.sensor_selection;

  // Compute total trace time
  const totalMs = result.execution_trace.reduce((acc, t) => acc + (t.duration_ms || 0), 0);
  const totalSec = (totalMs / 1000).toFixed(1);

  const tabClass = (t: Tab) =>
    `px-4 py-2.5 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
      tab === t
        ? "border-sky-500 text-sky-400"
        : "border-transparent text-slate-400 hover:text-slate-200"
    }`;

  return (
    <div className="flex flex-col h-full bg-slate-900/70 border-l border-slate-800/80 animate-slide-right overflow-hidden">
      {/* ── Header ─────────────────────────────────────────── */}
      <div className="px-5 pt-5 pb-4 border-b border-slate-800/60">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-emerald-400" />
            <span className="text-xs font-semibold uppercase tracking-widest text-emerald-400">
              Investigation Complete
            </span>
          </div>

          {/* Autonomous sensor badge */}
          {sensorDecision?.primary && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-950 border border-sky-700/60 text-sky-300 font-bold">
              {sensorDecision.primary.toUpperCase()} (Primary)
            </span>
          )}
        </div>

        {/* ── Confidence summary (always visible) ── */}
        <div className="flex items-end justify-between">
          <div>
            <span className="text-4xl font-bold font-mono tracking-tight leading-none" style={{
              color: isHighConf ? "#34d399" : isMedConf ? "#38bdf8" : "#fbbf24"
            }}>
              {pct}%
            </span>
            <div className="flex items-center gap-1.5 mt-1">
              {isHighConf && <span className="text-emerald-400 text-sm">✓</span>}
              <span className={`text-sm font-semibold ${
                isHighConf ? "text-emerald-300" : isMedConf ? "text-sky-300" : "text-amber-300"
              }`}>
                {isHighConf ? "VERIFIED HIGH" : isMedConf ? "MODERATE" : "LOW CONFIDENCE"}
              </span>
            </div>
          </div>

          <div className="text-right text-xs text-slate-500 space-y-0.5">
            <div className="font-mono">{totalAgents} agents</div>
            <div className="font-mono">{totalSec}s total</div>
          </div>
        </div>

        {/* Micro-summary confidence checks */}
        <div className="mt-3 space-y-1">
          {result.confidence_breakdown.evidence_agreement > 0.8 && (
            <p className="text-xs text-slate-300 flex items-center gap-1.5">
              <span className="text-emerald-400">✓</span>
              Evidence consistent across sensors & models
            </p>
          )}
          {result.confidence_breakdown.spatial_consistency > 0.8 && (
            <p className="text-xs text-slate-300 flex items-center gap-1.5">
              <span className="text-emerald-400">✓</span>
              Spatially verified ({result.location.features.length} features)
            </p>
          )}
        </div>

        {/* Expandable confidence breakdown */}
        <button
          onClick={() => setShowConfidenceBreakdown((v) => !v)}
          className="mt-3 text-xs text-sky-400 hover:text-sky-300 transition-colors cursor-pointer"
        >
          {showConfidenceBreakdown ? "▴ Hide breakdown" : "▾ View Confidence Breakdown"}
        </button>

        {showConfidenceBreakdown && (
          <div className="mt-3 space-y-1.5 animate-slide-up">
            {Object.entries(result.confidence_breakdown).map(([k, v]) => (
              <div key={k} className="space-y-0.5">
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>{CONFIDENCE_LABELS[k] ?? k}</span>
                  <span className="font-mono">{(v * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-sky-500 to-emerald-400 rounded-full transition-all duration-500"
                    style={{ width: `${Math.max(4, v * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Tabs ──────────────────────────────────────────── */}
      <div className="flex border-b border-slate-800/60 bg-slate-950/30">
        <button className={tabClass("answer")} onClick={() => setTab("answer")}>Answer</button>
        <button className={tabClass("evidence")} onClick={() => setTab("evidence")}>
          Evidence {result.evidence.length > 0 ? `(${result.evidence.length})` : ""}
        </button>
        <button className={tabClass("reasoning")} onClick={() => setTab("reasoning")}>Reasoning</button>
        <button className={tabClass("export")} onClick={() => setTab("export")}>Export</button>
      </div>

      {/* ── Tab Content ───────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">

        {/* ANSWER TAB */}
        {tab === "answer" && (
          <div className="p-5 space-y-4">
            {/* The answer text */}
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-2">
                EarthQuery Verified Answer
              </p>
              <p className="text-sm text-slate-100 leading-relaxed whitespace-pre-line font-normal">
                {result.answer}
              </p>
            </div>

            {/* Evidence Lens Call to Action */}
            <div className="rounded-xl bg-gradient-to-r from-sky-950/60 to-indigo-950/60 border border-sky-500/40 p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-sky-300">
                  Ground-Truth Proof
                </span>
                <span className="text-[10px] font-mono text-emerald-400">
                  {result.artifacts.length} Artifacts Available
                </span>
              </div>
              <button
                onClick={() => onOpenEvidenceLens && onOpenEvidenceLens(null)}
                className="w-full py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs shadow-md transition-all cursor-pointer flex items-center justify-center gap-1.5"
              >
                <span>🔍</span> SHOW EVIDENCE LENS
              </button>
            </div>

            {/* Audited Claims */}
            {claims.length > 0 && (
              <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3 space-y-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                  Traceable Claims ({claims.length})
                </span>
                <div className="space-y-1.5">
                  {claims.map((c) => (
                    <div
                      key={c.id}
                      className="p-2 rounded-lg border border-slate-800 bg-slate-900/70 flex items-center justify-between"
                    >
                      <span className="text-xs text-slate-200 pr-2">{c.text}</span>
                      <button
                        onClick={() => onOpenEvidenceLens && onOpenEvidenceLens(c)}
                        className="shrink-0 px-2 py-0.5 rounded bg-sky-950 border border-sky-700 text-[10px] font-mono text-sky-300 hover:bg-sky-900 cursor-pointer"
                      >
                        Inspect ↗
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Globe evidence CTA */}
            {result.location.features.length > 0 && (
              <div className="rounded-xl bg-slate-800/40 border border-slate-700/60 p-3.5 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-200">
                    {result.location.features.length} regions on globe
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">

                    Spatial evidence rendered on the 3D Earth
                  </p>
                </div>
                {onHighlightEvidence && (
                  <button
                    onClick={onHighlightEvidence}
                    className="rounded-lg bg-sky-600 hover:bg-sky-500 px-3.5 py-2 text-xs font-semibold text-white transition-colors shadow"
                  >
                    View on Globe
                  </button>
                )}
              </div>
            )}

            {/* Uncertainty flags */}
            {result.uncertainty.length > 0 && (
              <div className="space-y-2">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                  Uncertainty Flags
                </p>
                {result.uncertainty.map((u, i) => (
                  <div key={i} className="text-xs rounded-lg bg-slate-800/40 border border-slate-700/50 p-3 space-y-0.5">
                    <span className={`font-semibold font-mono ${SEV_COLOR[u.severity] ?? "text-slate-400"}`}>
                      [{u.severity.toUpperCase()}] {u.signal}
                    </span>
                    <p className="text-slate-400">{u.explanation}</p>
                  </div>
                ))}
              </div>
            )}

            {/* SOPs if present */}
            {sops.length > 0 && (
              <div className="space-y-2">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                  Disaster Response Protocols
                </p>
                {sops.map((sop) => (
                  <div key={sop.sop_id} className="rounded-xl bg-sky-950/30 border border-sky-800/40 p-3.5 text-xs space-y-1.5">
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-semibold text-sky-200 leading-tight">{sop.title}</span>
                      <span className="shrink-0 text-[9px] font-mono text-sky-400 bg-sky-950/60 border border-sky-800 px-1.5 py-0.5 rounded">
                        {sop.sop_id}
                      </span>
                    </div>
                    <p className="text-slate-400 text-[10px]">
                      Authority: <span className="text-slate-300">{sop.authority}</span>
                    </p>
                    <ul className="list-disc list-inside space-y-0.5 text-slate-300 text-[10px]">
                      {sop.action_protocols.map((act, i) => (
                        <li key={i}>{act}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* EVIDENCE TAB */}
        {tab === "evidence" && (
          <div className="p-5 space-y-4">
            {/* Categorized evidence */}
            <div className="space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-3">
                Agent Evidence Chain
              </p>

              {result.evidence.length === 0 ? (
                <p className="text-xs text-slate-500">No structured evidence entries.</p>
              ) : (
                result.evidence.map((e, i) => (
                  <div key={i} className="rounded-lg bg-slate-800/30 border border-slate-700/50 p-3 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-semibold text-sky-300">{e.agent}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-slate-500 text-[10px]">{e.type}</span>
                        {e.confidence !== undefined && (
                          <span className="text-[10px] font-mono text-slate-300">
                            {(e.confidence * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="text-slate-300 leading-relaxed">{e.summary}</p>
                  </div>
                ))
              )}
            </div>

            {/* Highlight on globe */}
            {onHighlightEvidence && result.location.features.length > 0 && (
              <button
                onClick={onHighlightEvidence}
                className="w-full rounded-lg border border-sky-700/60 bg-sky-950/40 hover:bg-sky-900/50 py-2.5 text-sm font-medium text-sky-300 transition-colors"
              >
                🎯 Highlight Evidence on Globe
              </button>
            )}
          </div>
        )}

        {/* REASONING TAB */}
        {tab === "reasoning" && (
          <div className="p-5 space-y-4">
            {/* Pipeline summary (collapsed by default) */}
            <div className="rounded-xl bg-slate-800/30 border border-slate-700/50 overflow-hidden">
              <button
                onClick={() => setShowPipeline((v) => !v)}
                className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/40 transition-colors"
              >
                <div className="space-y-0.5">
                  <p className="text-sm font-medium text-slate-200">Autonomous Agent Pipeline</p>
                  <p className="text-xs text-slate-400">
                    {totalAgents} specialists executed · {totalSec}s total
                  </p>
                </div>
                <span className="text-slate-400 text-sm">{showPipeline ? "▴" : "▾"}</span>
              </button>

              {showPipeline && (
                <div className="border-t border-slate-700/50 p-4 space-y-0 animate-slide-up">
                  {result.execution_trace.map((t, i) => (
                    <div key={i} className="flex items-center justify-between py-1.5 border-b border-slate-800/60 last:border-0">
                      <div>
                        <span className="text-xs font-mono text-sky-300">{t.agent}</span>
                        <span className="text-xs text-slate-500 ml-2">{t.action}</span>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] font-mono">
                        <span className={t.status === "ok" ? "text-emerald-400" : "text-amber-400"}>
                          {t.status}
                        </span>
                        <span className="text-slate-400">{t.duration_ms}ms</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Plan rationale */}
            {result.plan_rationale && (
              <div className="text-xs text-slate-400 space-y-1">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-2">
                  Autonomous Planner Reasoning
                </p>
                <pre className="font-mono text-[10px] bg-slate-950/60 border border-slate-800 rounded-lg p-3 overflow-auto whitespace-pre-wrap text-slate-300">
                  {JSON.stringify(result.plan_rationale, null, 2)}
                </pre>
              </div>
            )}

            {/* GIS Code */}
            {result.generated_code.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-3">
                  Generated GIS Code
                  <span className="ml-2 text-emerald-400 font-mono">✓ AST Validated</span>
                </p>
                <CodePanel code={result.generated_code} />
              </div>
            )}
          </div>
        )}

        {/* EXPORT TAB */}
        {tab === "export" && (
          <div className="p-5 space-y-4">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              Export Intelligence Dossier
            </p>
            <p className="text-sm text-slate-300 leading-relaxed">
              Download the full analytical package including GeoJSON vector masks, GeoTIFF change rasters, uncertainty breakdown, and execution logs.
            </p>

            {/* Generated artifacts */}
            {result.artifacts.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mb-2">
                  Generated Files
                </p>
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
          </div>
        )}
      </div>
    </div>
  );
}
