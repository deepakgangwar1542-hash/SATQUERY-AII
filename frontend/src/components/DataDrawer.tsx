/**
 * DataDrawer — Collapsible left panel
 *
 * Default state: collapsed ~52px tab showing scene count + expand arrow
 * Expanded: shows Sentinel scene cards, temporal context, sensor info
 * Advanced: EPSG, pixel dimensions, filenames behind [ Advanced ]
 *
 * Progressive disclosure: user doesn't NEED technical metadata to understand
 * the product.
 */
import { useState } from "react";
import type { UploadedAsset } from "../services/types";

interface Props {
  assets: UploadedAsset[];
  selected: string[];
  onSelectionChange: (ids: string[]) => void;
  onUpload: (file: File, sensor: "optical" | "sar", date: string) => void;
  uploading: boolean;
  uploadError: string | null;
  aoi: Record<string, any> | null;
  drawMode: boolean;
  onToggleDrawMode: () => void;
  onClearAoi: () => void;
  dates: string[];   // sorted dates from selected assets
}

function SceneLabel(asset: UploadedAsset): string {
  const type = asset.sensor_type === "sar" ? "Sentinel-1 SAR" : "Sentinel-2";
  const date = asset.capture_date
    ? new Date(asset.capture_date).toLocaleDateString("en-GB", { month: "short", year: "numeric" })
    : "Unknown date";
  return `${type} · ${date}`;
}

