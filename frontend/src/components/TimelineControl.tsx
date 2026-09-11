import { useEffect, useRef, useState } from "react";

interface Props {
  dates: string[]; // ISO dates across the selected assets
  onDateChange: (date: string) => void;
}

/** Temporal replay (FR-15): scrub or auto-replay the per-date transitions.
 * Backend supports N≥2 dates; v1 demos 2–3. */
export function TimelineControl({ dates, onDateChange }: Props) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (index >= dates.length) setIndex(0);
  }, [dates.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    onDateChange(dates[index] ?? dates[0]);
  }, [index]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!playing) {
      if (timer.current) window.clearInterval(timer.current);
      return;
    }
    timer.current = window.setInterval(() => {
      setIndex((i) => (i + 1) % dates.length);
    }, 1600);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [playing, dates.length]);

  if (dates.length < 2) {
    return <p className="text-xs text-slate-600">
      Select ≥2 dated assets to enable temporal replay.
    </p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setPlaying((p) => !p)}
          className={`rounded px-3 py-1 text-xs font-medium ${
            playing ? "bg-amber-600 hover:bg-amber-500" : "bg-sky-600 hover:bg-sky-500"} text-white`}>
          {playing ? "⏸ Pause replay" : "▶ Replay"}
        </button>
        <input
          type="range" min={0} max={dates.length - 1} value={index}
          onChange={(e) => { setPlaying(false); setIndex(Number(e.target.value)); }}
          className="h-1 flex-1 accent-sky-500"
        />
      </div>
      <div className="flex justify-between">
        {dates.map((d, i) => (
          <button key={d} onClick={() => { setPlaying(false); setIndex(i); }}
            className={`rounded px-2 py-0.5 font-mono text-[11px] ${
              i === index ? "bg-sky-900/70 text-sky-200" : "text-slate-500 hover:text-slate-300"}`}>
            {d}
          </button>
        ))}
      </div>
    </div>
  );
}
