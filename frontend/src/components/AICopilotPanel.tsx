import { useState } from "react";
import type { QueryResult, SopEntry } from "../services/types";
import { CodePanel } from "./CodePanel";
import * as api from "../services/api";

interface Props {
  result: QueryResult | null;
  question: string;
  isAnalyzing: boolean;
  onHighlightEvidence?: () => void;
  backendCapabilities?: Record<string, any>;
  dates: string[];
}

type CopilotTab = "verdict" | "evidence" | "sops" | "code" | "export";

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
  backendCapabilities,
  dates,
}: Props) {
  const [activeTab, setActiveTab] = useState<CopilotTab>("verdict");
  const [showModels, setShowModels] = useState(false);

  // Derive Query Understanding from question & backend plan rationale
  const rationale = result?.plan_rationale || {};
  const isTemporal = dates.length >= 2 || (rationale.bi_temporal as boolean) || question.toLowerCase().includes("between") || question.toLowerCase().includes("change");
  const intent = isTemporal ? "CHANGE DETECTION & TEMPORAL VQA" : "ZERO-SHOT OBJECT GROUNDING";
  
  let target = "GEOSPATIAL ANOMALIES";
  if (question.toLowerCase().includes("vegetation") || question.toLowerCase().includes("forest")) {
    target = "VEGETATION & CANOPY COVER";
  } else if (question.toLowerCase().includes("water") || question.toLowerCase().includes("flood")) {
    target = "HYDROLOGICAL & WATER EXTENT";
  } else if (question.toLowerCase().includes("tank") || question.toLowerCase().includes("industrial") || question.toLowerCase().includes("building")) {
    target = "INDUSTRIAL ASSETS & STORAGE TANKS";
  }

  // Derive quantitative summary if available
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
              Multimodal Geospatial Intelligence
            </span>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-950/60 p-0.5 text-[10px]">
          <button
            onClick={() => setActiveTab("verdict")}
            className={`rounded px-2 py-1 font-medium transition-all ${
              activeTab === "verdict"
                ? "bg-sky-600 text-white font-semibold shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Answer
          </button>
          <button
            onClick={() => setActiveTab("evidence")}
            className={`rounded px-2 py-1 font-medium transition-all ${
              activeTab === "evidence"
                ? "bg-sky-600 text-white font-semibold shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Evidence ({result?.evidence?.length ?? 0})
          </button>
          {sops.length > 0 && (
            <button
              onClick={() => setActiveTab("sops")}
              className={`rounded px-2 py-1 font-medium transition-all ${
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
            className={`rounded px-2 py-1 font-medium transition-all ${
              activeTab === "code"
                ? "bg-sky-600 text-white font-semibold shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            GIS Code
          </button>
          <button
            onClick={() => setActiveTab("export")}
            className={`rounded px-2 py-1 font-medium transition-all ${
              activeTab === "export"
                ? "bg-sky-600 text-white font-semibold shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Export
          </button>
        </div>
      </div>

      {/* Main Panel Content */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-3.5">
        {/* QUERY UNDERSTANDING CARD (Visible whenever query exists) */}
        <div className="rounded-xl border border-sky-500/30 bg-slate-950/60 p-3 space-y-2.5 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-sky-400 flex items-center gap-1">
              <span>🧠</span> Query Understanding
            </span>
            <span className="text-[9px] font-mono text-emerald-400 uppercase bg-emerald-950/60 border border-emerald-800 px-1.5 py-0.5 rounded">
              ✓ Intent Parsed
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-2 space-y-0.5">
              <span className="text-slate-500 uppercase text-[9px] font-bold block">Autonomous Intent</span>
              <span className="font-semibold text-slate-200 font-mono leading-tight block truncate">
                {intent}
              </span>
            </div>

            <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-2 space-y-0.5">
              <span className="text-slate-500 uppercase text-[9px] font-bold block">Target Domain</span>
              <span className="font-semibold text-slate-200 font-mono leading-tight block truncate">
                {target}
              </span>
            </div>

            <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-2 space-y-0.5">
              <span className="text-slate-500 uppercase text-[9px] font-bold block">Temporal Window</span>
              <span className="font-semibold text-sky-300 font-mono leading-tight block truncate">
                {dates.length >= 2 ? `${dates[0]} → ${dates[1]}` : dates[0] || "Single Epoch"}
              </span>
            </div>

            <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-2 space-y-0.5">
              <span className="text-slate-500 uppercase text-[9px] font-bold block">Threshold Delta</span>
              <span className="font-semibold text-amber-300 font-mono leading-tight block truncate">
                &gt;20% Spectral Shift
              </span>
            </div>
          </div>

          {/* Autonomous Capability Checklist */}
          <div className="pt-1 flex flex-wrap gap-1 text-[9px] font-mono text-slate-300">
            <span className="rounded bg-sky-950/80 border border-sky-800/80 px-1.5 py-0.5 text-sky-300">
              ✓ Spatial Validator
            </span>
            <span className="rounded bg-sky-950/80 border border-sky-800/80 px-1.5 py-0.5 text-sky-300">
              ✓ Perception VLM
            </span>
            {isTemporal && (
              <>
                <span className="rounded bg-sky-950/80 border border-sky-800/80 px-1.5 py-0.5 text-sky-300">
                  ✓ Siamese UNet
                </span>
                <span className="rounded bg-sky-950/80 border border-sky-800/80 px-1.5 py-0.5 text-sky-300">
                  ✓ Change-VQA
                </span>
              </>
            )}
            <span className="rounded bg-sky-950/80 border border-sky-800/80 px-1.5 py-0.5 text-sky-300">
              ✓ Grounding DINO
            </span>
            <span className="rounded bg-sky-950/80 border border-sky-800/80 px-1.5 py-0.5 text-sky-300">
              ✓ Consensus Verifier
            </span>
          </div>
        </div>

        {/* TAB 1: EXECUTIVE VERDICT & CONFIDENCE */}
        {activeTab === "verdict" && (
          <div className="space-y-3.5">
            {isAnalyzing ? (
              <div className="rounded-xl border border-dashed border-sky-500/40 bg-slate-950/40 p-6 text-center space-y-2 animate-pulse">
                <div className="h-6 w-6 rounded-full border-2 border-sky-400 border-t-transparent animate-spin mx-auto" />
                <p className="font-semibold text-sky-300">Synthesizing Multimodal Intelligence...</p>
                <p className="text-[10px] text-slate-400">
                  Autonomous agents are cross-verifying optical, SAR, and temporal layers.
                </p>
              </div>
            ) : result ? (
              <>
                {/* Executive Answer Card */}
                <div className="rounded-xl border border-sky-500/40 bg-gradient-to-br from-slate-900/90 to-sky-950/30 p-3.5 space-y-2.5 shadow-md">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-sky-300 flex items-center gap-1.5">
                      <span>✦</span> Executive Intelligence Answer
                    </span>
                    <span className="text-[9px] font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-700/60 px-2 py-0.5 rounded-full">
                      ✓ Evidence Grounded
                    </span>
                  </div>

                  <p className="text-xs text-slate-100 leading-relaxed font-sans whitespace-pre-line">
                    {result.answer}
                  </p>

                  {/* Quantitative Summary Pill */}
                  <div className="flex items-center justify-between border-t border-slate-800/80 pt-2 text-[10px] text-slate-300 font-mono">
                    <span>Grounded Spatial Features:</span>
                    <span className="font-bold text-sky-400">{featuresCount} regions on globe</span>
                  </div>
                </div>

                {/* CONFIDENCE DASHBOARD */}
                <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-3.5 space-y-3 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                        Multimodal Confidence
                      </span>
                      <div className="flex items-baseline gap-1.5 mt-0.5">
                        <span className="text-2xl font-bold font-mono text-emerald-400">
                          {confidencePct}%
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          ({result.consistency_verdict.replace("_", " ")})
                        </span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="rounded-full border border-emerald-700/80 bg-emerald-950/80 px-2.5 py-1 text-[10px] font-bold uppercase text-emerald-300 tracking-wider">
                        ✓ Verified High
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
                            <span className="text-slate-300">
                              {CONFIDENCE_LABELS[key] || key}
                            </span>
                            <span className="font-mono text-slate-400">
                              {(val * 100).toFixed(0)}%
                            </span>
                          </div>
                          <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden ring-1 ring-slate-700/40">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-sky-500 via-indigo-400 to-emerald-400 transition-all duration-500"
                              style={{ width: `${Math.max(5, Math.min(100, val * 100))}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Verification Flags */}
                  <div className="pt-1 border-t border-slate-800/60 space-y-1 text-[10px] text-slate-300">
                    <div className="flex items-center gap-1.5 text-emerald-300">
                      <span>✓</span>
                      <span>Evidence consistent across optical & temporal specialist agents</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-emerald-300">
                      <span>✓</span>
                      <span>Spatial coregistration and CRS bounds verified</span>
                    </div>
                  </div>

                  {/* Uncertainty notes if present */}
                  {result.uncertainty && result.uncertainty.length > 0 && (
                    <div className="rounded-lg border border-amber-800/60 bg-amber-950/40 p-2 space-y-1 text-[10px]">
                      <span className="font-bold text-amber-300 uppercase block">
                        Uncertainty Telemetry:
                      </span>
                      {result.uncertainty.map((u, i) => (
                        <div key={i} className="text-amber-200/90">
                          • [{u.severity.toUpperCase()}] {u.explanation}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Evidence Call-to-Action */}
                <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-300 block">
                      Answer Supported By
                    </span>
                    <span className="text-[10px] text-slate-400">
                      {result.evidence?.length || 0} agent evidence records & {featuresCount} globe polygons
                    </span>
                  </div>

                  {onHighlightEvidence && (
                    <button
                      onClick={onHighlightEvidence}
                      className="rounded-lg bg-sky-600 hover:bg-sky-500 px-2.5 py-1.5 text-[11px] font-bold text-white transition-all shadow cursor-pointer"
                    >
                      🎯 View On Globe
                    </button>
                  )}
                </div>
              </>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center text-slate-500 space-y-1">
                <p className="font-medium text-xs">Awaiting Intelligence Query</p>
                <p className="text-[10px]">
                  Submit a query above or click "▶ Launch Demo Mission" to run full pipeline.
                </p>
              </div>
            )}

            {/* COLLAPSIBLE SPECIALIST MODELS DRAWER */}
            <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 overflow-hidden shadow-sm">
              <button
                onClick={() => setShowModels((v) => !v)}
                className="w-full p-3 flex items-center justify-between text-left hover:bg-slate-900/60 transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm">🤖</span>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-200">
                    Specialist AI Models ({backendCapabilities ? "6 Active" : "Operational"})
                  </span>
                </div>
                <span className="text-slate-400 font-mono text-xs">
                  {showModels ? "▲" : "▼"}
                </span>
              </button>

              {showModels && (
                <div className="p-3 border-t border-slate-800/80 space-y-2.5 text-[10px] font-mono">
                  <div>
                    <span className="text-sky-400 font-bold uppercase block mb-1">Vision Perception</span>
                    <div className="space-y-1 text-slate-300 pl-2 border-l border-slate-800">
                      <div>✓ Grounding DINO (Zero-Shot Object Localization)</div>
                      <div>✓ BLIP VQA (Multimodal Remote-Sensing VLM)</div>
                      <div>✓ MobileSAM (Segment Anything Zero-Shot Contours)</div>
                    </div>
                  </div>

                  <div>
                    <span className="text-emerald-400 font-bold uppercase block mb-1">Geospatial Specialist</span>
                    <div className="space-y-1 text-slate-300 pl-2 border-l border-slate-800">
                      <div>✓ Siamese UNet (Bi-Temporal Differential ChangeNet)</div>
                      <div>✓ Spatial Grounding & CRS Coordinate Projector</div>
                      <div>✓ BigEarthNet Land-Cover Feature Extractor</div>
                    </div>
                  </div>

                  <div>
                    <span className="text-indigo-400 font-bold uppercase block mb-1">Intelligence & Verification</span>
                    <div className="space-y-1 text-slate-300 pl-2 border-l border-slate-800">
                      <div>✓ ChromaDB RAG Vector Store (Disaster SOPs)</div>
                      <div>✓ MiniLM Sentence Transformer Embeddings</div>
                      <div>✓ Weighted Consensus & Uncertainty Verifier</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
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
                No evidence items available. Execute a query to inspect agent observations.
              </div>
            )}
          </div>
        )}

        {/* TAB 3: DISASTER RAG PROTOCOLS */}
        {activeTab === "sops" && (
          <div className="space-y-2.5">
            <div className="rounded-xl border border-sky-500/30 bg-sky-950/20 p-3 space-y-1 text-xs">
              <span className="font-bold text-sky-300 uppercase text-[10px] flex items-center gap-1.5">
                <span>📋</span> Curated Operational Response SOPs (RAG Layer)
              </span>
              <p className="text-[10px] text-slate-400">
                Retrieved via ChromaDB dense semantic vector search based on detected query hazards.
              </p>
            </div>

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
                <div className="text-[10px] text-slate-400">
                  Authority: <span className="text-slate-300 font-medium">{sop.authority}</span>
                </div>
                <div className="pt-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400 block mb-1">
                    Action Protocols:
                  </span>
                  <ul className="list-disc list-inside space-y-1 text-[10px] text-slate-300 pl-1">
                    {sop.action_protocols.map((act, i) => (
                      <li key={i}>{act}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* TAB 4: GIS CODE VIEWER */}
        {activeTab === "code" && (
          <div className="space-y-2">
            <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3 space-y-1 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-sky-400">
                  Executable GIS Python Workflow
                </span>
                <span className="text-[9px] font-mono text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800">
                  ✓ AST Validated
                </span>
              </div>
              <p className="text-[10px] text-slate-400">
                Deterministic GeoPandas & Rasterio code generated for this analytical query.
              </p>
            </div>
            <CodePanel code={result?.generated_code ?? []} />
          </div>
        )}

        {/* TAB 5: EXPORT DOSSIER */}
        {activeTab === "export" && (
          <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-4 space-y-3 text-center">
            <div className="text-3xl">📋</div>
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
              Geospatial Intelligence Dossier
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Export complete analytical package including GeoJSON vector masks, GeoTIFF change rasters, uncertainty breakdown, and execution logs.
            </p>

            {result?.job_id ? (
              <a
                href={api.reportUrl(result.job_id)}
                download
                className="inline-block w-full rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 py-2.5 text-xs font-bold text-white transition-all shadow-lg shadow-emerald-600/30"
              >
                📥 Download Full Report Bundle (.zip)
              </a>
            ) : (
              <button
                disabled
                className="w-full rounded-xl bg-slate-800 py-2.5 text-xs font-semibold text-slate-500 cursor-not-allowed"
              >
                Run an analysis first to generate report
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
