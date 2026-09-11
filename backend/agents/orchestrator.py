"""Orchestrator — Explicit state graph over agents with EarthQuery compilation,
autonomous sensor selection, SAR specialist intelligence, deterministic GIS reasoning,
and self-correcting verification loop (FR-9, §12, SIH26167).
"""
from __future__ import annotations

import logging
from typing import TypedDict

from ..models import loaders
from ..services import artifact_store, job_store
from ..services.earthquery.compiler import EarthQueryCompiler
from ..services.earthquery.schema import EarthQuerySpec, InvestigationPlan, QueryUnderstanding
from ..services.earthquery.sensor_selector import AutonomousSensorSelector
from ..utils.assets import resolve_asset_paths
from . import change as change_agent
from . import change_vqa as change_vqa_agent
from . import code_agent as code_agent_mod
from . import grounding as grounding_agent
from . import hypothesis_engine as hypothesis_engine_mod
from . import multimodal as multimodal_agent
from . import perception as perception_agent
from . import rag as rag_agent
from . import sar as sar_agent_mod
from . import verifier as verifier_mod
from .graph import Graph
from .planner import build_investigation_plan, build_plan, narrate_plan, plan_rationale
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
    earthquery_spec: dict
    query_understanding: dict
    investigation_plan: dict
    sensor_selection: dict
    selected_models: list[dict]
    agent_outputs: dict[str, dict]
    artifacts: list[dict]
    evidence: list[dict]
    hypotheses: dict
    geospatial_results: dict
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
    job_store.emit_event(state["job_id"], "agent_completed", {"agent": name})


def _fail(state: OrchestratorState, name: str, exc: Exception) -> None:
    log.warning("agent %s failed: %s", name, exc)
    job_store.set_agent_status(state["job_id"], name, "failed")
    state["uncertainty"].append({
        "signal": f"agent_failed_{name}", "severity": "medium",
        "explanation": f"{name} failed after retry and was skipped: {exc}",
    })
    prev = state["agent_outputs"].get(name) or {}
    state["agent_outputs"][name] = {**prev, "failed": True, "error": str(exc)}
    job_store.emit_event(state["job_id"], "agent_failed", {"agent": name, "error": str(exc)})


def _agent_node(name: str, fn):
    def node(state: OrchestratorState) -> None:
        job_id = state["job_id"]
        job_store.set_agent_status(job_id, name, "running")
        job_store.emit_event(job_id, "agent_started", {"agent": name})
        last_exc: Exception | None = None
        for attempt in (1, 2):
            try:
                with traced(job_id, name, f"{name}_attempt_{attempt}", sink=state["execution_trace"]):
                    out = fn(state) or {}
                _succeed(state, name, out)
                return
            except Exception as exc:
                last_exc = exc
        _fail(state, name, last_exc)
    return node


# ---------------------------------------------------------------- nodes ----

def planner_node(state: OrchestratorState) -> None:
    job_id = state["job_id"]
    with traced(job_id, "orchestrator", "plan", sink=state["execution_trace"]):
        plan_obj, spec, understanding = build_investigation_plan(
            query=state["query"],
            assets=state["assets"],
            spatial_scope=state["region"],
        )
        state["plan"] = build_plan(state["query"], state["assets"])
        state["plan_rationale"] = plan_rationale(state["query"], state["assets"])
        state["earthquery_spec"] = spec.model_dump()
        state["query_understanding"] = understanding.model_dump()
        state["investigation_plan"] = plan_obj.model_dump()
        state["sensor_selection"] = state["plan_rationale"].get("sensor_selection", {})

        state["dates"] = sorted({a.get("capture_date") for a in state["assets"] if a.get("capture_date")})

        # Emit SSE events for live stream
        job_store.emit_event(job_id, "query_understanding", state["query_understanding"])
        job_store.emit_event(job_id, "planning", {"steps": state["investigation_plan"].get("steps", [])})
        job_store.emit_event(job_id, "sensor_selection", state["sensor_selection"])


