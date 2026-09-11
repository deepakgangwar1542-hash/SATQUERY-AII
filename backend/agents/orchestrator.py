"""Orchestrator — explicit state graph over the agents (FR-9, §12).

State schema per §12.1; graph per §12.2; failure recovery per §12.3; plan per
the deterministic planner. Every node appends §12.5 trace events and live
agent-status updates to the job store, so the UI can stream progress (§7.1).
"""
from __future__ import annotations

import logging
from typing import TypedDict

from ..services import artifact_store, job_store
from ..utils.assets import resolve_asset_paths
from . import change as change_agent
from . import change_vqa as change_vqa_agent
from . import code_agent as code_agent_mod
from . import grounding as grounding_agent
from . import multimodal as multimodal_agent
from . import perception as perception_agent
from . import rag as rag_agent
from . import verifier as verifier_mod
from .graph import Graph
from .planner import build_plan, narrate_plan, plan_rationale
from .trace import traced

log = logging.getLogger("satquery.orchestrator")


class OrchestratorState(TypedDict, total=False):
    job_id: str
    query: str
    region: dict | None
    dates: list[str]
    assets: list[dict]
    plan: list[str]
    plan_rationale: dict
    agent_outputs: dict[str, dict]
    artifacts: list[dict]
    evidence: list[dict]
    confidence_breakdown: dict[str, float]
    uncertainty: list[dict]
    consistency_verdict: str
    execution_trace: list[dict]
    status: str
    error: str | None
    final: dict


def _optical_asset(state: OrchestratorState) -> dict | None:
    return next((a for a in state["assets"] if a.get("sensor_type") != "sar"), None)


def _sar_asset(state: OrchestratorState) -> dict | None:
    return next((a for a in state["assets"] if a.get("sensor_type") == "sar"), None)


def _succeed(state: OrchestratorState, name: str, out: dict) -> None:
    state["agent_outputs"][name] = out
    job_store.set_agent_status(state["job_id"], name, "completed")


def _fail(state: OrchestratorState, name: str, exc: Exception) -> None:
    """§7.2/§12.3: record the failure, add an uncertainty note, continue.
    Any partial output already stored (e.g. generated code from a failed
    sandbox run) is preserved — FR-12 AC4 wants the executed code surfaced
    even when execution fails."""
    log.warning("agent %s failed: %s", name, exc)
    job_store.set_agent_status(state["job_id"], name, "failed")
    state["uncertainty"].append({
        "signal": f"agent_failed_{name}", "severity": "medium",
        "explanation": f"{name} failed after one retry and was skipped: {exc}"})
    prev = state["agent_outputs"].get(name) or {}
    state["agent_outputs"][name] = {**prev, "failed": True, "error": str(exc)}


def _agent_node(name: str, fn):
    """Node wrapper: live status, §12.5 trace, retry-once, degrade (§12.3)."""
    def node(state: OrchestratorState) -> None:
        job_id = state["job_id"]
        job_store.set_agent_status(job_id, name, "running")
        last_exc: Exception | None = None
        for attempt in (1, 2):
            try:
                with traced(job_id, name, f"{name}_attempt_{attempt}",
                            sink=state["execution_trace"]):
                    out = fn(state) or {}
                _succeed(state, name, out)
                return
            except Exception as exc:  # noqa: BLE001 — orchestrator must survive
                last_exc = exc
        _fail(state, name, last_exc)  # type: ignore[arg-type]
    return node


# ---------------------------------------------------------------- nodes ----

def planner_node(state: OrchestratorState) -> None:
    with traced(state["job_id"], "orchestrator", "plan", sink=state["execution_trace"]):
        state["plan"] = build_plan(state["query"], state["assets"])
        state["plan_rationale"] = plan_rationale(state["query"], state["assets"])
        # Optional LLM narration (§ xAI enhancement): purely explanatory,
        # never influences `state["plan"]` itself. None when XAI_API_KEY is
        # unset or the call fails.
        state["plan_rationale"]["narrative"] = narrate_plan(
            state["query"], state["plan"], state["plan_rationale"])
        state["dates"] = sorted({a.get("capture_date") for a in state["assets"]
                                 if a.get("capture_date")})


