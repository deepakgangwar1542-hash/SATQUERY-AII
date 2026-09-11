"""GIS Code Agent — dynamic analysis-code generation + sandbox execution (FR-12).

v1 generation strategy (deterministic, demo-safe): for each approved intent a
pre-audited template produces the full Python source; parameters (thresholds,
band mappings, asset paths) are injected as `input/params.json`, never by
string-substitution into code. An LLM-backed generator is available behind
`generate_with_llm()` for queries that don't match an approved template — it
MUST pass the same AST validator (FR-12 AC2) and the §12.3 regeneration rule
(validator reason appended to the prompt, one retry) before execution. The
exact source executed is always returned to the client (FR-12 AC4), and the
LLM path is never used silently: `execute_analysis()` only calls it when
`choose_intent()` found no template match, and only when `XAI_API_KEY` is
configured — otherwise the caller gets the existing "no approved template"
error, unchanged.
"""
from __future__ import annotations

from pathlib import Path

from ..sandbox import runner
from ..sandbox.validator import validate_code
from ..services import llm_client

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "sandbox" / "templates"

INTENT_PARAMS = {
    "ndvi_delta_threshold": {"requires": 2, "kind": "optical"},
    "ndwi_change": {"requires": 2, "kind": "optical"},
    "area_stats": {"requires": 1, "kind": "optical"},
}

_LLM_SYSTEM_PROMPT = (
    "You write short, self-contained Python scripts for a sandboxed "
    "geospatial analysis runner. The script reads raster paths and "
    "parameters from a JSON file at input/params.json (already written for "
    "you; do not write to it), performs the requested raster analysis using "
    "only rasterio/numpy/shapely/geopandas/pyproj, and writes its result to "
    "output/result.json (a small JSON-serializable dict of scalar "
    "statistics) and optionally output/output.geojson (a GeoJSON "
    "FeatureCollection in EPSG:4326). Rules: no network access, no "
    "subprocess/os.system/eval/exec, no imports outside the allowed "
    "scientific-Python stack, no reads/writes outside input/ and output/. "
    "Return ONLY the raw Python source code, no markdown fences, no "
    "explanation."
)


def generate_with_llm(query: str, params: dict, retry_reasons: list[str] | None = None) -> dict | None:
    """LLM-backed fallback code generation for queries with no matching
    template. Returns {source, params, template} or None if the LLM is
    unavailable, fails, or its output does not pass static validation after
    one regeneration attempt (§12.3)."""
    if not llm_client.is_available():
        return None
    user_prompt = f"User question: {query!r}\nAvailable input params (JSON): {params!r}"
    if retry_reasons:
        user_prompt += (f"\n\nYour previous attempt was rejected by static validation "
                        f"for these reasons: {retry_reasons}. Fix them and try again.")
    source = llm_client.complete(_LLM_SYSTEM_PROMPT, user_prompt, max_tokens=1200)
    if not source:
        return None
    reasons = validate_code(source, allowed_open_dirs=["input", "output"])
    if reasons:
        if retry_reasons:  # already retried once; give up (§12.3: one retry)
            return None
        return generate_with_llm(query, params, retry_reasons=reasons)
    return {"source": source, "params": params, "template": "llm_generated"}


def choose_intent(query: str, n_assets: int) -> str | None:
    q = (query or "").lower()
    if "water" in q or "flood" in q or "ndwi" in q:
        return "ndwi_change" if n_assets >= 2 else "area_stats"
    if any(t in q for t in ("ndvi", "vegetation", "decrease", "increase",
                            "percent", "%", "area", "threshold", "km2", "km²",
                            "how much", "change")):
        return "ndvi_delta_threshold" if n_assets >= 2 else "area_stats"
    return "area_stats" if n_assets >= 1 else None


def generate_analysis_code(intent: str, params: dict, query: str | None = None) -> dict:
    """Return {source, params, template}. Falls back to `generate_with_llm()`
    when `intent` has no approved template and a `query` string is given
    (only reachable when `XAI_API_KEY` is configured); otherwise raises, same
    as before."""
    template_path = TEMPLATES_DIR / f"{intent}.py"
    if intent not in INTENT_PARAMS or not template_path.exists():
        if query is not None:
            llm_gen = generate_with_llm(query, params)
            if llm_gen is not None:
                return llm_gen
        raise ValueError(
            f"intent '{intent}' has no approved template. v1 supports: "
            f"{sorted(INTENT_PARAMS)}. "
            "This limitation is reported to the user explicitly (§12.3)."
        )
    source = template_path.read_text(encoding="utf-8")
    reasons = validate_code(source, allowed_open_dirs=["input", "output"])
    if reasons:  # cannot happen for audited templates; guard anyway
        raise ValueError(f"template failed static validation: {reasons}")
    return {"source": source, "params": params, "template": intent}


def execute_analysis(intent: str, params: dict, asset_paths: list[str],
                     timeout_s: int = runner.DEFAULT_TIMEOUT_S,
                     query: str | None = None) -> dict:
    """Generate + sandbox-execute. Returns {generated_code, result, sandbox_log}."""
    gen = generate_analysis_code(intent, params, query=query)
    run = runner.run_sandboxed(gen["source"], asset_paths, params=gen["params"],
                               timeout_s=timeout_s)
    # §12.3 recovery: on static-validation failure regenerate once with the
    # rejection reasons recorded. Templates always pass; for the LLM path
    # `generate_with_llm()` already retries once internally, so this covers
    # the template branch's contract unchanged.
    if not run["ok"] and run["validation_reasons"]:
        gen = generate_analysis_code(intent, {**params,
                                              "validator_rejections": run["validation_reasons"]},
                                     query=query)
        run = runner.run_sandboxed(gen["source"], asset_paths, params=gen["params"],
                                   timeout_s=timeout_s)
    return {
        "generated_code": [{"agent": "gis_code_agent", "language": "python",
                            "source": gen["source"], "template": intent}],
        "result": run.get("outputs", {}).get("result.json", {}),
        "geojson": run.get("outputs", {}).get("output.geojson"),
        "sandbox_log": {"exit_code": run["exit_code"], "duration_ms": run["duration_ms"],
                        "stdout": run["stdout"][-2000:], "stderr": run["stderr"][-2000:],
                        "validation_reasons": run["validation_reasons"]},
        "ok": run["ok"],
    }
