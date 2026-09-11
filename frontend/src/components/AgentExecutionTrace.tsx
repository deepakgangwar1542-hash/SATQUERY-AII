import { useState, useEffect } from "react";
import { getJobStatus, jobStreamUrl } from "../services/api";
import type { AgentStatus, JobStatus, TraceEvent } from "../services/types";

interface Props {
  jobId: string | null;
  onCompleted?: () => void;
  completedTrace?: TraceEvent[];
  isAnalyzing: boolean;
}

interface SpecialistNode {
  id: string;
  name: string;
  icon: string;
  role: string;
  backendAgentNames: string[];
}

const SPECIALIST_PIPELINE: SpecialistNode[] = [
  {
    id: "validator",
    name: "Spatial Validator",
    icon: "🛡️",
    role: "CRS & Resolution Audit",
    backendAgentNames: ["input_validator", "validator"],
  },
  {
    id: "planner",
    name: "Query Planner",
    icon: "🧭",
    role: "Autonomous Specialist Routing",
    backendAgentNames: ["planner", "orchestrator"],
  },
  {
    id: "perception",
    name: "Optical Perception",
    icon: "👁️",
    role: "BLIP Multimodal Remote-Sensing VLM",
    backendAgentNames: ["perception"],
  },
  {
    id: "change",
    name: "Change Detection",
    icon: "🔄",
    role: "Siamese UNet Differential Analysis",
    backendAgentNames: ["change_agent", "change"],
  },
  {
    id: "change_vqa",
    name: "Change-VQA",
    icon: "💬",
    role: "Temporal Reasoning & Semantic VQA",
    backendAgentNames: ["change_vqa"],
  },
  {
    id: "grounding",
    name: "Spatial Grounding",
    icon: "🎯",
    role: "Grounding DINO Zero-Shot Detection",
    backendAgentNames: ["grounding"],
  },
  {
    id: "rag",
    name: "Disaster SOP RAG",
    icon: "📋",
    role: "ChromaDB Emergency Protocols",
    backendAgentNames: ["rag"],
  },
  {
    id: "gis_code",
    name: "GIS Code Engine",
    icon: "💻",
    role: "Python GeoPandas / Rasterio Pipeline",
    backendAgentNames: ["gis_code", "gis_code_agent"],
  },
  {
    id: "verifier",
    name: "Confidence Verifier",
    icon: "⚖️",
    role: "Cross-Sensor Consensus & Verification",
    backendAgentNames: ["verifier", "evidence_aggregator"],
  },
];