def input_validator_node(state: OrchestratorState) -> None:
    with traced(state["job_id"], "input_validator", "validate_assets",
                sink=state["execution_trace"]):
        from ..geospatial import raster as graster
        reports, paths = {}, resolve_asset_paths(state["assets"])
        for a in state["assets"]:
            p = paths.get(a["asset_id"])
            if not p:
                reports[a["asset_id"]] = {"valid": False, "errors": ["asset_not_found"]}
                continue
            reports[a["asset_id"]] = graster.validate_raster(p, a.get("sensor_type"))
        all_valid = all(r.get("valid") for r in reports.values())
        if not any(r.get("valid") for r in reports.values()):
            raise RuntimeError(f"all_assets_invalid:{reports}")
        mappings = {}
        for a in state["assets"]:
            r = reports.get(a["asset_id"], {})
            if a.get("band_mapping"):
                mappings[a["asset_id"]] = a["band_mapping"]
            elif r.get("band_mapping_guess"):
                mappings[a["asset_id"]] = r["band_mapping_guess"]
        return {
            "reports": reports, "all_valid": all_valid,
            "any_missing_nodata": any(r.get("nodata") is None for r in reports.values()),
            "band_mapping_confidence": min(
                (r.get("band_mapping_confidence", "high") for r in reports.values()),
                key=lambda c: {"high": 3, "medium": 2, "low": 1, "none": 0}.get(c, 0),
            ),
            "mappings": mappings,
        }


def perception_node(state: OrchestratorState) -> None:
    asset = _optical_asset(state) or (state["assets"] or [{}])[0]
    paths = resolve_asset_paths(state["assets"])
    path = paths.get(asset.get("asset_id"))
    if not path:
        raise RuntimeError("perception: optical asset missing")
    mapping = state["agent_outputs"].get("input_validator", {}).get("mappings", {}).get(
        asset.get("asset_id"))
    out = perception_agent.answer_question(path, state["query"], band_mapping=mapping)
    out["scene_profile"] = out.get("evidence", [{}])[0].get("data", {})
    return out


def grounding_node(state: OrchestratorState) -> None:
    asset = _optical_asset(state)
    paths = resolve_asset_paths(state["assets"])
    path = paths.get(asset.get("asset_id")) if asset else None
    if not path:
        raise RuntimeError("grounding: optical asset missing")
    mapping = state["agent_outputs"].get("input_validator", {}).get("mappings", {}).get(
        asset.get("asset_id"))
    out = grounding_agent.ground_objects(path, state["query"], band_mapping=mapping)
    return out


def change_node(state: OrchestratorState) -> None:
    paths = resolve_asset_paths(state["assets"])
    dated = sorted([a for a in state["assets"] if a.get("capture_date")],
                   key=lambda a: a["capture_date"])
    optical = [a for a in dated if a.get("sensor_type") != "sar"] or \
              [a for a in state["assets"] if a.get("sensor_type") != "sar"]
    if len(optical) < 2:
        raise RuntimeError("change_agent: needs two dated optical assets")
    before, after = optical[0], optical[-1]
    mappings = state["agent_outputs"].get("input_validator", {}).get("mappings", {})
    out_dir = artifact_store.job_artifact_dir(state["job_id"])
    out = change_agent.detect_change(
        paths[before["asset_id"]], paths[after["asset_id"]],
        band_mapping_before=mappings.get(before["asset_id"]),
        band_mapping_after=mappings.get(after["asset_id"]),
        out_dir=str(out_dir))
    for fname in ("change_mask.tif", "change_map.geojson"):
        if (out_dir / fname).exists():
            state["artifacts"].append({
                "type": "raster" if fname.endswith(".tif") else "geojson",
                "name": fname,
                "url": f"/artifacts/{state['job_id']}/{fname}"})
    state["uncertainty"].extend(out.get("uncertainty", []))
    return out


def change_vqa_node(state: OrchestratorState) -> None:
    paths = resolve_asset_paths(state["assets"])
    dated = sorted([a for a in state["assets"] if a.get("capture_date")],
                   key=lambda a: a["capture_date"])
    optical = [a for a in dated if a.get("sensor_type") != "sar"] or \
              [a for a in state["assets"] if a.get("sensor_type") != "sar"]
    if len(optical) < 2:
        raise RuntimeError("change_vqa: needs two dated optical assets")
    mappings = state["agent_outputs"].get("input_validator", {}).get("mappings", {})
    change_out = state["agent_outputs"].get("change_agent")
    if change_out and not change_out.get("failed"):
        change_result = change_out
    else:
        out_dir = artifact_store.job_artifact_dir(state["job_id"])
        change_result = change_agent.detect_change(
            paths[optical[0]["asset_id"]], paths[optical[-1]["asset_id"]],
            band_mapping_before=mappings.get(optical[0]["asset_id"]),
            band_mapping_after=mappings.get(optical[-1]["asset_id"]),
            out_dir=str(out_dir))
    grounding_out = state["agent_outputs"].get("grounding") or {}
    out = change_vqa_agent.answer_change_question(
        paths[optical[0]["asset_id"]], paths[optical[-1]["asset_id"]], state["query"],
        change_result=change_result,
        grounding_objects=grounding_out.get("objects") if not grounding_out.get("failed") else None)
    state["uncertainty"].extend(out.get("uncertainty", []))
    return out


