/**
 * MissionControl — ROOT PAGE COMPONENT
 *
 * Three-state UI machine:
 *   IDLE      → Globe + Hero Query Composer (centered, full screen)
 *   ANALYZING → Globe + Left Analyzing overlay + Bottom pipeline bar
 *   RESULT    → Globe + Left AI Answer Panel + Bottom collapsed bar
 *
 * Layout: [DataDrawer | Globe : center-panel ] [AgentPipelineBar]
 * The center panel (column B) changes content per state.
 *
 * Rules:
 * - NO fake data.
 * - NO hardcoded confidence values.
 * - ALL values from real backend responses.
 */
import { useState, useCallback, useEffect } from "react";
import type { AppState, UploadedAsset, QueryResult, AgentStatus, TraceEvent } from "../services/types";
import * as api from "../services/api";

import { DataDrawer } from "../components/DataDrawer";
import { GlobeWorkspace } from "../components/GlobeWorkspace";
import { QueryComposer } from "../components/QueryComposer";
import { AnalysisOverlay } from "../components/AnalysisOverlay";
import { AIAnswerPanel } from "../components/AIAnswerPanel";
import { AgentPipelineBar } from "../components/AgentPipelineBar";

// ─────────────────────────────────────────────────────────────
// Demo mission preset — triggers a REAL backend query
// ─────────────────────────────────────────────────────────────
const DEMO_QUERY =
  "Identify flood-affected areas and generate a change detection map, then retrieve emergency response protocols.";

// Health indicator colours
const HEALTH_COLOR: Record<string, string> = {
  healthy: "text-emerald-400",
  degraded: "text-amber-400",
  unhealthy: "text-rose-400",
};

