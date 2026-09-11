import { useEffect, useState } from "react";
import { getJobStatus, jobStreamUrl } from "../services/api";
import type { AgentStatus, JobStatus, TraceEvent } from "../services/types";

interface Props {
  jobId: string | null;
  onStatus: (s: JobStatus) => void;
  onCompleted: () => void;
}

const AGENT_META: Record<string, { label: string; icon: string; role: string }> = {
  planner: { label: "Planner", icon: "🧭", role: "Goal Decomposition & Routing" },
  validator: { label: "Spatial Validator", icon: "🛡️", role: "CRS & Resolution Audit" },
  perception: { label: "Perception (VLM)", icon: "👁️", role: "BLIP VQA Multimodal Reasoning" },
  grounding: { label: "Grounding (DINO)", icon: "🎯", role: "Zero-Shot Object Localization" },
  change: { label: "ChangeNet (UNet)", icon: "🔄", role: "Bi-Temporal Siamese Differential" },
  verifier: { label: "Verifier & Synthesis", icon: "⚖️", role: "Consensus & Uncertainty Scoring" },
  gis_code: { label: "GIS Code Engine", icon: "💻", role: "Deterministic Python/Rasterio Execution" },
};

const BADGE: Record<string, { bg: string; text: string; dot: string; pulse: boolean }> = {
  pending: { bg: "bg-slate-800/60 border-slate-700/50", text: "text-slate-400", dot: "bg-slate-500", pulse: false },
  running: { bg: "bg-amber-500/10 border-amber-500/40", text: "text-amber-300", dot: "bg-amber-400", pulse: true },
  completed: { bg: "bg-emerald-500/10 border-emerald-500/40", text: "text-emerald-300", dot: "bg-emerald-400", pulse: false },
  failed: { bg: "bg-rose-500/10 border-rose-500/40", text: "text-rose-300", dot: "bg-rose-400", pulse: false },
  skipped: { bg: "bg-slate-900/40 border-slate-800/40", text: "text-slate-600", dot: "bg-slate-700", pulse: false },
};

/** Live agent status via SSE with polling fallback (§7.1 P1, FR-16). */
export function AgentStatusPanel({ jobId, onStatus, onCompleted }: Props) {
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<string>("idle");
  const [trace, setTrace] = useState<TraceEvent[]>([]);

  useEffect(() => {
    if (!jobId) {
      setAgents([]); setProgress(0); setStatus("idle"); setTrace([]);
      return;
    }
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

  const isExecuting = status === "running" || status === "queued";

  return (
    <div className="space-y-3 rounded-xl border border-slate-800/80 bg-slate-900/50 p-3.5 backdrop-blur-md">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`h-2.5 w-2.5 rounded-full ${
            status === "completed" ? "bg-emerald-400" :
            isExecuting ? "bg-amber-400 animate-ping" :
            status === "failed" ? "bg-rose-400" : "bg-slate-600"
          }`} />
          <span className="text-xs font-semibold tracking-wider text-slate-200 uppercase">
            Agent Pipeline
          </span>
        </div>
        <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${
          status === "completed" ? "bg-emerald-950/60 border-emerald-700 text-emerald-300" :
          isExecuting ? "bg-amber-950/60 border-amber-700 text-amber-300 animate-pulse" :
          status === "failed" ? "bg-rose-950/60 border-rose-700 text-rose-300" :
          "bg-slate-800/60 border-slate-700 text-slate-400"
        }`}>
          {status}
        </span>
      </div>

      {/* Progress Bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-[10px] text-slate-400">
          <span>Execution Progress</span>
          <span className="font-mono font-medium text-sky-400">{progress}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-800/80 p-0.5 ring-1 ring-slate-700/40">
          <div
            className="h-full rounded-full bg-gradient-to-r from-sky-500 via-indigo-500 to-emerald-400 transition-all duration-500 shadow-sm shadow-sky-500/50"
            style={{ width: `${Math.max(progress, isExecuting ? 8 : 0)}%` }}
          />
        </div>
      </div>

      {/* Agent Step Nodes */}
      <div className="space-y-1.5 pt-1">
        {agents.length > 0 ? (
          agents.map((a) => {
            const meta = AGENT_META[a.name] ?? { label: a.name, icon: "⚡", role: "Specialized Task" };
            const badge = BADGE[a.status] ?? BADGE.pending;
            return (
              <div
                key={a.name}
                className={`flex items-center justify-between rounded-lg border px-2.5 py-1.5 transition-colors ${badge.bg}`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-sm">{meta.icon}</span>
                  <div className="truncate">
                    <div className="text-xs font-medium text-slate-200 leading-none">
                      {meta.label}
                    </div>
                    <div className="text-[10px] text-slate-500 truncate mt-0.5">
                      {meta.role}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0 pl-2">
                  <span className={`h-1.5 w-1.5 rounded-full ${badge.dot} ${badge.pulse ? "animate-ping" : ""}`} />
                  <span className={`text-[10px] font-mono font-semibold uppercase ${badge.text}`}>
                    {a.status}
                  </span>
                </div>
              </div>
            );
          })
        ) : (
          <div className="rounded-lg border border-dashed border-slate-800 p-3 text-center text-xs text-slate-500">
            {jobId ? "Initializing autonomous orchestrator..." : "Ready to plan and orchestrate agent tasks"}
          </div>
        )}
      </div>

      {/* Live execution trace mini-log */}
      {trace.length > 0 && (
        <div className="border-t border-slate-800/80 pt-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Telemetry Trace
          </div>
          <div className="max-h-20 overflow-y-auto space-y-1 font-mono text-[10px] text-slate-400 bg-slate-950/60 rounded p-1.5 border border-slate-800/50">
            {trace.slice(-5).map((t, i) => (
              <div key={i} className="flex items-center justify-between gap-1">
                <span className="text-slate-500 truncate">{t.agent}:{t.action}</span>
                <span className="text-sky-400 shrink-0 font-medium">{t.duration_ms}ms</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
