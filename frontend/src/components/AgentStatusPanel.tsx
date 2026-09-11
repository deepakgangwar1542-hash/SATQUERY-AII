import { useEffect, useState } from "react";
import { getJobStatus, jobStreamUrl } from "../services/api";
import type { AgentStatus, JobStatus, TraceEvent } from "../services/types";

interface Props {
  jobId: string | null;
  onStatus: (s: JobStatus) => void;
  onCompleted: () => void;
}

const BADGE: Record<string, string> = {
  pending: "bg-slate-700 text-slate-300",
  running: "bg-amber-600 text-amber-50 animate-pulse",
  completed: "bg-emerald-700 text-emerald-100",
  failed: "bg-red-700 text-red-100",
  skipped: "bg-slate-800 text-slate-500",
};

/** Live agent status via SSE with polling fallback (§7.1 P1, FR-16). */
export function AgentStatusPanel({ jobId, onStatus, onCompleted }: Props) {
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<string>("");
  const [trace, setTrace] = useState<TraceEvent[]>([]);

  useEffect(() => {
    if (!jobId) return;
    setAgents([]); setProgress(0); setStatus("queued"); setTrace([]);

    const es = new EventSource(jobStreamUrl(jobId));
    es.onmessage = (ev) => {
      try { const d = JSON.parse(ev.data); refresh(d); } catch { /* ignore */ }
    };
    es.addEventListener("end", () => { es.close(); onCompleted(); });

    // polling fallback keeps the panel correct even if SSE drops
    const poll = setInterval(async () => {
      try { refresh(await getJobStatus(jobId)); } catch { /* job gone */ }
    }, 1500);

    async function refresh(d: Partial<JobStatus>) {
      if (d.agents) setAgents(d.agents);
      if (d.progress_pct !== undefined) setProgress(d.progress_pct);
      if (d.status) {
        setStatus(d.status);
        if (d.status === "completed" || d.status === "failed") {
          onStatus({ job_id: jobId!, status: d.status as any,
                     agents: d.agents ?? [], progress_pct: 100 });
          onCompleted();
        }
      }
    }

    return () => { es.close(); clearInterval(poll); };
  }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>Agent pipeline</span>
        <span className={status === "failed" ? "text-red-400" : ""}>{status}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded bg-slate-800">
        <div className="h-full bg-sky-500 transition-all" style={{ width: `${progress}%` }} />
      </div>
      <ul className="space-y-1">
        {agents.map((a) => (
          <li key={a.name} className="flex items-center justify-between text-xs">
            <span className="font-mono text-slate-300">{a.name}</span>
            <span className={`rounded px-1.5 py-0.5 ${BADGE[a.status] ?? BADGE.pending}`}>
              {a.status}
            </span>
          </li>
        ))}
        {agents.length === 0 && (
          <li className="text-xs text-slate-600">waiting for orchestrator…</li>
        )}
      </ul>
      {trace.length > 0 && (
        <div className="max-h-24 overflow-y-auto font-mono text-[10px] text-slate-500">
          {trace.slice(-6).map((t, i) => (
            <div key={i}>{t.timestamp} {t.agent}:{t.action} {t.status} {t.duration_ms}ms</div>
          ))}
        </div>
      )}
    </div>
  );
}
