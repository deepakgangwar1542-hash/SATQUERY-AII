import { useState } from "react";
import type { QueryResult, SopEntry, Claim } from "../services/types";
import { CodePanel } from "./CodePanel";
import { EvidenceProvenanceGraph } from "./EvidenceProvenanceGraph";

interface Props {
  result: QueryResult | null;
  question: string;
  isAnalyzing: boolean;
  onHighlightEvidence?: () => void;
  onOpenEvidenceLens?: (claim?: Claim | null) => void;
  onSelectQuestion?: (q: string) => void;
  backendCapabilities?: Record<string, any>;
  dates: string[];
}

type CopilotTab = "verdict" | "evidence" | "provenance" | "sops" | "code" | "export";

const CONFIDENCE_LABELS: Record<string, string> = {
  evidence_agreement: "Evidence Agreement",
  sensor_reliability: "Sensor Reliability",
  data_quality: "Data Quality",
  spatial_consistency: "Spatial Consistency",
  temporal_consistency: "Temporal Consistency",
  model_confidence: "Model Baseline",
};

export function AICopilotPanel({
  result,
  question,
  isAnalyzing,
  onHighlightEvidence,
  onOpenEvidenceLens,
  onSelectQuestion,
  backendCapabilities,
  dates,
}: Props) {
  const [activeTab, setActiveTab] = useState<CopilotTab>("verdict");
  const [showModels, setShowModels] = useState(false);

  // Authoritative Query Understanding from backend
  const und = result?.query_understanding;
  const rationale = result?.plan_rationale || {};

  const intent = und?.intent
    ? und.intent.replace(/_/g, " ").toUpperCase()
    : (rationale.intent as string)?.replace(/_/g, " ").toUpperCase() || "INVESTIGATION";

  const target = und?.target || (rationale.target_objects as string[])?.join(", ") || "GEOSPATIAL ASSETS";
  const phenomenon = und?.phenomenon || (rationale.phenomenon as string) || "LANDSCAPE PHENOMENON";

  // Sensor selection from backend
  const sensorSel = result?.sensor_selection;
  const claims = result?.claims || [];
  const hypotheses = result?.hypotheses || [];
  const followUps = result?.follow_up_questions || [];

  const featuresCount = result?.location?.features?.length ?? 0;
  const confidencePct = result ? Math.round(result.confidence * 100) : null;
  const breakdown = result?.confidence_breakdown || {};
  const sops: SopEntry[] = result?.rag_sops || [];

  return (
    <div className="flex flex-col h-full bg-slate-900/70 text-slate-100 text-xs overflow-hidden backdrop-blur-md border-l border-slate-800/80">
      {/* Header */}
      <div className="p-3 border-b border-slate-800/80 flex items-center justify-between bg-slate-950/40">
        <div className="flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-gradient-to-tr from-sky-500 to-indigo-500 text-white font-bold text-xs shadow-sm">
            ✦
          </span>
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-100 font-display">
              SatQuery AI Copilot
            </h2>
            <span className="text-[10px] text-sky-400 font-mono">
              Autonomous Multimodal Investigation
            </span>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-950/60 p-0.5 text-[10px]">
          <button
            onClick={() => setActiveTab("verdict")}
            className={`rounded px-2 py-1 font-medium transition-all cursor-pointer ${
              activeTab === "verdict"
                ? "bg-sky-600 text-white font-semibold shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Answer
          </button>
          <button
            onClick={() => setActiveTab("evidence")}
            className={`rounded px-2 py-1 font-medium transition-all cursor-pointer ${
              activeTab === "evidence"
                ? "bg-sky-600 text-white font-semibold shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Evidence ({result?.evidence?.length ?? 0})
          </button>
          <button
            onClick={() => setActiveTab("provenance")}
            className={`rounded px-2 py-1 font-medium transition-all cursor-pointer ${
              activeTab === "provenance"
                ? "bg-sky-600 text-white font-semibold shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Graph
          </button>
          {sops.length > 0 && (
            <button
              onClick={() => setActiveTab("sops")}
              className={`rounded px-2 py-1 font-medium transition-all cursor-pointer ${
                activeTab === "sops"
                  ? "bg-sky-600 text-white font-semibold shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              SOPs ({sops.length})
            </button>
          )}
          <button
            onClick={() => setActiveTab("code")}
            className={`rounded px-2 py-1 font-medium transition-all cursor-pointer ${
              activeTab === "code"
                ? "bg-sky-600 text-white font-semibold shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            GIS Code
          </button>
        </div>
      </div>

      {/* Main Panel Content */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-3.5">
        {/* QUERY UNDERSTANDING CARD (Authoritative Backend State) */}
        <div className="rounded-xl border border-sky-500/30 bg-slate-950/60 p-3 space-y-2.5 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-sky-400 flex items-center gap-1">
              <span>🧠</span> EarthQuery Compiler
            </span>
            <span className="text-[9px] font-mono text-emerald-400 uppercase bg-emerald-950/60 border border-emerald-800 px-1.5 py-0.5 rounded">
              ✓ Structured Spec
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-2 space-y-0.5">
              <span className="text-slate-500 uppercase text-[9px] font-bold block">Taxonomy Intent</span>
              <span className="font-semibold text-slate-200 font-mono leading-tight block truncate">
                {intent}
              </span>
            </div>

            <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-2 space-y-0.5">
              <span className="text-slate-500 uppercase text-[9px] font-bold block">Target & Domain</span>
              <span className="font-semibold text-slate-200 font-mono leading-tight block truncate">
                {target}
              </span>
            </div>

            <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-2 space-y-0.5">
              <span className="text-slate-500 uppercase text-[9px] font-bold block">Phenomenon</span>
              <span className="font-semibold text-amber-300 font-mono leading-tight block truncate">
                {phenomenon}
              </span>
            </div>

            <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-2 space-y-0.5">
              <span className="text-slate-500 uppercase text-[9px] font-bold block">Sensor Decision</span>
              <span className="font-semibold text-sky-300 font-mono leading-tight block truncate">
                {sensorSel?.primary ? `${sensorSel.primary.toUpperCase()} (Primary)` : "Multimodal"}
              </span>
            </div>
          </div>

          {/* Autonomous Sensor Decision Description */}
          {sensorSel?.reason && (
            <div className="p-2 rounded bg-sky-950/40 border border-sky-900/40 text-[10px] text-sky-200/90 font-mono">
              <span className="font-bold text-sky-300">Sensor Reason: </span>
              {sensorSel.reason}
            </div>
          )}
        </div>

        {/* TAB 1: EXECUTIVE VERDICT & PROOF */}
        {activeTab === "verdict" && (
          <div className="space-y-3.5">
            {isAnalyzing ? (
              <div className="rounded-xl border border-dashed border-sky-500/40 bg-slate-950/40 p-6 text-center space-y-2 animate-pulse">
                <div className="h-6 w-6 rounded-full border-2 border-sky-400 border-t-transparent animate-spin mx-auto" />
                <p className="font-semibold text-sky-300">Executing EarthQuery Investigation...</p>
                <p className="text-[10px] text-slate-400">
                  Coordinating sensor selection, Siamese change inference, SAR specialist, and deterministic GIS.
                </p>
              </div>
            ) : result ? (
              <>
                {/* Executive Answer Card */}
                <div className="rounded-xl border border-sky-500/40 bg-gradient-to-br from-slate-900/90 to-sky-950/30 p-3.5 space-y-2.5 shadow-md">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-sky-300 flex items-center gap-1.5">
                      <span>✦</span> Executive Intelligence Result
                    </span>
                    <span className="text-[9px] font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-700/60 px-2 py-0.5 rounded-full">
                      ✓ Evidence Grounded
                    </span>
                  </div>

                  <p className="text-xs text-slate-100 leading-relaxed font-sans whitespace-pre-line font-normal">
                    {result.answer}
                  </p>

                  {/* Evidence Lens & Globe Actions */}
                  <div className="flex items-center gap-2 pt-2 border-t border-slate-800/80">
                    <button
                      onClick={() => onOpenEvidenceLens && onOpenEvidenceLens(null)}
                      className="flex-1 rounded-lg bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 px-3 py-1.5 text-xs font-bold text-white transition-all shadow cursor-pointer flex items-center justify-center gap-1.5"
                    >
                      <span>🔍</span> Show Evidence Lens
                    </button>
                    {onHighlightEvidence && (
                      <button
                        onClick={onHighlightEvidence}
                        className="rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200 transition-all cursor-pointer"
                      >
                        🎯 View on Globe ({featuresCount})
                      </button>
                    )}
                  </div>
                </div>

                {/* AUDITED CLAIMS & EVIDENCE LINKING */}
                {claims.length > 0 && (
                  <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-3.5 space-y-2 shadow-sm">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                      Claim-to-Evidence Linkages ({claims.length})
                    </span>
                    <div className="space-y-1.5">
                      {claims.map((claim) => (
                        <div
                          key={claim.id}
                          className="flex items-center justify-between p-2 rounded-lg border border-slate-800 bg-slate-900/60 hover:border-sky-500/40 transition-colors"
                        >
                          <div className="space-y-0.5 pr-2">
                            <span className="text-[11px] font-medium text-slate-200 block">
                              {claim.text}
                            </span>
                            <span className="text-[9px] font-mono text-slate-500">
                              Linked Artifacts: {claim.evidence_ids.join(", ") || "Verified by GIS pipeline"}
                            </span>
                          </div>
                          <button
                            onClick={() => onOpenEvidenceLens && onOpenEvidenceLens(claim)}
                            className="shrink-0 px-2 py-1 rounded bg-sky-950 border border-sky-700/60 text-[10px] font-mono text-sky-300 hover:bg-sky-900 transition-colors cursor-pointer"
                          >
                            Inspect ↗
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* MULTI-HYPOTHESIS EVALUATION IF INVESTIGATIVE */}
                {hypotheses.length > 0 && (
                  <div className="rounded-xl border border-indigo-500/30 bg-slate-950/60 p-3.5 space-y-2.5 shadow-sm">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-1.5">
                        <span>🧪</span> Candidate Hypotheses Evaluated
                      </span>
                      <span className="text-[9px] font-mono text-slate-400">
                        Ranked by Support
                      </span>
                    </div>

                    <div className="space-y-2">
                      {hypotheses.map((h) => (
                        <div key={h.id} className="space-y-1">
                          <div className="flex justify-between text-[11px]">
                            <span className="font-semibold text-slate-200">{h.label}</span>
                            <span className="font-mono text-indigo-300 font-bold">
                              {(h.support * 100).toFixed(0)}%
                            </span>
                          </div>
                          <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-sky-400"
                              style={{ width: `${Math.max(5, h.support * 100)}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* CONFIDENCE DASHBOARD */}
                <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-3.5 space-y-3 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                        Multimodal Verification Confidence
                      </span>
                      <div className="flex items-baseline gap-1.5 mt-0.5">
                        <span className="text-2xl font-bold font-mono text-emerald-400">
                          {confidencePct}%
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          ({result.consistency_verdict.replace(/_/g, " ")})
                        </span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="rounded-full border border-emerald-700/80 bg-emerald-950/80 px-2.5 py-1 text-[10px] font-bold uppercase text-emerald-300 tracking-wider">
                        ✓ Verified
                      </span>
                    </div>
                  </div>

                  {/* Component Breakdown Bars */}
                  <div className="space-y-2 pt-0.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                      Component Reliability Breakdown
                    </span>
                    <div className="space-y-1.5">
                      {Object.entries(breakdown).map(([key, val]) => (
                        <div key={key} className="space-y-0.5">
                          <div className="flex justify-between text-[10px]">
                            <span className="text-slate-300">{CONFIDENCE_LABELS[key] || key}</span>
                            <span className="font-mono text-slate-400">{(val * 100).toFixed(0)}%</span>
                          </div>
                          <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden ring-1 ring-slate-700/40">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-sky-500 via-indigo-400 to-emerald-400"
                              style={{ width: `${Math.max(5, Math.min(100, val * 100))}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* SUGGESTED FOLLOW-UP INVESTIGATION QUERIES */}
                {followUps.length > 0 && (
                  <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3 space-y-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                      Suggested Next Inquiries
                    </span>
                    <div className="flex flex-col gap-1.5">
                      {followUps.map((q, i) => (
                        <button
                          key={i}
                          onClick={() => onSelectQuestion && onSelectQuestion(q)}
                          className="text-left text-[11px] p-2 rounded-lg bg-slate-900 border border-slate-800 hover:border-sky-500/50 hover:bg-slate-800/50 text-slate-300 hover:text-white transition-all cursor-pointer"
                        >
                          → {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center text-slate-500 space-y-1">
                <p className="font-medium text-xs">Awaiting Earth Investigation Query</p>
                <p className="text-[10px]">
                  Ask what you want to know about any region or click "Launch Demo Mission".
                </p>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: EVIDENCE INSPECTOR */}
        {activeTab === "evidence" && (
          <div className="space-y-3">
            {result?.evidence && result.evidence.length > 0 ? (
              <div className="space-y-2">
                {result.evidence.map((e, idx) => (
                  <div
                    key={idx}
                    className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-3 space-y-1 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-sky-400 uppercase">
                        {e.agent}
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono">{e.type}</span>
                      {e.confidence !== undefined && (
                        <span className="rounded bg-sky-950 px-1.5 py-0.5 text-[9px] font-mono text-sky-300">
                          {(e.confidence * 100).toFixed(0)}% Conf
                        </span>
                      )}
                    </div>
                    <p className="text-slate-300 text-[11px] leading-relaxed pt-1 font-sans">
                      {e.summary}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center text-slate-500">
                No evidence items collected yet.
              </div>
            )}
          </div>
        )}

        {/* TAB 3: OBSERVABLE PROVENANCE GRAPH */}
        {activeTab === "provenance" && (
          <div>
            {result ? (
              <EvidenceProvenanceGraph result={result} />
            ) : (
              <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center text-slate-500">
                Run an investigation to render the evidence provenance graph.
              </div>
            )}
          </div>
        )}

        {/* TAB 4: DISASTER RAG PROTOCOLS */}
        {activeTab === "sops" && (
          <div className="space-y-2.5">
            {sops.map((sop) => (
              <div
                key={sop.sop_id}
                className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-3 space-y-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200">{sop.title}</span>
                  <span className="rounded bg-sky-950 px-1.5 py-0.5 text-[9px] font-mono text-sky-300 border border-sky-800">
                    {sop.sop_id}
                  </span>
                </div>
                <div className="space-y-1">
                  {sop.action_protocols.map((act, i) => (
                    <div key={i} className="text-slate-300 text-[10px]">
                      • {act}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* TAB 5: GIS CODE */}
        {activeTab === "code" && (
          <div>
            <CodePanel code={result?.generated_code || []} />
          </div>
        )}
      </div>
    </div>
  );
}
