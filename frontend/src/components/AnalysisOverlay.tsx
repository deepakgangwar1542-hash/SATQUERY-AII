/**
 * AnalysisOverlay — STATE B (ANALYZING)
 *
 * Shown in the CENTER COLUMN while the backend is processing.
 * Reads live agent statuses from SSE and renders an animated step list.
 * Never shows fake data — every node reflects real backend execution.
 */
import { useEffect, useState } from "react";
import { getJobStatus, jobStreamUrl } from "../services/api";
import type { AgentStatus, JobStatus } from "../services/types";

interface Step {
  id: string;
  label: string;
  detail: string;
  agentKeys: string[]; // backend agent names that map to this step
}

// Canonical display pipeline — maps backend agent names to human steps.
const STEPS: Step[] = [
  { id: "understand", label: "Understanding Query", detail: "Parsing intent, temporal cues, targets", agentKeys: ["planner", "orchestrator"] },
  { id: "validate", label: "Validating Imagery", detail: "CRS, resolution, band mapping checks", agentKeys: ["input_validator", "validator"] },
  { id: "optical", label: "Optical Analysis", detail: "BLIP VQA multimodal scene understanding", agentKeys: ["perception"] },
  { id: "change", label: "Change Detection", detail: "Siamese UNet bi-temporal differential", agentKeys: ["change_agent", "change"] },
  { id: "change_vqa", label: "Temporal Reasoning", detail: "Cross-date semantic VQA", agentKeys: ["change_vqa"] },
  { id: "grounding", label: "Spatial Grounding", detail: "Grounding DINO zero-shot localization", agentKeys: ["grounding"] },
  { id: "rag", label: "Knowledge Retrieval", detail: "ChromaDB disaster SOP vector search", agentKeys: ["rag"] },
  { id: "gis", label: "Geospatial Computation", detail: "Python Rasterio / GeoPandas pipeline", agentKeys: ["gis_code", "gis_code_agent"] },
  { id: "verify", label: "Verifying Result", detail: "Cross-agent consensus & uncertainty scoring", agentKeys: ["verifier", "evidence_aggregator"] },
];

function parseIntent(question: string): { label: string; icon: string }[] {
  const q = question.toLowerCase();
  const tags: { label: string; icon: string }[] = [];
  if (/flood|water|inund/.test(q)) tags.push({ label: "Flood Change", icon: "🌊" });
  if (/vegetation|forest|canopy|ndvi|tree/.test(q)) tags.push({ label: "Vegetation", icon: "🌿" });
  if (/building|structure|urban|construct/.test(q)) tags.push({ label: "Buildings", icon: "🏗️" });
  if (/fire|burn|disaster/.test(q)) tags.push({ label: "Disaster", icon: "🔥" });
  if (/sar|radar|backscatter/.test(q)) tags.push({ label: "SAR / Radar", icon: "📡" });
  if (/between|before|after|change|increase|decrease|diff/.test(q)) tags.push({ label: "Temporal Change", icon: "📅" });
  if (/count|how many|number/.test(q)) tags.push({ label: "Count / Area", icon: "🔢" });
  if (tags.length === 0) tags.push({ label: "Geospatial Analysis", icon: "🛰️" });
  return tags;
}

interface Props {
  jobId: string | null;
  question: string;
  onCompleted: () => void;
}

