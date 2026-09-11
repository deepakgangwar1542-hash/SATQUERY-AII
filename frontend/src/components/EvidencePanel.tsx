import type { EvidenceEntry, SopEntry, UncertaintyNote } from "../services/types";

interface Props {
  evidence: EvidenceEntry[];
  uncertainty: UncertaintyNote[];
  trace: { timestamp: string; agent: string; action: string; duration_ms: number; status: string }[];
  sops?: SopEntry[];
}

const SEV_STYLE: Record<string, string> = {
  high: "text-rose-400",
  medium: "text-amber-400",
  low: "text-slate-400",
};

/** "WHY THIS ANSWER?" — rendered from structured evidence & RAG disaster protocols (FR-16). */
export function EvidencePanel({ evidence, uncertainty, trace, sops }: Props) {
  return (
    <div className="space-y-4">
      {/* RAG Curated SOP Section */}
      {sops && sops.length > 0 && (
        <section className="rounded-xl border border-sky-500/30 bg-sky-950/20 p-3 space-y-2.5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-sky-300 flex items-center gap-1.5">
              <span>📋</span> Operational Disaster & Response Protocols (RAG)
            </span>
            <span className="rounded-full bg-sky-900/60 px-2 py-0.5 text-[9px] font-mono text-sky-300">
              {sops.length} active guidelines
            </span>
          </div>

          <div className="space-y-2">
            {sops.map((sop) => (
              <div
                key={sop.sop_id}
                className="rounded-lg border border-slate-800/80 bg-slate-900/80 p-2.5 space-y-1 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-sky-200">{sop.title}</span>
                  <span className="rounded bg-sky-900/60 px-1.5 py-0.5 text-[9px] font-mono text-sky-300">
                    {sop.sop_id}
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 font-medium">
                  Authoritative Framework: <span className="text-slate-300">{sop.authority}</span>
                </div>
                <div className="text-[11px] text-slate-300 pt-1">
                  <span className="text-amber-400 font-semibold block mb-0.5">
                    Recommended Action Protocols:
                  </span>
                  <ul className="list-disc list-inside space-y-0.5 text-slate-300 text-[10px]">
                    {sop.action_protocols.map((act, aIdx) => (
                      <li key={aIdx}>{act}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {/* Evidence Chain */}
        <section>
          <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">
            Evidence Chain
          </h3>
          <ul className="space-y-2">
            {evidence.map((e, i) => (
              <li key={i} className="rounded-lg border border-slate-800 bg-slate-900/60 p-2.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-semibold text-sky-300">{e.agent}</span>
                  <span className="text-slate-500 text-[10px]">{e.type}</span>
                  {e.confidence !== undefined && (
                    <span className="text-slate-400 font-mono text-[10px]">
                      {(e.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                <p className="mt-1 text-slate-300 leading-relaxed">{e.summary}</p>
              </li>
            ))}
            {evidence.length === 0 && (
              <li className="text-xs text-slate-600">No evidence entries collected yet.</li>
            )}
          </ul>
        </section>

        {/* Uncertainty & Telemetry */}
        <section>
          <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">
            Uncertainty Flags
          </h3>
          <ul className="space-y-2">
            {uncertainty.map((u, i) => (
              <li key={i} className="rounded-lg border border-slate-800/80 bg-slate-900/40 p-2 text-xs">
                <span className={`font-mono text-[11px] font-semibold ${SEV_STYLE[u.severity] ?? "text-slate-400"}`}>
                  [{u.severity.toUpperCase()}] {u.signal}
                </span>
                <p className="text-slate-400 text-[11px] mt-0.5">{u.explanation}</p>
              </li>
            ))}
            {uncertainty.length === 0 && (
              <li className="text-xs text-emerald-500/80">Zero uncertainty flags raised.</li>
            )}
          </ul>

          <h3 className="mt-4 mb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">
            Execution Trace
          </h3>
          <ol className="max-h-48 space-y-0.5 overflow-y-auto font-mono text-[10px] text-slate-500 bg-slate-950/60 rounded p-2 border border-slate-800/60">
            {trace.map((t, i) => (
              <li key={i} className="flex items-center justify-between">
                <span className={t.status === "ok" ? "text-slate-400" : "text-rose-400"}>
                  {t.agent}:{t.action}
                </span>
                <span className="text-sky-400/80">{t.duration_ms}ms</span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}