def multimodal_node(state: OrchestratorState) -> None:
    paths = resolve_asset_paths(state["assets"])
    optical = _optical_asset(state)
    sar = _sar_asset(state)
    out = multimodal_agent.predict_multimodal(
        paths.get(optical["asset_id"]) if optical else None,
        paths.get(sar["asset_id"]) if sar else None)
    return out


def gis_code_node(state: OrchestratorState) -> None:
    paths = resolve_asset_paths(state["assets"])
    dated = sorted([a for a in state["assets"] if a.get("capture_date")],
                   key=lambda a: a["capture_date"])
    ordered = dated or state["assets"]
    n = len(ordered)
    intent = code_agent_mod.choose_intent(state["query"], n)
    if intent is None:
        raise RuntimeError("gis_code_agent: no resolvable analysis intent")
    mappings = state["agent_outputs"].get("input_validator", {}).get("mappings", {})
    # Sandbox contract: params reference basenames copied into input/.
    import os
    file_params = {}
    if n >= 2:
        file_params["optical_before"] = "input/" + os.path.basename(paths[ordered[0]["asset_id"]])
        file_params["optical_after"] = "input/" + os.path.basename(paths[ordered[-1]["asset_id"]])
    else:
        file_params["optical"] = "input/" + os.path.basename(paths[ordered[0]["asset_id"]])
    file_params["band_mapping"] = mappings.get(ordered[0]["asset_id"]) or {}
    file_params["threshold_pct"] = -20.0
    out = code_agent_mod.execute_analysis(
        intent, file_params, [paths[a["asset_id"]] for a in ordered],
        query=state["query"])
    if out["geojson"]:
        url = artifact_store.save_json(state["job_id"], out["geojson"], "analysis.geojson")
        state["artifacts"].append({"type": "geojson", "name": "analysis.geojson", "url": url})
    if not out["ok"]:
        out["uncertainty"] = [{
            "signal": "sandbox_execution_failed", "severity": "medium",
            "explanation": f"Sandboxed analysis did not produce a result: "
                           f"{out['sandbox_log'].get('stderr', '')[:200]}"}]
        state["agent_outputs"]["gis_code_agent"] = out  # keep code for AC4
        raise RuntimeError(f"sandbox_failed:{out['sandbox_log'].get('stderr', '')[:200]}")
    return out


def rag_node(state: OrchestratorState) -> dict:
    return rag_agent.retrieve(state["query"], k=3)



def evidence_aggregator_node(state: OrchestratorState) -> None:
    with traced(state["job_id"], "evidence_aggregator", "collect",
                sink=state["execution_trace"]):
        evidence: list[dict] = []
        for name, out in state["agent_outputs"].items():
            if not isinstance(out, dict) or out.get("failed"):
                continue
            for e in out.get("evidence", []) or []:
                evidence.append(e)
            if name == "rag" and out.get("passages"):
                evidence.append({
                    "agent": "rag", "type": "knowledge",
                    "summary": "; ".join(p["section"] or p["source"]
                                         for p in out["passages"]),
                    "data": out, "confidence": 0.9})
        state["evidence"] = evidence


def verifier_node(state: OrchestratorState) -> None:
    with traced(state["job_id"], "verifier", "compute_confidence",
                sink=state["execution_trace"]):
        val = state["agent_outputs"].get("input_validator", {})
        v = verifier_mod.compute(state["agent_outputs"], val, state.get("dates", []))
        state["confidence_breakdown"] = v["confidence_breakdown"]
        state["consistency_verdict"] = v["consistency_verdict"]
        state["uncertainty"].extend(v["uncertainty"])
        state["agent_outputs"]["verifier"] = {
            "confidence": v["final_confidence"],
            "evidence": [{"agent": "verifier", "type": "verdict",
                          "summary": v["consistency_verdict"],
                          "data": v["confidence_breakdown"],
                          "confidence": v["final_confidence"]}],
        }


MAX_MAP_FEATURES = 500