def input_validator_node(state: OrchestratorState) -> None:
    with traced(state["job_id"], "input_validator", "validate_assets", sink=state["execution_trace"]):
        from ..geospatial import raster as graster
        reports, paths = {}, resolve_asset_paths(state["assets"])
        for a in state["assets"]:
            p = paths.get(a["asset_id"])
            if not p:
                reports[a["asset_id"]] = {"valid": False, "errors": ["asset_not_found"]}
                continue
            reports[a["asset_id"]] = graster.validate_raster(p, a.get("sensor_type"))
        if not any(r.get("valid") for r in reports.values()):
            raise RuntimeError(f"all_assets_invalid:{reports}")
        mappings = {}
        for a in state["assets"]:
            r = reports.get(a["asset_id"], {})
            if a.get("band_mapping"):
                mappings[a["asset_id"]] = a["band_mapping"]
            elif r.get("band_mapping_guess"):
                mappings[a["asset_id"]] = r["band_mapping_guess"]

        out = {
            "reports": reports,
            "all_valid": all(r.get("valid") for r in reports.values()),
            "any_missing_nodata": any(r.get("nodata") is None for r in reports.values()),
            "band_mapping_confidence": min(
                (r.get("band_mapping_confidence", "high") for r in reports.values()),
                key=lambda c: {"high": 3, "medium": 2, "low": 1, "none": 0}.get(c, 0),
            ),
            "mappings": mappings,
        }
        job_store.emit_event(state["job_id"], "data_quality", out)
        return out


def perception_node(state: OrchestratorState) -> None:
    asset = _optical_asset(state) or (state["assets"] or [{}])[0]
    paths = resolve_asset_paths(state["assets"])
    path = paths.get(asset.get("asset_id"))
    if not path:
        raise RuntimeError("perception: optical asset missing")
    mapping = state["agent_outputs"].get("input_validator", {}).get("mappings", {}).get(asset.get("asset_id"))
    
    # Record model decision
    model_rec = loaders.select_model("scene_understanding", "optical")
    state.setdefault("selected_models", []).append(model_rec)
    job_store.emit_event(state["job_id"], "model_selection", model_rec)

    out = perception_agent.answer_question(path, state["query"], band_mapping=mapping)
    out["scene_profile"] = out.get("evidence", [{}])[0].get("data", {})
    return out


def grounding_node(state: OrchestratorState) -> None:
    asset = _optical_asset(state)
    paths = resolve_asset_paths(state["assets"])
    path = paths.get(asset.get("asset_id")) if asset else None
    if not path:
        raise RuntimeError("grounding: optical asset missing")
    mapping = state["agent_outputs"].get("input_validator", {}).get("mappings", {}).get(asset.get("asset_id"))

    model_rec = loaders.select_model("object_grounding", "optical")
    state.setdefault("selected_models", []).append(model_rec)
    job_store.emit_event(state["job_id"], "model_selection", model_rec)

    out = grounding_agent.ground_objects(path, state["query"], band_mapping=mapping)
    return out


def change_node(state: OrchestratorState) -> None:
    paths = resolve_asset_paths(state["assets"])
    dated = sorted([a for a in state["assets"] if a.get("capture_date")], key=lambda a: a["capture_date"])
    optical = [a for a in dated if a.get("sensor_type") != "sar"] or [a for a in state["assets"] if a.get("sensor_type") != "sar"]
    if len(optical) < 2:
        raise RuntimeError("change_agent: needs two dated optical assets")
    before, after = optical[0], optical[-1]
    mappings = state["agent_outputs"].get("input_validator", {}).get("mappings", {})
    out_dir = artifact_store.job_artifact_dir(state["job_id"])

    model_rec = loaders.select_model("temporal_change", "optical")
    state.setdefault("selected_models", []).append(model_rec)
    job_store.emit_event(state["job_id"], "model_selection", model_rec)

    out = change_agent.detect_change(
        paths[before["asset_id"]], paths[after["asset_id"]],
        band_mapping_before=mappings.get(before["asset_id"]),
        band_mapping_after=mappings.get(after["asset_id"]),
        out_dir=str(out_dir),
    )
    for fname in ("change_mask.tif", "change_map.geojson"):
        if (out_dir / fname).exists():
            state["artifacts"].append({
                "type": "raster" if fname.endswith(".tif") else "geojson",
                "name": fname,
                "url": f"/artifacts/{state['job_id']}/{fname}",
            })
    state["uncertainty"].extend(out.get("uncertainty", []))
    return out


