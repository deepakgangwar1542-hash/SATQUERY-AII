"""GIS Code Agent — dynamic analysis-code generation + sandbox execution (FR-12).

v1 generation strategy (deterministic, demo-safe): for each approved intent a
pre-audited template produces the full Python source; parameters (thresholds,
band mappings, asset paths) are injected as `input/params.json`, never by
string-substitution into code. An LLM-backed generator can be added behind
`generate_with_llm()` — it MUST pass the same AST validator (FR-12 AC2) and
the §12.3 regeneration rule (validator reason appended to the prompt) before
execution. The exact source executed is always returned to the client
(FR-12 AC4).
"""
from __future__ import annotations

from pathlib import Path

from ..sandbox import runner
from ..sandbox.validator import validate_code

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "sandbox" / "templates"

INTENT_PARAMS = {
    "ndvi_delta_threshold": {"requires": 2, "kind": "optical"},
    "ndwi_change": {"requires": 2, "kind": "optical"},
    "area_stats": {"requires": 1, "kind": "optical"},
}


def choose_intent(query: str, n_assets: int) -> str | None:
    q = (query or "").lower()
    if "water" in q or "flood" in q or "ndwi" in q:
        return "ndwi_change" if n_assets >= 2 else "area_stats"
    if any(t in q for t in ("ndvi", "vegetation", "decrease", "increase",
                            "percent", "%", "area", "threshold", "km2", "km²",
                            "how much", "change")):
        return "ndvi_delta_threshold" if n_assets >= 2 else "area_stats"
    return "area_stats" if n_assets >= 1 else None


def generate_analysis_code(intent: str, params: dict) -> dict:
    """Return {source, params, template}. Raises on unknown intent."""
    template_path = TEMPLATES_DIR / f"{intent}.py"
    if intent not in INTENT_PARAMS or not template_path.exists():
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
                     timeout_s: int = runner.DEFAULT_TIMEOUT_S) -> dict:
    """Generate + sandbox-execute. Returns {generated_code, result, sandbox_log}."""
    gen = generate_analysis_code(intent, params)
    run = runner.run_sandboxed(gen["source"], asset_paths, params=gen["params"],
                               timeout_s=timeout_s)
    # §12.3 recovery: on static-validation failure regenerate once with the
    # rejection reasons recorded (templates always pass; the hook is here for
    # a future LLM generator).
    if not run["ok"] and run["validation_reasons"]:
        gen = generate_analysis_code(intent, {**params,
                                              "validator_rejections": run["validation_reasons"]})
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