def composer_node(state: OrchestratorState) -> None:
    with traced(state["job_id"], "composer", "final_answer", sink=state["execution_trace"]):
        outputs = state["agent_outputs"]
        answer = None
        for key in ("change_vqa", "perception", "multimodal"):
            out = outputs.get(key) or {}
            if not out.get("failed") and out.get("answer"):
                answer = out["answer"]
                break
        if answer is None:
            parts = [e.get("summary") for e in state["evidence"] if e.get("summary")]
            answer = " ".join(str(p) for p in parts[:2]) or \
                "Analysis completed; no natural-language summary was produced."

        # location FeatureCollection: change polygons + grounded objects.
        features: list[dict] = []
        change_out = outputs.get("change_agent") or {}
        fc = change_out.get("change_geojson") or {}
        features.extend(fc.get("features", []))
        gout = outputs.get("grounding") or {}
        for o in (gout.get("objects") or []):
            if o.get("geometry_wgs84"):
                features.append({"type": "Feature",
                                 "properties": {"class_label": o["class_label"],
                                                "confidence": o["confidence"],
                                                "kind": "detection"},
                                 "geometry": o["geometry_wgs84"]})
        code_agent_out = outputs.get("gis_code_agent") or {}
        if code_agent_out.get("generated_code"):
            features.extend((code_agent_out.get("geojson") or {}).get("features", []))

        # Enrich answer with operational SOP guidance if matched
        rag_sops = (outputs.get("rag") or {}).get("sops", [])
        if rag_sops:
            top_sop = rag_sops[0]
            action_text = "; ".join(top_sop["action_protocols"][:2])
            answer += f"\n\nOperational Guidance ({top_sop['authority']} - {top_sop['sop_id']}): {action_text}"

        display = {"gis_code": "gis_code_agent"}.get
        result = {
            "job_id": state["job_id"],
            "answer": answer,
            "confidence": (outputs.get("verifier") or {}).get("confidence", 0.5),
            "confidence_breakdown": state.get("confidence_breakdown", {}),
            "consistency_verdict": state.get("consistency_verdict", "PARTIALLY_CONSISTENT"),
            "artifacts": state["artifacts"],
            "agents_used": ["orchestrator", "input_validator"]
                           + [display(n, n) for n in state["plan"]] + ["verifier"],
            "plan_rationale": state.get("plan_rationale", {}),
            "generated_code": code_agent_out.get("generated_code", []),
            "uncertainty": state["uncertainty"],
            "location": {"type": "FeatureCollection", "features": features[:MAX_MAP_FEATURES]},
            "evidence": state["evidence"],
            "rag_sops": rag_sops,
            "execution_trace": state["execution_trace"],
        }
        state["final"] = result



# ---------------------------------------------------------------- graph ----

def build_graph() -> Graph:
    g = Graph("satquery_orchestrator")
    g.add_node("planner", planner_node)
    g.add_node("input_validator", _agent_node("input_validator", input_validator_node))
    g.add_node("perception", _agent_node("perception", perception_node))
    g.add_node("grounding", _agent_node("grounding", grounding_node))
    g.add_node("change_agent", _agent_node("change_agent", change_node))
    g.add_node("change_vqa", _agent_node("change_vqa", change_vqa_node))
    g.add_node("multimodal", _agent_node("multimodal", multimodal_node))
    g.add_node("gis_code", _agent_node("gis_code_agent", gis_code_node))
    g.add_node("rag", _agent_node("rag", rag_node))
    g.add_node("evidence_aggregator", evidence_aggregator_node)
    g.add_node("verifier", verifier_node)
    g.add_node("composer", composer_node)

    g.set_entry("planner")
    g.add_edge("planner", "input_validator")
    g.add_router("input_validator", lambda s: [n for n in s["plan"] if n in g.nodes])
    for specialist in ("perception", "grounding", "change_agent", "change_vqa",
                       "multimodal", "gis_code", "rag"):
        g.add_edge(specialist, "evidence_aggregator")
    g.add_edge("evidence_aggregator", "verifier")
    g.add_edge("verifier", "composer")
    return g


GRAPH = build_graph()


def run_query(request: dict) -> dict:
    """Synchronous orchestration for one job. Returns the final result payload."""
    state: OrchestratorState = {
        "job_id": request["job_id"],
        "query": request.get("question", ""),
        "region": request.get("region"),
        "dates": [],
        "assets": request.get("assets", []),
        "plan": [],
        "plan_rationale": {},
        "agent_outputs": {},
        "artifacts": [],
        "evidence": [],
        "confidence_breakdown": {},
        "uncertainty": [],
        "consistency_verdict": "PARTIALLY_CONSISTENT",
        "execution_trace": [],
        "status": "running",
        "error": None,
        "final": {},
    }
    job_store.set_status(request["job_id"], "running", progress=5)
    try:
        GRAPH.run(state)
        final = state["final"]
        final["execution_trace"] = state["execution_trace"]
        job_store.set_result(request["job_id"], final)
        return final
    except Exception as exc:  # job-level failure (e.g., all assets invalid)
        log.exception("job %s failed", request["job_id"])
        job_store.fail_job(request["job_id"], str(exc))
        raise