export default function MissionControl() {
  // ── UI State machine ──────────────────────────────────────
  const [appState, setAppState] = useState<AppState>("idle");

  // ── Query ─────────────────────────────────────────────────
  const [question, setQuestion] = useState("");

  // ── Assets / Data ─────────────────────────────────────────
  const [assets, setAssets] = useState<UploadedAsset[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // ── AOI ───────────────────────────────────────────────────
  const [aoi, setAoi] = useState<Record<string, any> | null>(null);
  const [drawMode, setDrawMode] = useState(false);

  // ── Job / Results ─────────────────────────────────────────
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);

  // ── Live pipeline ─────────────────────────────────────────
  const [liveAgents, setLiveAgents] = useState<AgentStatus[]>([]);
  const [liveProgress, setLiveProgress] = useState(0);

  // ── System health ─────────────────────────────────────────
  const [health, setHealth] = useState<string>("…");

  // Load persisted assets on mount
  useEffect(() => {
    api.listAssets().then((list) => {
      setAssets(list);
      setSelectedIds(list.map((a) => a.asset_id));
    }).catch(() => {/* no-op if backend not running */});

    // System health
    api.getHealth().then((h) => {
      setHealth(h.status ?? "healthy");
    }).catch(() => setHealth("degraded"));
  }, []);

  // ── Derived values ────────────────────────────────────────
  const selectedAssets = assets.filter((a) => selectedIds.includes(a.asset_id));

  const footprintBounds: number[] | null =
    selectedAssets.length > 0
      ? selectedAssets.reduce<number[]>((acc, a) => {
          const b = a.validation?.bounds_wgs84 ?? a.validation?.bounds;
          if (!b || b.length < 4) return acc;
          if (acc.length === 0) return [...b];
          return [
            Math.min(acc[0], b[0]),
            Math.min(acc[1], b[1]),
            Math.max(acc[2], b[2]),
            Math.max(acc[3], b[3]),
          ];
        }, [])
      : null;

  const layerDates = [...new Set(
    selectedAssets
      .map((a) => a.capture_date)
      .filter(Boolean) as string[]
  )].sort();

  const features = result?.location?.features ?? [];

  // ── Upload handler ────────────────────────────────────────
  const handleUpload = useCallback(async (file: File, sensor: "optical" | "sar", date: string) => {
    setUploading(true);
    setUploadError(null);
    try {
      const uploaded = await api.uploadRaster(file, sensor, date || null);
      setAssets((prev) => [...prev, uploaded]);
      setSelectedIds((prev) => [...prev, uploaded.asset_id]);
    } catch (err: any) {
      setUploadError(err.message ?? "Upload failed");
    } finally {
      setUploading(false);
    }
  }, []);

  // ── Analysis handler ──────────────────────────────────────
  const handleAnalyze = useCallback(async (overrideQuestion?: string) => {
    const q = overrideQuestion ?? question;
    if (!q.trim()) return;
    if (selectedAssets.length === 0 && !overrideQuestion) {
      // Allow demo to run with no real assets
      if (!overrideQuestion) return;
    }

    setAppState("analyzing");
    setResult(null);
    setJobError(null);
    setLiveAgents([]);
    setLiveProgress(0);
    setCurrentJobId(null);

    try {
      const jobId = await api.submitQuery({
        question: q,
        region: aoi ?? null,
        assets: selectedAssets.map((a) => ({
          asset_id: a.asset_id,
          capture_date: a.capture_date,
          sensor_type: a.sensor_type,
        })),
      });

      setCurrentJobId(jobId);

      // Poll for result
      const maxWait = 300_000; // 5 min
      const start = Date.now();
      let pollResult: QueryResult | null = null;

      while (Date.now() - start < maxWait) {
        try {
          const status = await api.getJobStatus(jobId);
          if (status.agents) setLiveAgents(status.agents);
          if (status.progress_pct !== undefined) setLiveProgress(status.progress_pct);

          if (status.status === "completed") {
            pollResult = await api.getResult(jobId);
            break;
          }
          if (status.status === "failed") {
            setJobError(status.error ?? "Analysis failed");
            setAppState("error");
            return;
          }
        } catch { /* ignore transient errors */ }
        await new Promise((r) => setTimeout(r, 1500));
      }

      if (!pollResult) {
        setJobError("Analysis timed out");
        setAppState("error");
        return;
      }

      setResult(pollResult);
      setAppState("result");
    } catch (err: any) {
      setJobError(err.message ?? "Unknown error");
      setAppState("error");
    }
  }, [question, selectedAssets, aoi]);

  // Demo mission — fires a real query
  const handleDemo = useCallback(() => {
    setQuestion(DEMO_QUERY);
    handleAnalyze(DEMO_QUERY);
  }, [handleAnalyze]);

  // Reset to idle
  const handleReset = useCallback(() => {
    setAppState("idle");
    setQuestion("");
    setResult(null);
    setJobError(null);
    setCurrentJobId(null);
    setLiveAgents([]);
    setLiveProgress(0);
  }, []);

  // Edit query → back to idle with question preserved
  const handleEditQuery = useCallback(() => {
    setAppState("idle");
    setResult(null);
  }, []);

  // Highlight evidence: fly to first feature bounds
  const handleHighlightEvidence = useCallback(() => {
    if (result?.location?.features?.[0]?.geometry?.coordinates) {
      const coords = result.location.features[0].geometry.coordinates as number[][][];
      if (coords[0]) {
        const lons = coords[0].map((c) => c[0]);
        const lats = coords[0].map((c) => c[1]);
        const bounds = [
          Math.min(...lons), Math.min(...lats),
          Math.max(...lons), Math.max(...lats),
        ];
        // GlobeWorkspace handles the actual fly-to when footprintBounds changes
        // We'll just show a toast — the globe already has the features
      }
    }
  }, [result]);

  // Completed trace from result
  const completedTrace: TraceEvent[] = result?.execution_trace ?? [];

  // ════════════════════════════════════════════════════════
  // RENDER
  // ════════════════════════════════════════════════════════
  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 overflow-hidden">

      {/* ── HEADER ──────────────────────────────────────────── */}
      <header className="shrink-0 flex items-center justify-between px-5 border-b border-slate-800/60 bg-slate-950/90 backdrop-blur-xl z-30" style={{ height: "52px" }}>
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 shadow-lg shadow-sky-500/30 text-sm font-black text-white">
            S
          </div>
          <div>
            <span className="text-sm font-bold text-slate-100 tracking-tight">SatQuery AI</span>
            <span className="ml-2 text-[10px] font-mono text-slate-500 hidden sm:inline">SIH26167</span>
          </div>
        </div>

        {/* Center: state indicator */}
        <div className="flex items-center gap-2">
          {appState === "idle" && (
            <span className="text-xs text-slate-500 hidden md:inline">
              Interactive Vision-Language Assistant
            </span>
          )}
          {appState === "analyzing" && (
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
              </span>
              <span className="text-xs text-amber-400 font-semibold font-mono">Autonomous Analysis</span>
            </div>
          )}
          {appState === "result" && (
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span className="text-xs text-emerald-400 font-semibold">Analysis Complete</span>
            </div>
          )}
          {appState === "error" && (
            <span className="text-xs text-rose-400 font-semibold">Analysis Failed</span>
          )}
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-2">
          {/* System health */}
          <span className={`text-[10px] font-mono hidden lg:inline ${HEALTH_COLOR[health] ?? "text-slate-400"}`}>
            ● {health}
          </span>

          {/* Demo Mission */}
          {(appState === "idle" || appState === "error") && (
            <button
              onClick={handleDemo}
              className="rounded-xl bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 px-4 py-1.5 text-xs font-bold text-white shadow-lg shadow-sky-600/30 transition-all active:scale-95"
            >
              ▶ Demo Mission
            </button>
          )}

          {/* New Query */}
          {(appState === "result" || appState === "error") && (
            <button
              onClick={handleReset}
              className="rounded-xl border border-slate-700/70 bg-slate-800/60 hover:bg-slate-700/60 px-3 py-1.5 text-xs font-medium text-slate-300 transition-all"
            >
              ↩ New Query
            </button>
          )}
        </div>
      </header>

      {/* ── MAIN LAYOUT ─────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── LEFT: Data Drawer ────────────────────── */}
        <DataDrawer
          assets={assets}
          selected={selectedIds}
          onSelectionChange={setSelectedIds}
          onUpload={handleUpload}
          uploading={uploading}
          uploadError={uploadError}
          aoi={aoi}
          drawMode={drawMode}
          onToggleDrawMode={() => setDrawMode((v) => !v)}
          onClearAoi={() => { setAoi(null); setDrawMode(false); }}
          dates={layerDates}
        />

        {/* ── CENTER: Globe + State-Driven Overlay ─── */}
        <div className="relative flex flex-col flex-1 overflow-hidden">

          {/* ── IDLE: Query composer floated over globe ── */}
          {appState === "idle" && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center pointer-events-none">
              <div className="pointer-events-auto w-full max-w-3xl px-4">
                <QueryComposer
                  question={question}
                  onChange={setQuestion}
                  onAnalyze={() => handleAnalyze()}
                  onEditQuery={handleEditQuery}
                  appState={appState}
                  sceneCount={selectedIds.length}
                />
              </div>
            </div>
          )}

          {/* ── ANALYZING / RESULT: Query pill at top, non-overlapping ── */}
          {(appState === "analyzing" || appState === "result") && (
            <div className="shrink-0 z-10 relative">
              <QueryComposer
                question={question}
                onChange={setQuestion}
                onAnalyze={() => handleAnalyze()}
                onEditQuery={handleEditQuery}
                appState={appState}
                sceneCount={selectedIds.length}
              />
            </div>
          )}

          {/* Globe — fills remaining height */}
          <div className="flex-1 relative overflow-hidden">
            <GlobeWorkspace
              features={features}
              footprintBounds={footprintBounds}
              drawMode={drawMode}
              onAoiDrawn={(geojson) => { setAoi(geojson); setDrawMode(false); }}
              layerDates={layerDates}
              showIdleOverlay={appState === "idle"}
            />
          </div>
        </div>

        {/* ── ANALYZING: Right side analysis panel ──── */}
        {appState === "analyzing" && (
          <div className="w-72 shrink-0 border-l border-slate-800/60 bg-slate-900/80 backdrop-blur-xl z-20 overflow-hidden animate-slide-right">
            <AnalysisOverlay
              jobId={currentJobId}
              question={question}
              onCompleted={() => {
                // The polling in handleAnalyze already handles transition
              }}
            />
          </div>
        )}

        {/* ── RESULT: Right side AI answer panel ────── */}
        {appState === "result" && result && (
          <div className="w-80 shrink-0 z-20 overflow-hidden animate-slide-right">
            <AIAnswerPanel
              result={result}
              onHighlightEvidence={handleHighlightEvidence}
            />
          </div>
        )}

        {/* ── ERROR: Inline error state ──────────────── */}
        {appState === "error" && (
          <div className="w-72 shrink-0 border-l border-slate-800/60 bg-slate-900/80 z-20 flex items-center justify-center p-6 animate-fade-in">
            <div className="text-center space-y-4">
              <div className="text-4xl">⚠️</div>
              <p className="text-sm font-semibold text-rose-400">Analysis Failed</p>
              <p className="text-xs text-slate-400 leading-relaxed">{jobError}</p>
              <button
                onClick={handleReset}
                className="w-full rounded-xl bg-slate-800 hover:bg-slate-700 py-2.5 text-sm font-medium text-slate-200 transition-colors"
              >
                Try Again
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── BOTTOM: Agent Pipeline Bar ───────────────── */}
      <AgentPipelineBar
        isAnalyzing={appState === "analyzing"}
        completedTrace={completedTrace}
        liveAgents={liveAgents}
        progress={liveProgress}
      />
    </div>
  );
}
