import { useCallback, useEffect, useMemo, useState } from "react";
import { QueryBar } from "../components/QueryBar";
import { CesiumGlobe } from "../components/CesiumGlobe";
import { AgentStatusPanel } from "../components/AgentStatusPanel";
import { ConfidencePanel } from "../components/ConfidencePanel";
import { EvidencePanel } from "../components/EvidencePanel";
import { CodePanel } from "../components/CodePanel";
import { TimelineControl } from "../components/TimelineControl";
import * as api from "../services/api";
import type { QueryResult, UploadedAsset } from "../services/types";

type RightTab = "pipeline" | "evidence" | "changemap" | "code" | "export";

const SCENARIOS = [
  {
    id: "vegetation_loss",
    name: "🌲 Vegetation Loss",
    label: "Bi-Temporal Deforestation (June vs Sept)",
    sensor: "optical",
    dates: ["2025-06-01", "2025-09-01"],
    question: "Show areas where vegetation decreased by more than 20% between June and September.",
  },
  {
    id: "water_inundation",
    name: "🌊 Flood & Water Shift",
    label: "Hydrological Change Analysis",
    sensor: "optical",
    dates: ["2025-06-01", "2025-09-01"],
    question: "Identify surface water extent changes and flooded zones between June and September.",
  },
  {
    id: "object_grounding",
    name: "🎯 Object Grounding",
    label: "Grounding DINO Zero-Shot Detection",
    sensor: "optical",
    dates: ["2025-06-01"],
    question: "Detect and localize industrial structures, storage tanks, and transportation features.",
  },
];

const PROMPT_SUGGESTIONS = [
  { label: "🌿 Vegetation Loss >20%", text: "Show areas where vegetation decreased by more than 20% between June and September." },
  { label: "💧 Water Body Shifts", text: "Identify surface water extent changes and flooded zones between June and September." },
  { label: "🏗️ Storage Tanks & Facilities", text: "Detect and localize industrial structures, storage tanks, and transportation features." },
];

