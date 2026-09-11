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

  const toggle = (id: string) =>
    onSelectionChange(
      selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id],
    );

  return (
    <div className="space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="file" accept=".tif,.tiff"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="max-w-56 file:mr-2 file:rounded file:border-0 file:bg-slate-700 file:px-2 file:py-1 file:text-slate-200"
        />
        <select value={sensor} onChange={(e) => setSensor(e.target.value as "optical" | "sar")}
          className="rounded bg-slate-800 px-2 py-1">
          <option value="optical">optical</option>
          <option value="sar">sar</option>
        </select>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
          className="rounded bg-slate-800 px-2 py-1" />
        <button
          disabled={!file || uploading}
          onClick={() => file && onUpload(file, sensor, date)}
          className="rounded bg-sky-600 px-3 py-1 font-medium text-white hover:bg-sky-500 disabled:opacity-40">
          {uploading ? "Uploading…" : "Upload GeoTIFF"}
        </button>
        {uploadError && <span className="text-red-400">{uploadError}</span>}
      </div>
      {assets.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {assets.map((a) => (
            <button key={a.asset_id} onClick={() => toggle(a.asset_id)}
              className={`rounded border px-2 py-1 text-xs ${
                selected.includes(a.asset_id)
                  ? "border-sky-400 bg-sky-900/60 text-sky-200"
                  : "border-slate-700 bg-slate-800/60 text-slate-400"}`}>
              <span className="font-mono">{a.name}</span>
              <span className="ml-1 opacity-60">
                {a.sensor_type}{a.capture_date ? ` · ${a.capture_date}` : ""}
              </span>
            </button>
          ))}
          <span className="self-center text-xs text-slate-500">
            {selected.length} selected for analysis
          </span>
        </div>
      )}
    </div>
  );
}
