import React from "react";

export interface QuerySuggestion {
  icon: string;
  label: string;
  category: string;
  query: string;
  mode: "temporal" | "single";
}

export const SUGGESTIONS: QuerySuggestion[] = [
  {
    icon: "🌿",
    label: "Vegetation Loss",
    category: "Spectral Change",
    query: "Show areas where vegetation decreased by more than 20% between June and September.",
    mode: "temporal",
  },
  {
    icon: "💧",
    label: "Water Body Shift",
    category: "Hydrology",
    query: "Identify surface water extent changes and flooded zones between June and September.",
    mode: "temporal",
  },
  {
    icon: "🏗️",
    label: "Urban & Industrial",
    category: "Grounding DINO",
    query: "Detect and localize industrial structures, storage tanks, and transportation facilities.",
    mode: "single",
  },
  {
    icon: "🔥",
    label: "Disaster / Burn Area",
    category: "Emergency RAG",
    query: "Assess canopy damage, burn severity, and retrieve authoritative disaster response SOPs.",
    mode: "temporal",
  },
  {
    icon: "🛰️",
    label: "Optical + SAR Comparison",
    category: "Multimodal Fusion",
    query: "Compare optical and SAR evidence for structural backscatter changes across dates.",
    mode: "temporal",
  },
];

interface Props {
  question: string;
  onQuestionChange: (q: string) => void;
  onAnalyze: () => void;
  isAnalyzing: boolean;
  mode: "temporal" | "single";
  onModeChange: (m: "temporal" | "single") => void;
  sceneCount: number;
}

export function HeroQueryCenterpiece({
  question,
  onQuestionChange,
  onAnalyze,
  isAnalyzing,
  mode,
  onModeChange,
  sceneCount,
}: Props) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onAnalyze();
    }
  };

  const handleSelectSuggestion = (s: QuerySuggestion) => {
    onQuestionChange(s.query);
    onModeChange(s.mode);
  };

  return (
    <div className="relative w-full max-w-4xl mx-auto z-20">
      {/* Outer ambient glow */}
      <div className="absolute -inset-1 rounded-2xl bg-gradient-to-r from-sky-500/20 via-indigo-500/20 to-teal-500/20 blur-xl opacity-75 pointer-events-none" />

      <div className="relative rounded-2xl border border-sky-500/30 bg-slate-900/90 p-3.5 sm:p-4 backdrop-blur-xl shadow-2xl shadow-black/80 space-y-3">
        {/* Header line: Title & Mode Selector */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-2.5">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-sky-500/20 text-sky-400 text-xs shadow-inner">
              ✦
            </span>
            <div>
              <h2 className="text-xs font-bold tracking-wider text-slate-100 uppercase font-display flex items-center gap-1.5">
                <span>What do you want to know?</span>
                <span className="text-[10px] text-sky-400/90 font-mono lowercase tracking-normal">
                  — Natural Language Remote Sensing Assistant
                </span>
              </h2>
            </div>
          </div>

          {/* Mode Switcher: Single Image vs Temporal Change */}
          <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-950/70 p-0.5 text-[11px]">
            <button
              onClick={() => onModeChange("temporal")}
              className={`flex items-center gap-1 rounded-md px-2.5 py-1 font-medium transition-all ${
                mode === "temporal"
                  ? "bg-sky-600 text-white shadow-sm font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <span>⏱️</span>
              <span>Temporal Change</span>
            </button>
            <button
              onClick={() => onModeChange("single")}
              className={`flex items-center gap-1 rounded-md px-2.5 py-1 font-medium transition-all ${
                mode === "single"
                  ? "bg-sky-600 text-white shadow-sm font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <span>🎯</span>
              <span>Single Image</span>
            </button>
          </div>
        </div>

        {/* The Natural Language Query Input */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none text-sky-400">
              <span className="text-sm">✦</span>
            </div>
            <input
              type="text"
              value={question}
              onChange={(e) => onQuestionChange(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isAnalyzing}
              placeholder="Ask SatQuery anything about your satellite imagery (e.g., 'Show areas where vegetation decreased >20%')..."
              className="w-full rounded-xl border border-slate-700/80 bg-slate-950/80 pl-9 pr-24 py-2.5 text-xs sm:text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/30 transition-all font-sans"
            />
            <span className="absolute inset-y-0 right-3 flex items-center text-[10px] text-slate-500 font-mono pointer-events-none">
              Press Enter ↵
            </span>
          </div>

          {/* Primary Action Button */}
          <button
            onClick={onAnalyze}
            disabled={isAnalyzing || sceneCount === 0}
            className={`flex items-center gap-2 rounded-xl px-5 py-2.5 text-xs sm:text-sm font-bold text-white transition-all shadow-lg cursor-pointer ${
              isAnalyzing
                ? "bg-slate-800 text-slate-400 cursor-wait"
                : "bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 shadow-sky-500/25 active:scale-[0.98]"
            }`}
          >
            {isAnalyzing ? (
              <>
                <span className="h-3.5 w-3.5 rounded-full border-2 border-slate-400 border-t-transparent animate-spin" />
                <span>Orchestrating...</span>
              </>
            ) : (
              <>
                <span>✦</span>
                <span>Analyze</span>
              </>
            )}
          </button>
        </div>

        {/* Suggestion Chips */}
        <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 shrink-0">
            Intelligent Queries:
          </span>
          {SUGGESTIONS.map((s, idx) => (
            <button
              key={idx}
              onClick={() => handleSelectSuggestion(s)}
              disabled={isAnalyzing}
              title={`${s.category}: ${s.query}`}
              className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-950/60 hover:bg-slate-800/80 hover:border-sky-500/60 px-2 py-1 text-[11px] text-slate-300 hover:text-white transition-all shadow-sm group cursor-pointer"
            >
              <span className="text-xs group-hover:scale-110 transition-transform">
                {s.icon}
              </span>
              <span className="font-medium">{s.label}</span>
            </button>
          ))}
        </div>

        {/* Active Analysis Banner */}
        {isAnalyzing && (
          <div className="flex items-center justify-between rounded-lg border border-sky-500/40 bg-sky-950/40 px-3 py-1.5 text-xs text-sky-300 animate-pulse">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-sky-400 animate-ping" />
              <span className="font-semibold">SATQUERY AI IS THINKING:</span>
              <span className="text-slate-300 text-[11px]">
                Understanding query → Selecting specialist models → Analyzing imagery → Verifying evidence
              </span>
            </div>
            <span className="text-[10px] font-mono text-sky-400 uppercase">
              Autonomous Pipeline Active
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
