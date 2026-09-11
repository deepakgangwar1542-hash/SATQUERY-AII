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

export function ConfidencePanel({ confidence, breakdown, verdict }: Props) {
  const pct = Math.round(confidence * 100);
  const isHigh = pct >= 80;
  const isMed = pct >= 50 && pct < 80;

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-900/50 p-3.5 backdrop-blur-md space-y-3">
      <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
            Multimodal Confidence
          </span>
          <div className="flex items-baseline gap-1.5 mt-0.5">
            <span className={`text-2xl font-bold font-mono ${
              isHigh ? "text-emerald-400" : isMed ? "text-sky-400" : "text-amber-400"
            }`}>
              {pct}%
            </span>
            <span className="text-[10px] text-slate-400">weighted score</span>
          </div>
        </div>

        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase ${
          VERDICT_STYLE[verdict] ?? VERDICT_STYLE.PARTIALLY_CONSISTENT
        }`}>
          {verdict.replace("_", " ")}
        </span>
      </div>

      <div className="space-y-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
          Component Breakdown
        </span>
        <div className="space-y-1.5">
          {Object.entries(breakdown).map(([k, v]) => (
            <div key={k} className="space-y-0.5">
              <div className="flex justify-between text-[10px]">
                <span className="text-slate-300 font-medium">{LABELS[k] ?? k}</span>
                <span className="font-mono text-slate-400">{(v * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-slate-800 ring-1 ring-slate-700/30">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-400 transition-all duration-300"
                  style={{ width: `${Math.max(3, Math.min(100, v * 100))}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

