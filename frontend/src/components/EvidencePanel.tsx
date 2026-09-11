import type { EvidenceEntry, UncertaintyNote } from "../services/types";

interface Props {
  evidence: EvidenceEntry[];
  uncertainty: UncertaintyNote[];
  trace: { timestamp: string; agent: string; action: string; duration_ms: number; status: string }[];
}

const SEV_STYLE: Record<string, string> = {
  high: "text-red-400",
  medium: "text-amber-400",
  low: "text-slate-400",
};

/** "WHY THIS ANSWER?" — rendered from the structured evidence object only
 * (FR-16: never re-generated as disconnected free text). */
export function EvidencePanel({ evidence, uncertainty, trace }: Props) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <section>
        <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">
          Evidence chain
        </h3>
        <ul className="space-y-2">
          {evidence.map((e, i) => (
            <li key={i} className="rounded border border-slate-800 bg-slate-900/60 p-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-mono text-sky-300">{e.agent}</span>
                <span className="text-slate-500">{e.type}</span>
                {e.confidence !== undefined && (
                  <span className="text-slate-400">{(e.confidence * 100).toFixed(0)}%</span>
                )}
              </div>
              <p className="mt-1 text-slate-300">{e.summary}</p>
            </li>
          ))}
          {evidence.length === 0 && <li className="text-xs text-slate-600">no evidence yet</li>}
        </ul>
      </section>
      <section>
        <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">
          Uncertainty notes
        </h3>
        <ul className="space-y-2">
          {uncertainty.map((u, i) => (
            <li key={i} className="text-xs">
              <span className={`font-mono ${SEV_STYLE[u.severity] ?? "text-slate-400"}`}>
                [{u.severity}] {u.signal}
              </span>
              <p className="text-slate-400">{u.explanation}</p>
            </li>
          ))}
          {uncertainty.length === 0 && (
            <li className="text-xs text-emerald-500/80">no uncertainty flagged</li>
          )}
        </ul>
        <h3 className="mt-4 mb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase">
          Execution trace
        </h3>
        <ol className="max-h-56 space-y-0.5 overflow-y-auto font-mono text-[10px] text-slate-500">
          {trace.map((t, i) => (
            <li key={i}>
              <span className="text-slate-600">{t.timestamp}</span>{" "}
              <span className={t.status === "ok" ? "text-emerald-500/80" : "text-red-400"}>
                {t.agent}:{t.action}
              </span>{" "}
              {t.duration_ms}ms
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