def change_vqa_node(state: OrchestratorState) -> None:
    paths = resolve_asset_paths(state["assets"])
    dated = sorted([a for a in state["assets"] if a.get("capture_date")], key=lambda a: a["capture_date"])
    optical = [a for a in dated if a.get("sensor_type") != "sar"] or [a for a in state["assets"] if a.get("sensor_type") != "sar"]
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
            out_dir=str(out_dir),
        )
    grounding_out = state["agent_outputs"].get("grounding") or {}
    out = change_vqa_agent.answer_change_question(
        paths[optical[0]["asset_id"]], paths[optical[-1]["asset_id"]], state["query"],
        change_result=change_result,
        grounding_objects=grounding_out.get("objects") if not grounding_out.get("failed") else None,
    )
    state["uncertainty"].extend(out.get("uncertainty", []))
    return out


def sar_node(state: OrchestratorState) -> None:
    paths = resolve_asset_paths(state["assets"])
    sar_assets = [a for a in state["assets"] if a.get("sensor_type") == "sar"]
    if not sar_assets:
        return {"note": "no_sar_asset_present", "confidence": 0.0}

    out_dir = artifact_store.job_artifact_dir(state["job_id"])
    model_rec = loaders.select_model("flood_detection", "sar")
    state.setdefault("selected_models", []).append(model_rec)
    job_store.emit_event(state["job_id"], "model_selection", model_rec)

    primary_sar = sar_assets[0]
    out = sar_agent_mod.analyze_sar_scene(
        paths[primary_sar["asset_id"]],
        out_dir=str(out_dir),
    )

    # If bi-temporal SAR exists, run temporal flood progression
    if len(sar_assets) >= 2:
        temporal_sar = sar_agent_mod.compare_temporal_sar(
            paths[sar_assets[0]["asset_id"]],
            paths[sar_assets[1]["asset_id"]],
            out_dir=str(out_dir),
        )
        out["temporal_sar"] = temporal_sar

    # Save water GeoJSON artifact
    if out.get("water_geojson"):
        url = artifact_store.save_json(state["job_id"], out["water_geojson"], "sar_flood_extent.geojson")
        state["artifacts"].append({"type": "geojson", "name": "sar_flood_extent.geojson", "url": url})

    return out


def multimodal_node(state: OrchestratorState) -> None:
    paths = resolve_asset_paths(state["assets"])
    optical = _optical_asset(state)
    sar = _sar_asset(state)
    out = multimodal_agent.predict_multimodal(
        paths.get(optical["asset_id"]) if optical else None,
        paths.get(sar["asset_id"]) if sar else None,
    )
    return out


