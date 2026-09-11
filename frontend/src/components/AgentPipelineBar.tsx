/**
 * AgentPipelineBar — Bottom drawer bar (~55px collapsed)
 *
 * Collapsed: "✦ AUTONOMOUS ANALYSIS · 9 specialists · 2.8s · [ Expand ]"
 * Expanded:  Full execution trace from real backend with timing per agent.
 *
 * Never renders fake execution — only shows agents that actually ran.
 */
import { useState } from "react";
import type { TraceEvent, AgentStatus } from "../services/types";

interface Props {
  isAnalyzing: boolean;
  completedTrace: TraceEvent[];
  liveAgents: AgentStatus[];
  progress: number;
}

const AGENT_META: Record<string, { label: string; icon: string }> = {
  orchestrator: { label: "Orchestrator", icon: "🧠" },
  planner: { label: "Query Planner", icon: "🧭" },
  input_validator: { label: "Spatial Validator", icon: "🛡️" },
  validator: { label: "Spatial Validator", icon: "🛡️" },
  perception: { label: "Optical Perception", icon: "👁️" },
  change_agent: { label: "Change Detection", icon: "🔄" },
  change: { label: "Change Detection", icon: "🔄" },
  change_vqa: { label: "Temporal VQA", icon: "💬" },
  grounding: { label: "Spatial Grounding", icon: "🎯" },
  rag: { label: "Knowledge RAG", icon: "📋" },
  gis_code: { label: "GIS Code Engine", icon: "💻" },
  gis_code_agent: { label: "GIS Code Engine", icon: "💻" },
  evidence_aggregator: { label: "Evidence Aggregator", icon: "📊" },
  verifier: { label: "Confidence Verifier", icon: "⚖️" },
};

export function AgentPipelineBar({ isAnalyzing, completedTrace, liveAgents, progress }: Props) {
  const [expanded, setExpanded] = useState(false);

  const totalMs = completedTrace.reduce((a, t) => a + (t.duration_ms || 0), 0);
  const totalSec = (totalMs / 1000).toFixed(1);
  const uniqueAgents = new Set(completedTrace.map((t) => t.agent)).size;

  const hasData = completedTrace.length > 0 || isAnalyzing;

  return (
    <div className="shrink-0 border-t border-slate-800/60 bg-slate-950/90 backdrop-blur-xl z-30">
      {/* ── COLLAPSED BAR ────────────────────────────────── */}
      <div
        className="flex items-center justify-between px-5 cursor-pointer hover:bg-slate-900/40 transition-colors"
        style={{ height: expanded ? "auto" : "52px" }}
        onClick={() => !expanded && hasData && setExpanded(true)}
      >
        <div className="flex items-center gap-3 h-[52px]">
          <span className={`h-2 w-2 rounded-full shrink-0 ${
            isAnalyzing ? "bg-amber-400 animate-ping" :
            completedTrace.length > 0 ? "bg-emerald-400" : "bg-slate-600"
          }`} />
          <span className="text-xs font-semibold uppercase tracking-widest text-slate-300">
            Autonomous Analysis
          </span>

          {/* Live progress */}
          {isAnalyzing && (
            <div className="flex items-center gap-2">
              <div className="w-28 h-1 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-sky-500 to-indigo-400 transition-all duration-700 rounded-full"
                  style={{ width: `${Math.max(8, progress)}%` }}
                />
              </div>
              <span className="text-[10px] font-mono text-sky-400">{progress}%</span>
            </div>
          )}

          {/* Completed summary */}
          {!isAnalyzing && completedTrace.length > 0 && (
            <span className="text-xs text-slate-400 font-mono">
              ✓ {uniqueAgents} specialists · {totalSec}s
            </span>
          )}

          {/* Idle state */}
          {!isAnalyzing && completedTrace.length === 0 && (
            <span className="text-xs text-slate-600">Ready</span>
          )}
        </div>

        <div className="flex items-center gap-3 h-[52px]">
          {/* Live agent feed (analyzing) */}
          {isAnalyzing && (
            <div className="hidden md:flex items-center gap-1 text-[10px] text-slate-500">
              {liveAgents.filter((a) => a.status === "running").map((a) => (
                <span key={a.name} className="text-amber-400 animate-pulse font-mono">
                  {AGENT_META[a.name]?.icon} {AGENT_META[a.name]?.label || a.name}
                </span>
              ))}
            </div>
          )}

          {/* Expand / collapse */}
          {hasData && (
            <button
              onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
              className="text-xs text-sky-400 hover:text-sky-300 font-medium transition-colors border border-slate-700/60 px-3 py-1 rounded-lg"
            >
              {expanded ? "▼ Collapse" : "▲ View Pipeline"}
            </button>
          )}
        </div>
      </div>

      {/* ── EXPANDED PIPELINE ─────────────────────────────── */}
      {expanded && (
        <div className="border-t border-slate-800/60 p-4 animate-slide-up max-h-56 overflow-y-auto">
          {completedTrace.length === 0 && isAnalyzing ? (
            <p className="text-xs text-slate-500 text-center py-4">
              Execution trace will appear here as agents complete…
            </p>
          ) : (
            <div className="space-y-1">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-3">
                Execution Telemetry — Actual Runtime Trace
              </p>
              {completedTrace.map((t, i) => {
                const meta = AGENT_META[t.agent.toLowerCase()] ?? {
                  label: t.agent,
                  icon: "⚡",
                };
                return (
                  <div
                    key={i}
                    className="flex items-center justify-between py-1.5 border-b border-slate-800/40 last:border-0"
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="text-sm">{meta.icon}</span>
                      <div>
                        <span className="text-xs font-medium text-slate-200">{meta.label}</span>
                        <span className="text-[10px] text-slate-500 ml-2">{t.action}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] font-mono shrink-0">
                      <span className={t.status === "ok" ? "text-emerald-400" : "text-amber-400"}>
                        {t.status === "ok" ? "✓" : "!"}
                      </span>
                      <span className="text-slate-400">{t.duration_ms}ms</span>
                    </div>
                  </div>
                );
              })}

              {/* Summary footer */}
              {completedTrace.length > 0 && (
                <div className="flex items-center justify-between pt-2 text-[10px] text-slate-500 font-mono">
                  <span>{uniqueAgents} unique agents</span>
                  <span>Total: {totalMs}ms ({totalSec}s)</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