export function DataDrawer({
  assets,
  selected,
  onSelectionChange,
  onUpload,
  uploading,
  uploadError,
  aoi,
  drawMode,
  onToggleDrawMode,
  onClearAoi,
  dates,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Upload form state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadSensor, setUploadSensor] = useState<"optical" | "sar">("optical");
  const [uploadDate, setUploadDate] = useState("");

  const handleUpload = () => {
    if (uploadFile) {
      onUpload(uploadFile, uploadSensor, uploadDate);
      setShowUpload(false);
      setUploadFile(null);
    }
  };

  const toggleSelect = (id: string) => {
    onSelectionChange(
      selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id],
    );
  };

  const selectedAssets = assets.filter((a) => selected.includes(a.asset_id));
  const opticalCount = selectedAssets.filter((a) => a.sensor_type === "optical").length;
  const sarCount = selectedAssets.filter((a) => a.sensor_type === "sar").length;
  const isTemporal = dates.length >= 2;

  // ── COLLAPSED ──────────────────────────────────────────────────────────
  if (!expanded) {
    return (
      <div className="w-14 shrink-0 border-r border-slate-800/60 bg-slate-900/60 flex flex-col items-center py-4 gap-3 backdrop-blur-md z-20">
        {/* Expand button */}
        <button
          onClick={() => setExpanded(true)}
          title="Open Data Context"
          className="flex flex-col items-center gap-1.5 text-slate-400 hover:text-sky-400 transition-colors group"
        >
          <span className="text-lg">🛰️</span>
          <span className="text-[9px] font-mono font-semibold text-slate-500 group-hover:text-sky-400">
            {selected.length}
          </span>
          <span className="text-[9px] text-slate-600 group-hover:text-slate-400">DATA</span>
          <span className="text-xs text-slate-600 group-hover:text-sky-400 mt-1">›</span>
        </button>

        {/* AOI badge */}
        {aoi && (
          <div title="Custom AOI active" className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        )}
      </div>
    );
  }

  // ── EXPANDED ────────────────────────────────────────────────────────────
  return (
    <div className="w-[280px] shrink-0 border-r border-slate-800/60 bg-slate-900/70 flex flex-col backdrop-blur-md z-20 overflow-hidden animate-slide-up">
      {/* Panel Header */}
      <div className="flex items-center justify-between px-4 py-3.5 border-b border-slate-800/60">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">Data Context</h2>
          <p className="text-xs text-slate-500 mt-0.5">{selected.length} of {assets.length} active</p>
        </div>
        <button
          onClick={() => setExpanded(false)}
          className="text-slate-500 hover:text-slate-300 text-sm font-mono"
        >
          ‹
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* ── TEMPORAL CONTEXT ── contextual only when applicable */}
        {isTemporal && (
          <div className="space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              Temporal Window
            </p>
            <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-3.5">
              <div className="flex items-center justify-between">
                <div className="text-center">
                  <p className="text-[9px] text-slate-500 uppercase font-bold tracking-wider">Before</p>
                  <p className="text-sm font-semibold text-slate-200 mt-0.5">
                    {new Date(dates[0]).toLocaleDateString("en-GB", { month: "short", year: "numeric" })}
                  </p>
                </div>
                <div className="flex-1 flex items-center justify-center px-3">
                  <div className="h-px flex-1 bg-slate-600" />
                  <span className="text-slate-500 text-xs mx-2 font-mono">
                    {Math.round(
                      (new Date(dates[dates.length - 1]).getTime() - new Date(dates[0]).getTime())
                      / (1000 * 86400)
                    )}d
                  </span>
                  <div className="h-px flex-1 bg-slate-600" />
                </div>
                <div className="text-center">
                  <p className="text-[9px] text-slate-500 uppercase font-bold tracking-wider">After</p>
                  <p className="text-sm font-semibold text-slate-200 mt-0.5">
                    {new Date(dates[dates.length - 1]).toLocaleDateString("en-GB", { month: "short", year: "numeric" })}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── SENSOR WORKFLOW ── */}
        {(opticalCount > 0 || sarCount > 0) && (
          <div className="space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              AI Selected Workflow
            </p>
            <div className="space-y-1.5">
              {opticalCount > 0 && (
                <div className="flex items-center gap-2.5 text-sm text-slate-200">
                  <span className="text-base">🛰️</span>
                  <span>Sentinel-2 Optical</span>
                  <span className="text-emerald-400 ml-auto text-xs">✓</span>
                </div>
              )}
              {sarCount > 0 && (
                <div className="flex items-center gap-2.5 text-sm text-slate-200">
                  <span className="text-base">📡</span>
                  <span>Sentinel-1 SAR</span>
                  <span className="text-emerald-400 ml-auto text-xs">✓</span>
                </div>
              )}
              {opticalCount > 0 && sarCount > 0 && (
                <div className="flex items-center gap-2.5 text-sm text-sky-300 mt-1 pt-1 border-t border-slate-700/50">
                  <span className="text-base">🔀</span>
                  <span className="font-medium">Multimodal Fusion</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── SCENE CARDS (compact) ── */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              Scenes ({assets.length})
            </p>
            {assets.length > 0 && (
              <button
                onClick={() =>
                  onSelectionChange(
                    selected.length === assets.length ? [] : assets.map((a) => a.asset_id),
                  )
                }
                className="text-[10px] text-sky-400 hover:text-sky-300 transition-colors"
              >
                {selected.length === assets.length ? "Deselect all" : "Select all"}
              </button>
            )}
          </div>

          {assets.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-700/60 p-4 text-center text-xs text-slate-500">
              No imagery loaded
            </div>
          ) : (
            <div className="space-y-1.5">
              {assets.map((asset) => {
                const isSelected = selected.includes(asset.asset_id);
                return (
                  <div
                    key={asset.asset_id}
                    onClick={() => toggleSelect(asset.asset_id)}
                    className={`rounded-lg border p-2.5 cursor-pointer transition-all ${
                      isSelected
                        ? "border-sky-500/70 bg-sky-950/30"
                        : "border-slate-700/50 bg-slate-800/30 hover:border-slate-600"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`h-2.5 w-2.5 rounded-full shrink-0 ${isSelected ? "bg-sky-500" : "bg-slate-700"}`} />
                      <div className="min-w-0">
                        <p className={`text-xs font-medium truncate ${isSelected ? "text-slate-200" : "text-slate-400"}`}>
                          {SceneLabel(asset)}
                        </p>
                        {isSelected && (
                          <p className="text-[10px] text-emerald-400 mt-0.5">✓ Active</p>
                        )}
                      </div>
                    </div>

                    {/* Advanced metadata (hidden by default) */}
                    {showAdvanced && (
                      <div className="mt-2 pt-2 border-t border-slate-700/50 text-[9px] text-slate-500 font-mono space-y-0.5">
                        <div>{asset.name}</div>
                        <div>{asset.validation?.crs}</div>
                        <div>{asset.validation?.width}×{asset.validation?.height}px</div>
                        <div>{asset.validation?.bands} bands · {asset.validation?.resolution_m?.[0]}m</div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Advanced metadata toggle */}
          {assets.length > 0 && (
            <button
              onClick={() => setShowAdvanced((v) => !v)}
              className="text-[10px] text-slate-500 hover:text-slate-400 transition-colors"
            >
              {showAdvanced ? "▴ Hide advanced metadata" : "▾ Advanced metadata"}
            </button>
          )}
        </div>

        {/* ── AREA OF INTEREST ── */}
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            Area of Interest
          </p>
          <div className="flex gap-2">
            <button
              onClick={onClearAoi}
              className={`flex-1 rounded-lg border py-1.5 text-xs font-medium transition-all ${
                !aoi && !drawMode
                  ? "border-sky-500/60 bg-sky-950/30 text-sky-300"
                  : "border-slate-700/60 bg-slate-800/30 text-slate-400 hover:border-slate-600"
              }`}
            >
              Full Scene
            </button>
            <button
              onClick={onToggleDrawMode}
              className={`flex-1 rounded-lg border py-1.5 text-xs font-medium transition-all ${
                drawMode
                  ? "border-amber-500/60 bg-amber-950/40 text-amber-300 animate-pulse"
                  : aoi
                  ? "border-emerald-500/60 bg-emerald-950/30 text-emerald-300"
                  : "border-slate-700/60 bg-slate-800/30 text-slate-400 hover:border-slate-600"
              }`}
            >
              {drawMode ? "Drawing…" : aoi ? "✓ Custom AOI" : "Draw AOI"}
            </button>
          </div>
          {drawMode && (
            <p className="text-[10px] text-amber-400/80 leading-tight">
              Click globe vertices · Double-click to close
            </p>
          )}
        </div>

        {/* ── ADD IMAGERY ── */}
        <div>
          <button
            onClick={() => setShowUpload((v) => !v)}
            className="w-full rounded-lg border border-slate-700/60 bg-slate-800/30 hover:bg-slate-800/60 py-2 text-xs font-medium text-slate-300 transition-colors"
          >
            {showUpload ? "▴ Cancel" : "+ Add Imagery"}
          </button>

          {showUpload && (
            <div className="mt-3 space-y-3 animate-slide-up">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-500 block mb-1">Sensor</label>
                  <select
                    value={uploadSensor}
                    onChange={(e) => setUploadSensor(e.target.value as "optical" | "sar")}
                    className="w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-sky-500"
                  >
                    <option value="optical">Optical (RGB/NIR)</option>
                    <option value="sar">SAR (Sentinel-1)</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-slate-500 block mb-1">Date</label>
                  <input
                    type="date"
                    value={uploadDate}
                    onChange={(e) => setUploadDate(e.target.value)}
                    className="w-full rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-sky-500"
                  />
                </div>
              </div>

              <input
                type="file"
                accept=".tif,.tiff"
                onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                className="w-full text-xs text-slate-400 file:mr-2 file:rounded-lg file:border-0 file:bg-sky-700 file:px-2.5 file:py-1 file:text-xs file:font-medium file:text-white hover:file:bg-sky-600 cursor-pointer"
              />

              {uploadError && (
                <p className="text-xs text-rose-400 bg-rose-950/40 border border-rose-800/50 rounded-lg p-2">
                  {uploadError}
                </p>
              )}

              <button
                disabled={!uploadFile || uploading}
                onClick={handleUpload}
                className="w-full rounded-lg bg-sky-600 hover:bg-sky-500 py-2 text-xs font-semibold text-white disabled:opacity-40 transition-colors"
              >
                {uploading ? "Ingesting…" : "Upload & Validate"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