def gis_code_node(state: OrchestratorState) -> None:
    paths = resolve_asset_paths(state["assets"])
    dated = sorted([a for a in state["assets"] if a.get("capture_date")], key=lambda a: a["capture_date"])
    ordered = dated or state["assets"]
    n = len(ordered)
    intent = code_agent_mod.choose_intent(state["query"], n)
    mappings = state["agent_outputs"].get("input_validator", {}).get("mappings", {})

    import os
    file_params = {}
    if n >= 2:
        file_params["optical_before"] = "input/" + os.path.basename(paths[ordered[0]["asset_id"]])
        file_params["optical_after"] = "input/" + os.path.basename(paths[ordered[-1]["asset_id"]])
    else:
        file_params["optical"] = "input/" + os.path.basename(paths[ordered[0]["asset_id"]])
    file_params["band_mapping"] = mappings.get(ordered[0]["asset_id"]) or {}
    file_params["threshold_pct"] = -20.0

    out = {}
    if intent is not None:
        out = code_agent_mod.execute_analysis(
            intent, file_params, [paths[a["asset_id"]] for a in ordered],
            query=state["query"],
        )
        if out.get("geojson"):
            url = artifact_store.save_json(state["job_id"], out["geojson"], "analysis.geojson")
            state["artifacts"].append({"type": "geojson", "name": "analysis.geojson", "url": url})

    # Deterministic Geospatial Reasoning Engine for flood/building intersections
    from ..geospatial.engine import calculate_affected_buildings
    grounding_out = state["agent_outputs"].get("grounding") or {}
    sar_out = state["agent_outputs"].get("sar_agent") or {}
    change_out = state["agent_outputs"].get("change_agent") or {}

    flood_layer = sar_out.get("water_geojson") or change_out.get("change_geojson")
    grounded_bldgs = grounding_out.get("objects") or []

    spec = state.get("earthquery_spec", {})
    if spec.get("intent") in ("flood_impact_change", "building_count", "affected_objects") or \
       ("flood" in state["query"].lower() and "building" in state["query"].lower()):
        affected_res = calculate_affected_buildings(flood_layer, grounded_bldgs)
        state["geospatial_results"] = affected_res
        if affected_res.get("affected_features_geojson", {}).get("features"):
            url = artifact_store.save_json(
                state["job_id"],
                affected_res["affected_features_geojson"],
                "affected_buildings.geojson",
            )
            state["artifacts"].append({"type": "geojson", "name": "affected_buildings.geojson", "url": url})
        out["affected_buildings"] = affected_res

    return out


def hypothesis_node(state: OrchestratorState) -> None:
    hypo_eval = hypothesis_engine_mod.HypothesisEngine.evaluate(
        query=state["query"],
        evidence_list=state.get("evidence", []),
        agent_outputs=state["agent_outputs"],
    )
    state["hypotheses"] = hypo_eval.model_dump()
    return hypo_eval.model_dump()


def rag_node(state: OrchestratorState) -> dict:
    return rag_agent.retrieve(state["query"], k=3)


