/**
 * EvidenceProvenanceGraph — clickable execution provenance chain.
 *
 * Every node is derived from real backend data:
 *   - input assets (result.location / evidence)
 *   - each recorded execution_trace step (agent, action, duration, status)
 *   - the final verified answer (confidence + consistency verdict)
 *
 * There are NO hardcoded fallbacks. When a field is missing the node is
 * simply not rendered, so the graph never invents numbers or steps.
 */
import { useState } from "react";
import type { QueryResult, TraceEvent } from "../services/types";

interface Props {
  result: QueryResult;
}

function statusStyle(status: string): { dot: string; text: string } {
  const s = status.toLowerCase();
  if (s === "ok" || s === "completed" || s === "success")
    return { dot: "bg-emerald-400", text: "text-emerald-300" };
  if (s === "skipped") return { dot: "bg-slate-500", text: "text-slate-400" };
  if (s === "conflict" || s === "replan")
    return { dot: "bg-amber-400", text: "text-amber-300" };
  if (s === "failed" || s === "error")
    return { dot: "bg-rose-400", text: "text-rose-300" };
  return { dot: "bg-sky-400", text: "text-sky-300" };
}

export function EvidenceProvenanceGraph({ result }: Props) {
  const [selected, setSelected] = useState<number | null>(null);

  const trace: TraceEvent[] = result.execution_trace ?? [];
  const evidenceCount = result.evidence?.length ?? 0;
  const featureCount = result.location?.features?.length ?? 0;
  const totalMs = trace.reduce((acc, t) => acc + (t.duration_ms || 0), 0);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4 font-sans text-xs text-slate-200">
      <div className="mb-4 flex items-center justify-between border-b border-slate-800/80 pb-2">
        <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-200">
          Execution Provenance
        </h3>
        <span className="font-mono text-[10px] text-slate-400">
          Trace ID: {result.job_id}
        </span>
      </div>

      <div className="flex flex-col">
        {/* Input node */}
        <div className="rounded-lg border border-slate-700/60 bg-slate-900/80 px-3 py-2">
          <span className="block text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400">
            Inputs
          </span>
          <span className="mt-0.5 block text-xs text-slate-200">
            {featureCount} map feature{featureCount === 1 ? "" : "s"} · {evidenceCount} evidence entr
            {evidenceCount === 1 ? "y" : "ies"}
            {result.sensor_selection?.primary
              ? ` · primary ${result.sensor_selection.primary.toUpperCase()}`
              : ""}
          </span>
        </div>

        {/* Trace step nodes */}
        {trace.map((t, i) => {
          const st = statusStyle(t.status);
          const isOpen = selected === i;
          return (
            <div key={i} className="flex flex-col items-stretch">
              <div className="ml-4 h-3 w-0.5 bg-slate-700" aria-hidden />
              <button
                onClick={() => setSelected(isOpen ? null : i)}
                className={`flex items-center justify-between rounded-lg border px-3 py-2 text-left transition-all cursor-pointer ${
                  isOpen
                    ? "border-sky-400 bg-sky-950/40"
                    : "border-slate-800 bg-slate-900/80 hover:border-slate-600"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`h-2 w-2 shrink-0 rounded-full ${st.dot}`} />
                  <span className="font-mono text-xs text-sky-300 shrink-0">{t.agent}</span>
                  <span className="truncate text-[11px] text-slate-400">{t.action}</span>
                </div>
                <div className="flex shrink-0 items-center gap-2 font-mono text-[10px]">
                  <span className={st.text}>{t.status}</span>
                  <span className="text-slate-500">{t.duration_ms}ms</span>
                </div>
              </button>
              {isOpen && (
                <div className="ml-4 mt-1 rounded-lg border border-slate-700 bg-slate-900/90 px-3 py-2 text-[11px] leading-relaxed text-slate-300 animate-slide-up">
                  <p>
                    <span className="text-slate-500">Agent:</span> {t.agent} ·{" "}
                    <span className="text-slate-500">Action:</span> {t.action}
                  </p>
                  <p className="mt-0.5">
                    <span className="text-slate-500">Status:</span> {t.status} ·{" "}
                    <span className="text-slate-500">Duration:</span> {t.duration_ms}ms
                    {t.timestamp ? (
                      <>
                        {" "}
                        · <span className="text-slate-500">At:</span> {t.timestamp}
                      </>
                    ) : null}
                  </p>
                  {t.detail && <p className="mt-0.5 text-slate-400">{t.detail}</p>}
                </div>
              )}
            </div>
          );
        })}

        {/* Final answer node */}
        <div className="ml-4 h-3 w-0.5 bg-slate-700" aria-hidden />
        <div className="rounded-lg border border-sky-500/40 bg-slate-900 px-3 py-2.5">
          <span className="block text-[10px] font-mono font-bold uppercase tracking-wider text-sky-400">
            Final Answer & Verified Claims
          </span>
          {result.answer && (
            <p className="mt-1 line-clamp-2 text-xs text-slate-100">{result.answer}</p>
          )}
          <span className="mt-1.5 inline-block rounded border border-emerald-500/30 bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] font-semibold text-emerald-300">
            {Math.round(result.confidence * 100)}% confidence · {result.consistency_verdict}
          </span>
        </div>
      </div>

      <p className="mt-3 border-t border-slate-800/60 pt-2 text-[10px] font-mono text-slate-500">
        {trace.length} step{trace.length === 1 ? "" : "s"} · {(totalMs / 1000).toFixed(1)}s total
      </p>
    </div>
  );
}
