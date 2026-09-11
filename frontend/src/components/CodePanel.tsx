import type { GeneratedCode } from "../services/types";

interface Props {
  code: GeneratedCode[];
}

const KEYWORDS = new Set([
  "import", "from", "as", "def", "return", "with", "open", "for", "in", "if",
  "else", "elif", "while", "try", "except", "raise", "None", "True", "False",
  "and", "or", "not", "lambda", "class", "pass", "break", "continue",
]);

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Tiny dependency-free Python highlighter — good enough for the code panel. */
function highlight(line: string): string {
  const escaped = escapeHtml(line);
  return escaped.replace(
    /("[^"]*"|#[^\n]*|\b\w+\b)/g,
    (tok) => {
      if (tok.startsWith("#")) return `<span class="text-slate-500">${tok}</span>`;
      if (tok.startsWith('"')) return `<span class="text-amber-300">${tok}</span>`;
      if (KEYWORDS.has(tok)) return `<span class="text-sky-400">${tok}</span>`;
      return tok;
    },
  );
}

/** The exact code the sandbox executed — P0 trust feature (FR-12 AC4). */
export function CodePanel({ code }: Props) {
  if (code.length === 0) {
    return <p className="text-xs text-slate-600">
      No generated code for this query (numeric/statistical questions trigger
      the GIS code agent).
    </p>;
  }
  return (
    <div className="space-y-4">
      {code.map((c, i) => (
        <div key={i}>
          <div className="mb-1 flex items-center justify-between text-[10px] text-slate-500">
            <span className="font-mono">
              {c.agent} · {c.template ?? "generated"} · {c.language}
            </span>
            <button
              className="rounded bg-slate-800 px-1.5 py-0.5 hover:bg-slate-700"
              onClick={() => navigator.clipboard?.writeText(c.source)}>
              copy
            </button>
          </div>
          <pre className="max-h-96 overflow-auto rounded border border-slate-800 bg-slate-950 p-3 font-mono text-[11px] leading-relaxed text-slate-300">
            <code dangerouslySetInnerHTML={{ __html: c.source.split("\n").map(highlight).join("\n") }} />
          </pre>
        </div>
      ))}
    </div>
  );
}