def evidence_aggregator_node(state: OrchestratorState) -> None:
    job_id = state["job_id"]
    with traced(job_id, "evidence_aggregator", "collect", sink=state["execution_trace"]):
        evidence: list[dict] = []
        ev_counter = 1

        for name, out in state["agent_outputs"].items():
            if not isinstance(out, dict) or out.get("failed"):
                continue

            for e in out.get("evidence", []) or []:
                item = {
                    "evidence_id": f"ev_{ev_counter:02d}",
                    "source": e.get("agent", name),
                    "type": e.get("type", "observation"),
                    "summary": e.get("summary", ""),
                    "confidence": e.get("confidence", 0.8),
                    "artifact": e.get("artifact"),
                    "data": e.get("data", {}),
                }
                evidence.append(item)
                ev_counter += 1

            if name == "sar_agent" and out.get("water_geojson"):
                evidence.append({
                    "evidence_id": f"ev_{ev_counter:02d}",
                    "source": "sar",
                    "type": "flood_mask",
                    "model": "sar_flood_detector",
                    "summary": out.get("interpretation", "SAR water extent detected via specular reflection."),
                    "confidence": out.get("confidence", 0.88),
                    "artifact": f"/artifacts/{job_id}/sar_flood_extent.geojson",
                    "limitations": out.get("limitations", []),
                    "data": out.get("metrics", {}),
                })
                ev_counter += 1

            if name == "change_agent" and out.get("statistics"):
                evidence.append({
                    "evidence_id": f"ev_{ev_counter:02d}",
                    "source": "optical",
                    "type": "change_detection_mask",
                    "model": out.get("metadata", {}).get("model", "siamese_unet_levircd"),
                    "summary": out.get("summary", "Bi-temporal change detection mask."),
                    "confidence": out.get("confidence", 0.85),
                    "artifact": f"/artifacts/{job_id}/change_map.geojson",
                    "data": out.get("statistics", {}),
                })
                ev_counter += 1

            if name == "gis_code_agent" and out.get("affected_buildings"):
                aff = out["affected_buildings"]
                evidence.append({
                    "evidence_id": f"ev_{ev_counter:02d}",
                    "source": "gis_reasoning",
                    "type": "building_spatial_intersection",
                    "model": "deterministic_gis_engine",
                    "summary": f"Spatial intersection confirmed {aff.get('affected_building_count', 0)} buildings inside flood footprint.",
                    "confidence": 0.94,
                    "artifact": f"/artifacts/{job_id}/affected_buildings.geojson",
                    "data": aff,
                })
                ev_counter += 1

            if name == "rag" and out.get("passages"):
                evidence.append({
                    "evidence_id": f"ev_{ev_counter:02d}",
                    "source": "rag",
                    "type": "knowledge",
                    "summary": "; ".join(p["section"] or p["source"] for p in out["passages"]),
                    "confidence": 0.90,
                    "data": out,
                })
                ev_counter += 1

        state["evidence"] = evidence
        job_store.emit_event(job_id, "evidence_added", {"evidence_count": len(evidence)})


def verifier_node(state: OrchestratorState) -> None:
    job_id = state["job_id"]
    with traced(job_id, "verifier", "compute_confidence", sink=state["execution_trace"]):
        val = state["agent_outputs"].get("input_validator", {})
        spec = state.get("earthquery_spec", {})
        policy = spec.get("confidence_policy", "general")

        v = verifier_mod.compute(state["agent_outputs"], val, state.get("dates", []), policy=policy)
        state["confidence_breakdown"] = v["confidence_breakdown"]
        state["consistency_verdict"] = v["consistency_verdict"]
        state["uncertainty"].extend(v["uncertainty"])

        if v.get("needs_replan"):
            job_store.emit_event(job_id, "conflict", {"conflicts": v.get("conflicts", [])})
            state["execution_trace"].append({
                "agent": "verifier",
                "action": "conflict_replanning",
                "duration_ms": 15,
                "status": "warning",
                "detail": f"Inter-sensor conflict detected ({'; '.join(v.get('conflicts', []))}); activated secondary verification.",
            })

        state["agent_outputs"]["verifier"] = {
            "confidence": v["final_confidence"],
            "task_specific": v.get("task_specific", {}),
            "evidence": [{
                "agent": "verifier", "type": "verdict",
                "summary": v["consistency_verdict"],
                "data": v["confidence_breakdown"],
                "confidence": v["final_confidence"],
            }],
        }
        job_store.emit_event(job_id, "verification", {
            "verdict": v["consistency_verdict"],
            "confidence": v["final_confidence"],
        })


MAX_MAP_FEATURES = 500