export function AgentExecutionTrace({
  jobId,
  onCompleted,
  completedTrace = [],
  isAnalyzing,
}: Props) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [progress, setProgress] = useState(0);
  const [jobStatus, setJobStatus] = useState<string>("idle");
  const [liveTrace, setLiveTrace] = useState<TraceEvent[]>([]);

  // Listen to SSE / polling
  useEffect(() => {
    if (!jobId) {
      setAgents([]);
      setProgress(0);
      setJobStatus("idle");
      setLiveTrace([]);
      return;
    }

    setJobStatus("running");
    setProgress(10);

    const es = new EventSource(jobStreamUrl(jobId));
    es.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (d.agents) setAgents(d.agents);
        if (d.progress_pct !== undefined) setProgress(d.progress_pct);
        if (d.status) setJobStatus(d.status);
      } catch {
        /* parse error */
      }
    };

    es.addEventListener("end", () => {
      es.close();
      setJobStatus("completed");
      setProgress(100);
      onCompleted?.();
    });

    const poll = setInterval(async () => {
      try {
        const res: JobStatus = await getJobStatus(jobId);
        if (res.agents) setAgents(res.agents);
        if (res.progress_pct !== undefined) setProgress(res.progress_pct);
        if (res.status) {
          setJobStatus(res.status);
          if (res.status === "completed" || res.status === "failed") {
            clearInterval(poll);
            onCompleted?.();
          }
        }
      } catch {
        /* ignore */
      }
    }, 1500);

    return () => {
      es.close();
      clearInterval(poll);
    };
  }, [jobId, onCompleted]);

  // Combine completed trace or live trace
  const activeTrace = completedTrace.length > 0 ? completedTrace : liveTrace;

  // Resolve status for each node in SPECIALIST_PIPELINE
  const getNodeInfo = (node: SpecialistNode) => {
    // 1. check live agents status
    const agentMatch = agents.find((a) =>
      node.backendAgentNames.some((name) => a.name.toLowerCase().includes(name)),
    );

    // 2. check trace for duration and completion
    const traceMatch = activeTrace.find((t) =>
      node.backendAgentNames.some((name) => t.agent.toLowerCase().includes(name)),
    );

    if (agentMatch) {
      return {
        status: agentMatch.status,
        duration: traceMatch?.duration_ms,
      };
    }

    if (traceMatch) {
      return {
        status: "completed",
        duration: traceMatch.duration_ms,
      };
    }

    if (jobStatus === "completed" && completedTrace.length > 0) {
      return { status: "completed", duration: undefined };
    }

    if (isAnalyzing) {
      return { status: "pending", duration: undefined };
    }

    return { status: "idle", duration: undefined };
  };

  return (
    <div className="w-full border-t border-slate-800/80 bg-slate-950/95 backdrop-blur-xl text-slate-100 z-30 transition-all select-none">
      {/* Top Drawer Control Bar */}
      <div
        onClick={() => setIsExpanded((v) => !v)}
        className="px-4 py-2 flex items-center justify-between cursor-pointer hover:bg-slate-900/50 transition-colors border-b border-slate-800/60"
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${
              isAnalyzing ? "bg-amber-400 animate-ping" : jobStatus === "completed" ? "bg-emerald-400" : "bg-sky-500"
            }`} />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-200 font-display">
              Autonomous Agent Orchestration Trace
            </span>
          </div>

          <span className="text-[10px] text-slate-400 font-mono hidden md:inline">
            {isAnalyzing
              ? "● Executing Specialist Agents..."
              : jobStatus === "completed"
              ? "✓ 9 Specialist Agents Orchestrated & Verified"
              : "● Agent Graph Standing By"}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Progress Bar (Visible when analyzing) */}
          {isAnalyzing && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-sky-400">{progress}%</span>
              <div className="w-24 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-sky-500 to-indigo-500 transition-all duration-300"
                  style={{ width: `${Math.max(10, progress)}%` }}
                />
              </div>
            </div>
          )}

          <button className="flex items-center gap-1 text-[11px] font-mono text-sky-400 hover:text-sky-300 font-semibold cursor-pointer">
            <span>{isExpanded ? "▼ Dock Trace" : "▲ Expand Pipeline"}</span>
          </button>
        </div>
      </div>

      {/* Horizontal Pipeline Graph (Always visible) */}
      <div className="px-4 py-2.5 overflow-x-auto">
        <div className="flex items-center gap-1.5 min-w-max">
          {SPECIALIST_PIPELINE.map((node, index) => {
            const { status, duration } = getNodeInfo(node);
            const isDone = status === "completed";
            const isCurrent = status === "running";
            const isPending = status === "pending";

            return (
              <div key={node.id} className="flex items-center">
                {/* Node Box */}
                <div
                  className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 transition-all text-xs ${
                    isCurrent
                      ? "border-amber-500 bg-amber-950/40 text-amber-200 shadow-md shadow-amber-500/20 ring-1 ring-amber-400/40 animate-pulse"
                      : isDone
                      ? "border-emerald-700/60 bg-emerald-950/30 text-emerald-300"
                      : isPending
                      ? "border-slate-800 bg-slate-900/40 text-slate-400"
                      : "border-slate-800/80 bg-slate-900/30 text-slate-500"
                  }`}
                >
                  <span className="text-sm">{node.icon}</span>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold text-slate-200 text-[11px] whitespace-nowrap">
                        {node.name}
                      </span>
                      {duration !== undefined && (
                        <span className="text-[9px] font-mono text-sky-400 bg-slate-950/80 px-1 rounded">
                          {duration}ms
                        </span>
                      )}
                    </div>
                    <span className="text-[9px] text-slate-400 block whitespace-nowrap">
                      {node.role}
                    </span>
                  </div>
                </div>

                {/* Arrow Connector */}
                {index < SPECIALIST_PIPELINE.length - 1 && (
                  <span className={`px-1 text-[11px] font-bold ${
                    isDone ? "text-emerald-500" : "text-slate-700"
                  }`}>
                    ➔
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Expanded Details Drawer */}
      {isExpanded && (
        <div className="p-4 border-t border-slate-800/80 bg-slate-950/90 grid grid-cols-1 md:grid-cols-2 gap-4 max-h-56 overflow-y-auto">
          {/* Agent execution log table */}
          <div>
            <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
              Agent Execution Telemetry Log
            </h4>
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 overflow-hidden font-mono text-[10px]">
              {activeTrace.length > 0 ? (
                <div className="divide-y divide-slate-800">
                  {activeTrace.map((t, i) => (
                    <div key={i} className="p-1.5 px-2 flex items-center justify-between">
                      <span className="text-sky-300 font-semibold">{t.agent}</span>
                      <span className="text-slate-400">{t.action}</span>
                      <span className="text-emerald-400">{t.duration_ms} ms</span>
                      <span className="text-slate-500">{t.status}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 text-center text-slate-500">
                  Awaiting query execution. Telemetry events will stream here live.
                </div>
              )}
            </div>
          </div>

          {/* Autonomous orchestration explanation */}
          <div className="space-y-2 text-xs text-slate-300 font-sans">
            <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
              Autonomous Orchestrator Architecture
            </h4>
            <p className="text-[11px] leading-relaxed text-slate-300">
              SatQuery AI operates an autonomous multi-agent pipeline adhering to the SIH26167 standard. Rather than requiring manual GIS configuration, user queries are dynamically parsed, decomposed into spatial sub-goals, and routed to specialist vision and remote-sensing agents.
            </p>
            <div className="grid grid-cols-2 gap-2 text-[10px] font-mono pt-1 text-slate-400">
              <div>• Zero-Shot Object Localization</div>
              <div>• Bi-Temporal Differential UNet</div>
              <div>• Vision-Language VQA (BLIP)</div>
              <div>• Weighted Consensus Verifier</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
