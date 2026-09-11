import React, { useState } from "react";
import type { UploadedAsset } from "../services/types";

interface Props {
  assets: UploadedAsset[];
  selected: string[];
  onSelectionChange: (ids: string[]) => void;
  onUpload: (file: File, sensor: "optical" | "sar", date: string) => void;
  uploading: boolean;
  uploadError: string | null;
}

export function QueryBar({
  assets, selected, onSelectionChange, onUpload, uploading, uploadError,
}: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [sensor, setSensor] = useState<"optical" | "sar">("optical");
  const [date, setDate] = useState("");
  const [showUpload, setShowUpload] = useState(false);

  const toggle = (id: string) =>
    onSelectionChange(
      selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id],
    );

  const selectAll = () => onSelectionChange(assets.map((a) => a.asset_id));
  const clearSelection = () => onSelectionChange([]);

  return (
    <div className="space-y-2.5">
      {/* Action Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Available Scenes
          </span>
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-sky-400">
            {assets.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {assets.length > 0 && (
            <button
              onClick={selected.length === assets.length ? clearSelection : selectAll}
              className="text-[11px] text-slate-400 hover:text-sky-300 transition-colors"
            >
              {selected.length === assets.length ? "Deselect all" : "Select all"}
            </button>
          )}
          <button
            onClick={() => setShowUpload((v) => !v)}
            className="flex items-center gap-1 rounded bg-slate-800 hover:bg-slate-700 px-2 py-1 text-[11px] font-medium text-slate-200 transition-all border border-slate-700/60"
          >
            <span>{showUpload ? "Hide Upload" : "+ Add GeoTIFF"}</span>
          </button>
        </div>
      </div>

      {/* Expandable Upload Drawer */}
      {showUpload && (
        <div className="rounded-xl border border-sky-500/30 bg-slate-900/90 p-3 space-y-2.5 shadow-lg">
          <div className="text-[11px] font-semibold text-sky-300 flex items-center gap-1.5">
            <span>🛰️ Ingest Satellite Raster (GeoTIFF)</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-slate-400 block mb-0.5">Sensor Type</label>
              <select
                value={sensor}
                onChange={(e) => setSensor(e.target.value as "optical" | "sar")}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200 outline-none focus:border-sky-500"
              >
                <option value="optical">Optical (RGB / NIR)</option>
                <option value="sar">SAR (Synthetic Aperture)</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] text-slate-400 block mb-0.5">Capture Date</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200 outline-none focus:border-sky-500"
              />
            </div>
          </div>

          <div>
            <label className="text-[10px] text-slate-400 block mb-0.5">Raster File (.tif / .tiff)</label>
            <input
              type="file"
              accept=".tif,.tiff"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full text-xs text-slate-400 file:mr-2 file:rounded-md file:border-0 file:bg-sky-600 file:px-2.5 file:py-1 file:text-xs file:font-semibold file:text-white hover:file:bg-sky-500 cursor-pointer"
            />
          </div>

          <button
            disabled={!file || uploading}
            onClick={() => file && onUpload(file, sensor, date)}
            className="w-full rounded-lg bg-sky-600 hover:bg-sky-500 py-1.5 text-xs font-semibold text-white transition-all shadow-md shadow-sky-600/30 disabled:opacity-40"
          >
            {uploading ? "Ingesting & Validating CRS..." : "Upload & Validate"}
          </button>

          {uploadError && (
            <p className="text-[11px] text-rose-400 bg-rose-950/40 border border-rose-900/50 rounded p-1.5">
              {uploadError}
            </p>
          )}
        </div>
      )}

      {/* Asset Cards List */}
      <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
        {assets.map((a) => {
          const isSelected = selected.includes(a.asset_id);
          const isOptical = a.sensor_type === "optical";
          return (
            <div
              key={a.asset_id}
              onClick={() => toggle(a.asset_id)}
              className={`cursor-pointer rounded-lg border p-2.5 transition-all select-none ${
                isSelected
                  ? "border-sky-500 bg-sky-950/40 shadow-sm shadow-sky-500/20"
                  : "border-slate-800/80 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-900/60"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => {}}
                    className="h-3.5 w-3.5 rounded border-slate-700 bg-slate-800 text-sky-500 accent-sky-500"
                  />
                  <div className="truncate">
                    <span className="font-mono text-xs font-semibold text-slate-200">
                      {a.name}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  <span
                    className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${
                      isOptical
                        ? "bg-emerald-950/80 text-emerald-300 border border-emerald-800"
                        : "bg-blue-950/80 text-blue-300 border border-blue-800"
                    }`}
                  >
                    {a.sensor_type}
                  </span>
                  {a.capture_date && (
                    <span className="font-mono text-[10px] text-slate-400 bg-slate-800/70 px-1.5 py-0.5 rounded">
                      {a.capture_date}
                    </span>
                  )}
                </div>
              </div>

              {a.validation && (
                <div className="mt-1.5 flex items-center gap-2 text-[10px] text-slate-400">
                  <span>{a.validation.crs || "EPSG:32643"}</span>
                  <span>•</span>
                  <span>{a.validation.bands || 4} Bands</span>
                  {a.validation.width && (
                    <>
                      <span>•</span>
                      <span>{a.validation.width}×{a.validation.height}px</span>
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {assets.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-800 p-4 text-center text-xs text-slate-500">
            No raster assets loaded. Click "+ Add GeoTIFF" or use a sample preset above.
          </div>
        )}
      </div>

      <div className="flex justify-between items-center text-[10px] text-slate-400 px-1">
        <span>Selected for multi-temporal run:</span>
        <span className="font-mono font-semibold text-sky-400">{selected.length} of {assets.length}</span>
      </div>
    </div>
  );
}