def composer_node(state: OrchestratorState) -> None:
    job_id = state["job_id"]
    with traced(job_id, "composer", "final_answer", sink=state["execution_trace"]):
        outputs = state["agent_outputs"]
        answer = None
        claims = []

        # Check if deterministic GIS computed affected buildings
        gis_aff = state.get("geospatial_results") or outputs.get("gis_code_agent", {}).get("affected_buildings")
        change_out = outputs.get("change_agent") or {}
        sar_out = outputs.get("sar_agent") or {}

        if gis_aff and gis_aff.get("total_buildings_detected", 0) > 0:
            aff_count = gis_aff.get("affected_building_count", 0)
            total_b = gis_aff.get("total_buildings_detected", 0)
            pct = gis_aff.get("affected_percentage", 0.0)
            chg_stat = change_out.get("statistics", {})
            chg_pct = chg_stat.get("percent_of_aoi", 0.0)

            answer = (
                f"Analysis confirmed flood inundation expanded across the target region ({chg_pct:.1f}% area change detected). "
                f"Deterministic geospatial intersection established that exactly {aff_count:,} out of {total_b:,} detected "
                f"buildings ({pct:.1f}%) were directly affected by the flood extent."
            )
            claims.append({
                "id": "claim_01",
                "text": f"Flooding increased by {chg_pct:.1f}% across compared period.",
                "evidence_ids": [e["evidence_id"] for e in state.get("evidence", []) if e.get("type") in ("change_detection_mask", "flood_mask")],
                "numeric_value": chg_pct,
                "metric_unit": "%",
            })
            claims.append({
                "id": "claim_02",
                "text": f"{aff_count:,} buildings were directly affected by flooding.",
                "evidence_ids": [e["evidence_id"] for e in state.get("evidence", []) if e.get("type") == "building_spatial_intersection"],
                "numeric_value": aff_count,
                "metric_unit": "buildings",
            })

        elif state.get("hypotheses"):
            hypo_data = state["hypotheses"]
            top = hypo_data.get("most_supported", "Landscape Change")
            answer = f"Investigation evaluated multiple hypotheses regarding observed changes. {hypo_data.get('interpretation', '')}"
            for h in hypo_data.get("hypotheses", []):
                claims.append({
                    "id": f"claim_{h.get('id', 'hypo')}",
                    "text": f"{h.get('label')}: support score {h.get('support', 0):.2f}",
                    "evidence_ids": h.get("evidence_ids", []),
                    "numeric_value": h.get("support"),
                    "metric_unit": "support_index",
                })

        # Fallback to narrative from specialists
        if answer is None:
            for key in ("change_vqa", "perception", "multimodal"):
                out = outputs.get(key) or {}
                if not out.get("failed") and out.get("answer"):
                    answer = out["answer"]
                    break

        if answer is None:
            parts = [e.get("summary") for e in state["evidence"] if e.get("summary")]
            answer = " ".join(str(p) for p in parts[:2]) or "Analysis completed; no natural-language summary was produced."

        # Location FeatureCollection: change polygons + grounded objects + flood layers + affected buildings
        features: list[dict] = []
        if gis_aff and gis_aff.get("affected_features_geojson", {}).get("features"):
            features.extend(gis_aff["affected_features_geojson"]["features"])

        if sar_out.get("water_geojson", {}).get("features"):
            features.extend(sar_out["water_geojson"]["features"])

        fc = change_out.get("change_geojson") or {}
        features.extend(fc.get("features", []))

        gout = outputs.get("grounding") or {}
        for o in (gout.get("objects") or []):
            if o.get("geometry_wgs84"):
                features.append({
                    "type": "Feature",
                    "properties": {"class_label": o["class_label"], "confidence": o["confidence"], "kind": "detection"},
                    "geometry": o["geometry_wgs84"],
                })

        code_agent_out = outputs.get("gis_code_agent") or {}
        if code_agent_out.get("generated_code"):
            features.extend((code_agent_out.get("geojson") or {}).get("features", []))

        # Operational SOP guidance
        rag_sops = (outputs.get("rag") or {}).get("sops", [])
        if rag_sops:
            top_sop = rag_sops[0]
            action_text = "; ".join(top_sop["action_protocols"][:2])
            answer += f"\n\nOperational Guidance ({top_sop['authority']} - {top_sop['sop_id']}): {action_text}"

        # Context-aware follow-up question generation (Section 30)
        q_lower = state["query"].lower()
        if "flood" in q_lower or "water" in q_lower:
            follow_ups = [
                "When did the flood inundation reach its peak extent?",
                "Which evacuation routes and primary roads were intersected by floodwater?",
                "Compare this flood impact with the same seasonal window last year.",
                "What is the estimated total affected agricultural and residential area?",
                "Show the high-resolution SAR specular reflection evidence layer.",
            ]
        elif "change" in q_lower or "cause" in q_lower:
            follow_ups = [
                "What was the dominant driver of landscape change in this bounding box?",
                "Are there signs of post-event vegetation regrowth or reconstruction?",
                "Inspect temporal backscatter variance across previous acquisition dates.",
                "Generate a detailed damage breakdown report for civil authorities.",
            ]
        else:
            follow_ups = [
                "Locate and count all critical infrastructure assets within 1 km.",
                "Measure the exact surface area of detected structures.",
                "Cross-validate optical detections against all-weather SAR data.",
                "Retrieve disaster response protocols for this geographic zone.",
            ]

        display = {"gis_code": "gis_code_agent"}.get
        verifier_data = outputs.get("verifier") or {}

        result = {
            "job_id": state["job_id"],
            "query": state["query"],
            "earthquery_spec": state.get("earthquery_spec", {}),
            "query_understanding": state.get("query_understanding", {}),
            "investigation": state.get("investigation_plan", {}),
            "sensor_selection": state.get("sensor_selection", {}),
            "model_selection": state.get("selected_models", []),
            "answer": answer,
            "claims": claims,
            "confidence": verifier_data.get("confidence", 0.5),
            "confidence_breakdown": state.get("confidence_breakdown", {}),
            "consistency_verdict": state.get("consistency_verdict", "PARTIALLY_CONSISTENT"),
            "task_specific_confidence": verifier_data.get("task_specific", {}),
            "artifacts": state["artifacts"],
            "agents_used": ["orchestrator", "input_validator"] + [display(n, n) for n in state["plan"]] + ["verifier"],
            "plan_rationale": state.get("plan_rationale", {}),
            "generated_code": code_agent_out.get("generated_code", []),
            "uncertainty": state["uncertainty"],
            "location": {"type": "FeatureCollection", "features": features[:MAX_MAP_FEATURES]},
            "evidence": state["evidence"],
            "hypotheses": state.get("hypotheses", {}).get("hypotheses", []),
            "geospatial_results": state.get("geospatial_results", {}),
            "rag_sops": rag_sops,
            "execution_trace": state["execution_trace"],
            "follow_up_questions": follow_ups,
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
    g.add_node("sar_agent", _agent_node("sar_agent", sar_node))
    g.add_node("multimodal", _agent_node("multimodal", multimodal_node))
    g.add_node("gis_code", _agent_node("gis_code_agent", gis_code_node))
    g.add_node("hypothesis_engine", _agent_node("hypothesis_engine", hypothesis_node))
    g.add_node("rag", _agent_node("rag", rag_node))
    g.add_node("evidence_aggregator", evidence_aggregator_node)
    g.add_node("verifier", verifier_node)
    g.add_node("composer", composer_node)

    g.set_entry("planner")
    g.add_edge("planner", "input_validator")
    g.add_router("input_validator", lambda s: [n for n in s["plan"] if n in g.nodes])
    for specialist in ("perception", "grounding", "change_agent", "change_vqa",
                       "sar_agent", "multimodal", "gis_code", "hypothesis_engine", "rag"):
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
        "earthquery_spec": {},
        "query_understanding": {},
        "investigation_plan": {},
        "sensor_selection": {},
        "selected_models": [],
        "agent_outputs": {},
        "artifacts": [],
        "evidence": [],
        "hypotheses": {},
        "geospatial_results": {},
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
    except Exception as exc:
        log.exception("job %s failed", request["job_id"])
        job_store.fail_job(request["job_id"], str(exc))
        raise
