/**
 * QueryComposer — PRIMARY INTERACTION COMPONENT
 *
 * IDLE state:   Full hero layout — headline, textarea, suggestion chips
 * RESULT state: Collapsed pill — truncated query + "Edit Query" action
 *
 * This is the most important component in the application.
 */
import React, { useRef, useEffect } from "react";
import type { AppState } from "../services/types";

export interface QuerySuggestion {
  icon: string;
  label: string;
  text: string;
}

export const SUGGESTIONS: QuerySuggestion[] = [
  {
    icon: "🌊",
    label: "Flooding",
    text: "Identify areas where flooding increased between June and August.",
  },
  {
    icon: "🏗️",
    label: "Buildings",
    text: "Detect and localize industrial structures, storage tanks, and transportation facilities.",
  },
  {
    icon: "🌿",
    label: "Vegetation",
    text: "Show areas where vegetation decreased by more than 20% between June and September.",
  },
  {
    icon: "🔥",
    label: "Disaster",
    text: "Assess canopy burn area and retrieve emergency response protocols for the affected region.",
  },
  {
    icon: "📡",
    label: "Optical + SAR",
    text: "Compare optical and SAR evidence for structural changes across dates.",
  },
];

interface Props {
  question: string;
  onChange: (q: string) => void;
  onAnalyze: () => void;
  onEditQuery: () => void;
  appState: AppState;
  sceneCount: number;
}

export function QueryComposer({
  question,
  onChange,
  onAnalyze,
  onEditQuery,
  appState,
  sceneCount,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, [question]);

  // Focus textarea when entering idle state
  useEffect(() => {
    if (appState === "idle" && textareaRef.current) {
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }, [appState]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      onAnalyze();
    }
  };

  const canAnalyze = question.trim().length > 3 && sceneCount > 0;

  // ── COLLAPSED STATE (result / analyzing) ──────────────────────────────
  if (appState === "result" || appState === "analyzing") {
    return (
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-800/60 bg-slate-900/40">
        <span className="text-sky-400 text-sm font-bold shrink-0">✦</span>
        <p className="text-sm text-slate-200 truncate flex-1 italic">
          "{question}"
        </p>
        {appState === "result" && (
          <button
            onClick={onEditQuery}
            className="shrink-0 text-xs text-sky-400 hover:text-sky-300 font-medium border border-slate-700/80 bg-slate-800/60 hover:bg-slate-700/60 px-3 py-1 rounded-lg transition-colors"
          >
            Edit Query
          </button>
        )}
      </div>
    );
  }

  // ── IDLE STATE — Full Hero Composer ──────────────────────────────────
  return (
    <div className="flex flex-col items-center justify-center w-full py-8 px-4 animate-fade-in">
      {/* Brand headline */}
      <div className="mb-1 text-sky-400/70 text-xs font-mono uppercase tracking-widest">
        SatQuery AI
      </div>
      <h1 className="text-2xl sm:text-3xl font-bold text-slate-100 mb-6 text-center leading-tight">
        What do you want to know?
      </h1>

      {/* The Query Input Box */}
      <div
        className="w-full max-w-2xl rounded-2xl border border-slate-700/80 bg-slate-900/80 focus-within:border-sky-500/60 focus-within:ring-2 focus-within:ring-sky-500/20 transition-all shadow-2xl shadow-black/60"
        style={{ backdropFilter: "blur(20px)" }}
      >
        <textarea
          ref={textareaRef}
          rows={2}
          value={question}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about your satellite imagery… (⌘ + Enter to analyze)"
          className="query-input w-full px-5 pt-4 pb-2 min-h-[56px] max-h-[120px]"
        />

        {/* Bottom row of the input box */}
        <div className="flex items-center justify-between px-5 pb-4 pt-1">
          <span className="text-xs text-slate-500">
            {sceneCount === 0 ? (
              <span className="text-amber-400">⚠ No imagery loaded — try Demo Mode</span>
            ) : (
              <span className="text-slate-400">{sceneCount} scene{sceneCount !== 1 ? "s" : ""} loaded</span>
            )}
          </span>

          <button
            onClick={onAnalyze}
            disabled={!canAnalyze}
            title="Analyze (⌘+Enter)"
            className={`flex items-center gap-2 rounded-xl px-5 py-2 text-sm font-semibold transition-all shadow-lg ${
              canAnalyze
                ? "bg-sky-500 hover:bg-sky-400 text-white shadow-sky-500/30 active:scale-[0.98]"
                : "bg-slate-800 text-slate-500 cursor-not-allowed"
            }`}
          >
            <span>Analyze</span>
            <span className="text-base">➤</span>
          </button>
        </div>
      </div>

      {/* Suggestion chips — visible only in IDLE */}
      <div className="flex flex-wrap items-center justify-center gap-2 mt-5 max-w-xl">
        {SUGGESTIONS.map((s, i) => (
          <button
            key={i}
            onClick={() => onChange(s.text)}
            className="flex items-center gap-1.5 rounded-full border border-slate-700/80 bg-slate-900/60 hover:bg-slate-800/80 hover:border-sky-500/50 px-3 py-1.5 text-sm text-slate-300 hover:text-white transition-all"
          >
            <span>{s.icon}</span>
            <span className="font-medium">{s.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