export function MissionControl() {
  const [assets, setAssets] = useState<UploadedAsset[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [question, setQuestion] = useState(
    "Show areas where vegetation decreased by more than 20% between June and September.",
  );
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [aoi, setAoi] = useState<Record<string, any> | null>(null);
  const [drawMode, setDrawMode] = useState(false);
  const [tab, setTab] = useState<RightTab>("pipeline");
  const [activeDate, setActiveDate] = useState<string | null>(null);
  const [backendHealth, setBackendHealth] = useState<{
    online: boolean;
    gpu?: boolean;
    models?: string[];
  }>({ online: false });

  // Poll backend health & model status
  const checkHealth = useCallback(async () => {
    try {
      const h = await api.getHealth();
      setBackendHealth({
        online: true,
        gpu: h.gpu_available,
        models: ["Grounding DINO", "BLIP VQA", "Siamese UNet", "MiniLM", "BigEarthNet"],
      });
    } catch {
      setBackendHealth({ online: false });
    }
  }, []);

  const loadAssets = useCallback(async () => {
    try {
      const list = await api.listAssets();
      setAssets(list);
      // Auto-select first two if none currently selected
      if (list.length > 0 && selected.length === 0) {
        setSelected(list.slice(0, 2).map((a) => a.asset_id));
      }
    } catch {
      /* backend offline */
    }
  }, [selected.length]);

  useEffect(() => {
    void checkHealth();
    void loadAssets();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, [checkHealth, loadAssets]);

  const onUpload = async (file: File, sensor: "optical" | "sar", date: string) => {
    setUploading(true);
    setUploadError(null);
    try {
      const a = await api.uploadRaster(file, sensor, date || null);
      setAssets((prev) => [...prev, a]);
      setSelected((prev) => [...prev, a.asset_id]);
    } catch (e: any) {
      setUploadError(e.message ?? "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const selectedAssets = useMemo(
    () => assets.filter((a) => selected.includes(a.asset_id)),
    [assets, selected],
  );

  const dates = useMemo(
    () => [...new Set(selectedAssets.map((a) => a.capture_date).filter(Boolean))] as string[],
    [selectedAssets],
  );

  // Quick-load scenario preset handler
  const loadScenario = (scenarioId: string) => {
    const s = SCENARIOS.find((item) => item.id === scenarioId);
    if (!s) return;
    setQuestion(s.question);
    setJobError(null);
    setResult(null);
    setJobId(null);

    // Pick assets matching the scenario's dates or sensors
    const matched = assets.filter((a) =>
      s.dates.includes(a.capture_date ?? "") || (s.dates.length === 1 && a.capture_date === s.dates[0]),
    );
    if (matched.length > 0) {
      setSelected(matched.map((m) => m.asset_id));
    } else if (assets.length >= 2) {
      setSelected(assets.slice(0, s.dates.length).map((a) => a.asset_id));
    }
  };

  const ask = async () => {
    setJobError(null);
    setResult(null);
    setJobId(null);
    setTab("pipeline");

    if (selectedAssets.length === 0) {
      setJobError("Please select or upload at least one satellite scene first.");
      return;
    }
    try {
      const id = await api.submitQuery({
        question,
        region: aoi,
        assets: selectedAssets.map((a) => ({
          asset_id: a.asset_id,
          capture_date: a.capture_date,
          sensor_type: a.sensor_type,
        })),
      });
      setJobId(id);
    } catch (e: any) {
      setJobError(e.message ?? "Query execution failed");
    }
  };

  const fetchResult = useCallback(async () => {
    if (!jobId) return;
    try {
      const res = await api.getResult(jobId);
      setResult(res);
      // Auto switch tab to evidence once finished
      setTab("evidence");
    } catch {
      /* not ready yet */
    }
  }, [jobId]);

  const footprintBounds = useMemo(() => {
    const b = selectedAssets.find((a) => a.validation?.bounds_wgs84)?.validation?.bounds_wgs84;
    return b && b.length === 4 ? b : null;
  }, [selectedAssets]);

  const features = result?.location?.features ?? [];

  return (
    <div className="flex h-screen w-screen flex-col bg-slate-950 text-slate-100 font-sans overflow-hidden select-none">
      {/* 1. TOP COMMAND BAR */}
      <header className="h-14 shrink-0 border-b border-slate-800/80 bg-slate-900/90 px-4 flex items-center justify-between backdrop-blur-md z-30">
        {/* Left: Brand & Telemetry */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="relative flex h-3.5 w-3.5 items-center justify-center">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-sky-500" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold tracking-widest text-sky-400 font-display">
                SATQUERY<span className="text-slate-100">&nbsp;AI</span>
              </span>
              <span className="text-[9px] uppercase tracking-wider text-slate-400 -mt-0.5">
                Mission Control · Multimodal Geospatial Intelligence
              </span>
            </div>
          </div>

          <div className="hidden lg:flex items-center gap-2 pl-4 border-l border-slate-800">
            {/* Backend Health Badge */}
            <div className="flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-950/80 px-2.5 py-1 text-[11px]">
              <span className={`h-2 w-2 rounded-full ${backendHealth.online ? "bg-emerald-400" : "bg-rose-500 animate-pulse"}`} />
              <span className="text-slate-300 font-medium">
                {backendHealth.online ? "Backend Online (8000)" : "Backend Offline"}
              </span>
            </div>

            {/* Real Models Indicator */}
            <div className="flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-950/80 px-2.5 py-1 text-[11px] text-slate-400">
              <span className="text-emerald-400">●</span>
              <span>5 Vision Models Active</span>
              <span className="text-[10px] text-slate-400 font-mono">(DINO · BLIP · UNet)</span>
            </div>
          </div>
        </div>

        {/* Right: Quick Scenario Presets */}
        <div className="flex items-center gap-2">
          <span className="hidden md:inline text-[11px] font-medium text-slate-400">
            ⚡ Quick Scenarios:
          </span>
          <div className="flex items-center gap-1.5">
            {SCENARIOS.map((s) => (
              <button
                key={s.id}
                onClick={() => loadScenario(s.id)}
                title={s.label}
                className="rounded-lg border border-slate-700/60 bg-slate-800/80 hover:bg-sky-600 hover:border-sky-500 px-2.5 py-1 text-xs font-medium text-slate-200 hover:text-white transition-all shadow-sm"
              >
                {s.name}
              </button>
            ))}
          </div>

          {aoi && (
            <button
              onClick={() => setAoi(null)}
              className="ml-2 flex items-center gap-1 rounded-full border border-emerald-700/80 bg-emerald-950/80 px-2.5 py-1 text-[10px] font-mono text-emerald-300 hover:bg-emerald-900"
            >
              <span>✓ Custom AOI Attached</span>
              <span className="text-emerald-400 hover:text-emerald-100">✕</span>
            </button>
          )}
        </div>
      </header>

      {/* 2. MAIN 3-COLUMN WORKSPACE */}
      <div className="flex flex-1 min-h-0 relative">
        {/* LEFT COLUMN: MISSION STUDIO (380px) */}
        <aside className="w-[380px] shrink-0 border-r border-slate-800/80 bg-slate-900/60 flex flex-col backdrop-blur-md z-20 overflow-hidden">
          <div className="p-3.5 border-b border-slate-800/80 flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-sky-400 font-display flex items-center gap-1.5">
              <span>🛰️</span> Mission Studio
            </h2>
            <span className="text-[10px] text-slate-400 font-medium">
              Guided 3-Step Workflow
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-3.5 space-y-4">
            {/* STEP 1: SCENES & IMAGERY */}
            <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3 space-y-2.5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-sky-500/20 text-sky-400 text-[10px]">
                    1
                  </span>
                  Satellite Scenes
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  {selected.length} active
                </span>
              </div>

              <QueryBar
                assets={assets}
                selected={selected}
                onSelectionChange={setSelected}
                onUpload={onUpload}
                uploading={uploading}
                uploadError={uploadError}
              />
            </div>

            {/* STEP 2: QUERY OBJECTIVE */}
            <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3 space-y-2.5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-sky-500/20 text-sky-400 text-[10px]">
                    2
                  </span>
                  Intelligence Query
                </span>
              </div>

              {/* Quick suggestion prompt chips */}
              <div className="flex flex-wrap gap-1">
                {PROMPT_SUGGESTIONS.map((p, idx) => (
                  <button
                    key={idx}
                    onClick={() => setQuestion(p.text)}
                    className="rounded border border-slate-800 bg-slate-900 px-2 py-0.5 text-[10px] text-slate-300 hover:border-sky-500 hover:text-sky-300 transition-colors"
                  >
                    {p.label}
                  </button>
                ))}
              </div>

              <textarea
                rows={3}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    ask();
                  }
                }}
                placeholder="Ask any geospatial question (e.g., 'Detect areas where vegetation decreased >20%')..."
                className="w-full resize-none rounded-lg border border-slate-800 bg-slate-900/90 p-2.5 text-xs text-slate-200 outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/50 transition-all font-sans leading-relaxed"
              />
            </div>

            {/* STEP 3: AREA OF INTEREST (AOI) */}
            <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3 space-y-2.5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-sky-500/20 text-sky-400 text-[10px]">
                    3
                  </span>
                  Geographic AOI
                </span>
                <span className="text-[10px] text-slate-400">
                  {aoi ? "Custom Polygon" : "Scene Extents"}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setDrawMode(false);
                    setAoi(null);
                  }}
                  className={`rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all ${
                    !aoi && !drawMode
                      ? "border-sky-500 bg-sky-950/50 text-sky-300"
                      : "border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  Entire Scene Bounds
                </button>

                <button
                  type="button"
                  onClick={() => setDrawMode((d) => !d)}
                  className={`rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all ${
                    drawMode
                      ? "border-amber-500 bg-amber-950/60 text-amber-300 animate-pulse"
                      : aoi
                      ? "border-emerald-500 bg-emerald-950/50 text-emerald-300"
                      : "border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  {drawMode ? "Drawing Active..." : aoi ? "Redraw Polygon" : "Draw Custom AOI"}
                </button>
              </div>

              {drawMode && (
                <p className="text-[11px] text-amber-400/90 leading-tight">
                  Click vertices on the 3D globe. Double-click to close and seal polygon.
                </p>
              )}
            </div>

            {/* PRIMARY ACTION BUTTON */}
            <div className="pt-2">
              <button
                onClick={ask}
                disabled={selected.length === 0}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 py-3 text-sm font-bold text-white transition-all shadow-lg shadow-sky-500/25 active:scale-[0.99] disabled:opacity-40 cursor-pointer"
              >
                <span>🚀 Run Autonomous Analysis</span>
              </button>

              {selected.length === 0 && (
                <p className="text-center text-[10px] text-amber-400/80 mt-1.5">
                  Select at least 1 satellite scene above to run intelligence pipeline.
                </p>
              )}

              {jobError && (
                <div className="mt-2 rounded-lg border border-rose-800/60 bg-rose-950/60 p-2.5 text-xs text-rose-300">
                  {jobError}
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* CENTER COLUMN: 3D GEOSPATIAL THEATER */}
        <main className="flex-1 min-w-0 relative flex flex-col bg-slate-950">
          <div className="flex-1 relative w-full h-full min-h-0">
            <CesiumGlobe
              features={features}
              footprintBounds={footprintBounds}
              drawMode={drawMode}
              onAoiDrawn={(g) => {
                setAoi(g);
                setDrawMode(false);
              }}
              activeLayerKey={activeDate}
              layerDates={dates}
            />
          </div>

          {/* Floating Bottom Temporal Scrubber (when 2+ dates exist) */}
          {dates.length >= 2 && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 w-[420px] max-w-[90%] pointer-events-auto rounded-xl border border-slate-700/60 bg-slate-900/90 p-2.5 backdrop-blur-md shadow-2xl">
              <TimelineControl dates={dates} onDateChange={setActiveDate} />
            </div>
          )}
        </main>

        {/* RIGHT COLUMN: INTELLIGENCE & EVIDENCE RAIL (400px) */}
        <aside className="w-[400px] shrink-0 border-l border-slate-800/80 bg-slate-900/70 flex flex-col backdrop-blur-md z-20 overflow-hidden">
          {/* Tabs Navigation */}
          <div className="flex border-b border-slate-800/80 px-2 pt-2 bg-slate-950/40">
            <button
              onClick={() => setTab("pipeline")}
              className={`flex-1 border-b-2 py-2 text-xs font-semibold transition-all ${
                tab === "pipeline"
                  ? "border-sky-500 text-sky-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              Agents
            </button>
            <button
              onClick={() => setTab("evidence")}
              className={`flex-1 border-b-2 py-2 text-xs font-semibold transition-all ${
                tab === "evidence"
                  ? "border-sky-500 text-sky-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              Evidence
            </button>
            <button
              onClick={() => setTab("changemap")}
              className={`flex-1 border-b-2 py-2 text-xs font-semibold transition-all ${
                tab === "changemap"
                  ? "border-sky-500 text-sky-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              Artifacts
            </button>
            <button
              onClick={() => setTab("code")}
              className={`flex-1 border-b-2 py-2 text-xs font-semibold transition-all ${
                tab === "code"
                  ? "border-sky-500 text-sky-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              GIS Code
            </button>
            <button
              onClick={() => setTab("export")}
              className={`flex-1 border-b-2 py-2 text-xs font-semibold transition-all ${
                tab === "export"
                  ? "border-sky-500 text-sky-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              Export
            </button>
          </div>

          {/* Tab Contents */}
          <div className="flex-1 overflow-y-auto p-3.5 space-y-3.5">
            {/* Executive Synthesis Card (Always visible when result is ready) */}
            {result && (
              <div className="space-y-3">
                <ConfidencePanel
                  confidence={result.confidence}
                  breakdown={result.confidence_breakdown}
                  verdict={result.consistency_verdict}
                />

                <div className="rounded-xl border border-sky-500/30 bg-sky-950/30 p-3.5 space-y-1.5 shadow-sm">
                  <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-sky-400">
                    <span>🧠</span> Executive Intelligence Verdict
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed font-sans">
                    {result.answer}
                  </p>
                </div>
              </div>
            )}

            {/* TAB 1: Live Agent Pipeline */}
            {tab === "pipeline" && (
              <AgentStatusPanel
                jobId={jobId}
                onStatus={() => {}}
                onCompleted={fetchResult}
              />
            )}

            {/* TAB 2: Structured Evidence & Metrics */}
            {tab === "evidence" && (
              <div className="space-y-3">
                {result ? (
                  <EvidencePanel
                    evidence={result.evidence ?? []}
                    uncertainty={result.uncertainty ?? []}
                    trace={result.execution_trace ?? []}
                  />
                ) : (
                  <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500">
                    No intelligence evidence collected yet. Execute a query to view agent reasoning.
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: Change Map & Detection Artifacts */}
            {tab === "changemap" && (
              <div className="space-y-3">
                <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3.5 space-y-2">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                    <span className="text-xs font-semibold text-slate-200">
                      Generated Artifacts
                    </span>
                    <span className="text-[10px] font-mono text-sky-400">
                      {result?.artifacts?.length ?? 0} files
                    </span>
                  </div>

                  {result?.artifacts?.length ? (
                    <ul className="space-y-1.5">
                      {result.artifacts.map((a) => (
                        <li
                          key={a.url}
                          className="flex items-center justify-between rounded-lg border border-slate-800/60 bg-slate-900/60 p-2 text-xs"
                        >
                          <a
                            className="text-sky-400 hover:text-sky-300 font-medium hover:underline truncate"
                            href={a.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {a.name}
                          </a>
                          <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                            {a.type}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-slate-500 py-2">
                      No change artifacts generated for this query yet.
                    </p>
                  )}

                  <div className="border-t border-slate-800 pt-2 text-[11px] text-slate-400 flex items-center justify-between">
                    <span>Active Features on Globe:</span>
                    <span className="font-mono text-white font-semibold">{features.length}</span>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 4: GIS Python Code */}
            {tab === "code" && (
              <div className="space-y-2">
                <CodePanel code={result?.generated_code ?? []} />
              </div>
            )}

            {/* TAB 5: Export Dossier */}
            {tab === "export" && (
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-4 space-y-3 text-center">
                <div className="text-2xl">📋</div>
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Geospatial Intelligence Dossier
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Export complete analytical package including GeoJSON vector masks, GeoTIFF change raster, uncertainty breakdown, and execution logs.
                </p>

                {jobId ? (
                  <a
                    href={api.reportUrl(jobId)}
                    download
                    className="inline-block w-full rounded-lg bg-emerald-600 hover:bg-emerald-500 py-2 text-xs font-bold text-white transition-all shadow-md shadow-emerald-600/30"
                  >
                    📥 Download Report Bundle (.zip)
                  </a>
                ) : (
                  <button
                    disabled
                    className="w-full rounded-lg bg-slate-800 py-2 text-xs font-semibold text-slate-500 cursor-not-allowed"
                  >
                    Run an analysis first to generate report
                  </button>
                )}
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
