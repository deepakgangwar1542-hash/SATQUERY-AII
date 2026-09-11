interface Props {
  confidence: number;
  breakdown: Record<string, number>;
  verdict: string;
}

const LABELS: Record<string, string> = {
  model_confidence: "Model",
  evidence_agreement: "Evidence agreement",
  sensor_reliability: "Sensor reliability",
  data_quality: "Data quality",
  spatial_consistency: "Spatial consistency",
  temporal_consistency: "Temporal consistency",
};

const VERDICT_STYLE: Record<string, string> = {
  CONSISTENT: "bg-emerald-900/60 text-emerald-300 border-emerald-700",
  PARTIALLY_CONSISTENT: "bg-amber-900/50 text-amber-300 border-amber-700",
  CONFLICTING: "bg-red-900/60 text-red-300 border-red-700",
};

/** §12.4 confidence breakdown as labeled bars — not a single number. */
export function ConfidencePanel({ confidence, breakdown, verdict }: Props) {
  const pct = Math.round(confidence * 100);
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-2xl font-semibold text-sky-300">{pct}%</span>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${
          VERDICT_STYLE[verdict] ?? VERDICT_STYLE.PARTIALLY_CONSISTENT}`}>
          {verdict.replace("_", " ")}
        </span>
      </div>
      <div className="space-y-1.5">
        {Object.entries(breakdown).map(([k, v]) => (
          <div key={k}>
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>{LABELS[k] ?? k}</span>
              <span>{(v * 100).toFixed(0)}%</span>
            </div>
            <div className="h-1 overflow-hidden rounded bg-slate-800">
              <div className="h-full rounded bg-gradient-to-r from-sky-600 to-emerald-500"
                style={{ width: `${Math.max(2, Math.min(100, v * 100))}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