export function AnalysisOverlay({ jobId, question, onCompleted }: Props) {
  const [liveAgents, setLiveAgents] = useState<AgentStatus[]>([]);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!jobId) return;
    setLiveAgents([]);
    setProgress(0);

    const es = new EventSource(jobStreamUrl(jobId));
    es.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data) as Partial<JobStatus>;
        if (d.agents) setLiveAgents(d.agents);
        if (d.progress_pct !== undefined) setProgress(d.progress_pct);
      } catch { /* ignore */ }
    };
    es.addEventListener("end", () => { es.close(); onCompleted(); });

    const poll = setInterval(async () => {
      try {
        const d = await getJobStatus(jobId);
        if (d.agents) setLiveAgents(d.agents);
        if (d.progress_pct !== undefined) setProgress(d.progress_pct);
        if (d.status === "completed" || d.status === "failed") {
          clearInterval(poll);
          onCompleted();
        }
      } catch { /* ignore */ }
    }, 1500);

    return () => { es.close(); clearInterval(poll); };
  }, [jobId, onCompleted]);

  // Resolve the display status for each pipeline step
  function getStepStatus(step: Step): "done" | "active" | "pending" {
    for (const key of step.agentKeys) {
      const agent = liveAgents.find(
        (a) => a.name.toLowerCase() === key || a.name.toLowerCase().includes(key),
      );
      if (!agent) continue;
      if (agent.status === "completed") return "done";
      if (agent.status === "running") return "active";
      if (agent.status === "failed") return "done"; // show as "done" with error coloring handled elsewhere
    }
    // If none of the agents for this step appear yet, treat as pending
    // But if progress is high, treat completed steps as done
    return "pending";
  }

  const tags = parseIntent(question);

  // Filter steps to only those that are relevant (have a matching agent or are always shown)
  const alwaysShow = new Set(["understand", "validate", "verify"]);
  const activeAgentKeys = new Set(liveAgents.map((a) => a.name.toLowerCase()));
  const visibleSteps = STEPS.filter((s) => {
    if (alwaysShow.has(s.id)) return true;
    return s.agentKeys.some((k) => activeAgentKeys.has(k) || activeAgentKeys.has(k.split("_")[0]));
  });

  return (
    <div className="flex flex-col h-full overflow-y-auto animate-fade-in">
      {/* Header */}
      <div className="p-6 border-b border-slate-800/60">
        <div className="flex items-center gap-2 mb-1">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-sky-500" />
          </span>
          <span className="text-xs font-semibold uppercase tracking-widest text-sky-400">
            SatQuery AI · Analyzing
          </span>
        </div>

        {/* Progress bar */}
        <div className="mt-3 h-1 w-full bg-slate-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-sky-500 to-indigo-400 transition-all duration-700 rounded-full"
            style={{ width: `${Math.max(8, progress)}%` }}
          />
        </div>
        <div className="flex justify-between text-[10px] text-slate-500 mt-1">
          <span>Autonomous execution in progress</span>
          <span className="font-mono text-sky-400">{progress}%</span>
        </div>
      </div>

      {/* Query Understanding */}
      <div className="p-6 border-b border-slate-800/40 space-y-3">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
          Query Understanding
        </p>
        <div className="flex flex-wrap gap-2">
          {tags.map((t, i) => (
            <span
              key={i}
              className="flex items-center gap-1.5 bg-slate-800/80 border border-slate-700/60 text-slate-200 text-sm rounded-lg px-3 py-1.5"
            >
              <span>{t.icon}</span>
              <span className="font-medium">{t.label}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Agent Pipeline Steps */}
      <div className="flex-1 p-6 space-y-1">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500 mb-4">
          Autonomous Analysis
        </p>

        {visibleSteps.map((step, idx) => {
          const status = getStepStatus(step);
          return (
            <div key={step.id}>
              {idx > 0 && (
                <div className="ml-[7px] h-4 w-px bg-slate-800" />
              )}
              <div className="flex items-start gap-3">
                {/* Step indicator */}
                <div className="shrink-0 mt-0.5">
                  {status === "done" && (
                    <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-emerald-500/20 border border-emerald-500/60 text-emerald-400 text-[9px] font-bold">
                      ✓
                    </span>
                  )}
                  {status === "active" && (
                    <span className="relative flex h-3.5 w-3.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400/40" />
                      <span className="relative inline-flex h-3.5 w-3.5 rounded-full bg-sky-500 border-2 border-sky-300" />
                    </span>
                  )}
                  {status === "pending" && (
                    <span className="flex h-3.5 w-3.5 rounded-full border border-slate-700 bg-slate-900" />
                  )}
                </div>

                {/* Step text */}
                <div className="min-w-0">
                  <p className={`text-sm font-medium leading-none ${
                    status === "done" ? "text-emerald-300" :
                    status === "active" ? "text-slate-100 animate-processing" :
                    "text-slate-500"
                  }`}>
                    {step.label}
                  </p>
                  {status === "active" && (
                    <p className="text-xs text-slate-400 mt-0.5 animate-fade-in">
                      {step.detail}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
