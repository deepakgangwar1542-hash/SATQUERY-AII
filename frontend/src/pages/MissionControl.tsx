import { useCallback, useMemo, useState } from "react";
import { QueryBar } from "../components/QueryBar";
import { CesiumGlobe } from "../components/CesiumGlobe";
import { AgentStatusPanel } from "../components/AgentStatusPanel";
import { ConfidencePanel } from "../components/ConfidencePanel";
import { EvidencePanel } from "../components/EvidencePanel";
import { CodePanel } from "../components/CodePanel";
import { TimelineControl } from "../components/TimelineControl";
import * as api from "../services/api";
import type { JobStatus, QueryResult, UploadedAsset } from "../services/types";

type Tab = "evidence" | "changemap" | "code" | "timeline" | "export";

const TABS: { id: Tab; label: string }[] = [
  { id: "evidence", label: "Evidence" },
  { id: "changemap", label: "Change Map" },
  { id: "code", label: "Generated Code" },
  { id: "timeline", label: "Timeline" },
  { id: "export", label: "Export" },
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
  const [tab, setTab] = useState<Tab>("evidence");
  const [activeDate, setActiveDate] = useState<string | null>(null);

  const loadAssets = useCallback(async () => {
    try { setAssets(await api.listAssets()); } catch { /* server offline */ }
  }, []);
  useMemo(() => void loadAssets(), [loadAssets]);

  const onUpload = async (file: File, sensor: "optical" | "sar", date: string) => {
    setUploading(true); setUploadError(null);
    try {
      const a = await api.uploadRaster(file, sensor, date || null);
      setAssets((prev) => [...prev, a]);
      setSelected((prev) => [...prev, a.asset_id]);
    } catch (e: any) {
      setUploadError(e.message ?? "upload failed");
    } finally {
      setUploading(false);
    }
  };

  const selectedAssets = assets.filter((a) => selected.includes(a.asset_id));
  const dates = useMemo(
    () => [...new Set(selectedAssets.map((a) => a.capture_date).filter(Boolean))] as string[],
    [selectedAssets],
  );

  const ask = async () => {
    setJobError(null); setResult(null); setJobId(null);
    if (selectedAssets.length === 0) {
      setJobError("select or upload at least one asset first");
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
      setJobError(e.message ?? "query failed");
    }
  };

  const fetchResult = useCallback(async () => {
    if (!jobId) return;
    try { setResult(await api.getResult(jobId)); } catch { /* not ready yet */ }
  }, [jobId]);

  const footprintBounds = useMemo(() => {
    const b = selectedAssets.find((a) => a.validation?.bounds_wgs84)?.validation?.bounds_wgs84;
    return b && b.length === 4 ? b : null;
  }, [selectedAssets]);

  const features = result?.location?.features ?? [];

  return (
    <div className="flex h-full flex-col bg-slate-950 text-slate-200">
      {/* header + query bar (§15.1) */}
      <header className="border-b border-slate-800 px-4 py-2">
        <div className="mb-2 flex items-center justify-between">
          <h1 className="text-sm font-bold tracking-widest text-sky-400">
            SATQUERY&nbsp;AI
            <span className="ml-2 text-[10px] font-normal tracking-normal text-slate-500">
              autonomous geospatial intelligence
            </span>
          </h1>
          {aoi && (
            <span className="rounded bg-emerald-900/50 px-2 py-0.5 text-[10px] text-emerald-300">
              AOI polygon attached ({aoi.coordinates?.[0]?.length ?? 0} vertices)
            </span>
          )}
        </div>
        <QueryBar assets={assets} selected={selected} onSelectionChange={setSelected}
          onUpload={onUpload} uploading={uploading} uploadError={uploadError} />
        <div className="mt-2 flex items-center gap-2">
          <input
            value={question} onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
            placeholder="Ask a geospatial question…"
            className="flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm outline-none focus:border-sky-500"
          />
          <button onClick={() => setDrawMode((d) => !d)}
            className={`rounded px-2.5 py-1.5 text-xs ${
              drawMode ? "bg-emerald-700 hover:bg-emerald-600" : "bg-slate-800 hover:bg-slate-700"}`}>
            {drawMode ? "drawing AOI…" : "Draw AOI"}
          </button>
          <button onClick={ask} disabled={!jobId && selected.length === 0}
            className="rounded bg-sky-600 px-4 py-1.5 text-sm font-medium hover:bg-sky-500 disabled:opacity-40">
            Analyze
          </button>
        </div>
        {jobError && <p className="mt-1 text-xs text-red-400">{jobError}</p>}
      </header>

      {/* globe + right rail */}
      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 border-r border-slate-800">
          <CesiumGlobe features={features} footprintBounds={footprintBounds}
            drawMode={drawMode} onAoiDrawn={(g) => { setAoi(g); setDrawMode(false); }}
            activeLayerKey={activeDate} layerDates={dates} />
        </div>
        <aside className="w-72 shrink-0 space-y-4 overflow-y-auto p-3">
          <AgentStatusPanel jobId={jobId} onStatus={() => {}} onCompleted={fetchResult} />
          {result && (
            <ConfidencePanel confidence={result.confidence}
              breakdown={result.confidence_breakdown}
              verdict={result.consistency_verdict} />
          )}
          {result && (
            <div className="rounded border border-slate-800 bg-slate-900/60 p-2 text-xs text-slate-300">
              {result.answer}
            </div>
          )}
        </aside>
      </div>

      {/* bottom tabs */}
      <footer className="border-t border-slate-800">
        <nav className="flex gap-1 px-3 pt-1.5">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`rounded-t px-3 py-1 text-xs ${
                tab === t.id ? "bg-slate-900 text-sky-300" : "text-slate-500 hover:text-slate-300"}`}>
              {t.label}
            </button>
          ))}
        </nav>
        <div className="max-h-64 overflow-y-auto bg-slate-900/60 p-3">
          {tab === "evidence" && (
            <EvidencePanel evidence={result?.evidence ?? []}
              uncertainty={result?.uncertainty ?? []}
              trace={result?.execution_trace ?? []} />
          )}
          {tab === "changemap" && (
            <div className="text-xs text-slate-300">
              {result?.artifacts?.length ? (
                <ul className="space-y-1">
                  {result.artifacts.map((a) => (
                    <li key={a.url}>
                      <a className="text-sky-400 hover:underline" href={a.url}>{a.name}</a>
                      <span className="ml-2 text-slate-500">{a.type}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-600">no change artifacts for this query</p>
              )}
              <p className="mt-2 text-slate-500">
                Polygons are rendered live on the globe ({features.length} features).
              </p>
            </div>
          )}
          {tab === "code" && <CodePanel code={result?.generated_code ?? []} />}
          {tab === "timeline" && (
            <TimelineControl dates={dates} onDateChange={setActiveDate} />
          )}
          {tab === "export" && (
            jobId ? (
              <a href={api.reportUrl(jobId)}
                className="rounded bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-600">
                Download report bundle (PDF + GeoJSON + CSV + code + trace)
              </a>
            ) : (
              <p className="text-xs text-slate-600">run a query first</p>
            )
          )}
        </div>
      </footer>
    </div>
  );
}
