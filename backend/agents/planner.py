"""Deterministic planner — implements the §12.2 branch-selection rules (FR-9 AC2).

Same query → same plan, always: keyword rules first; no LLM in the
plan-selection path itself, so demos cannot be flaky. `build_plan()` and
`plan_rationale()` are pure/deterministic and unchanged. `narrate_plan()` is
a separate, optional enhancement: it turns the already-decided plan into a
one-sentence human explanation via xAI when `XAI_API_KEY` is configured.
It never influences which agents run — only the text shown to the user.
"""
from __future__ import annotations

from ..services.earthquery.compiler import EarthQueryCompiler
from ..services.earthquery.schema import EarthQuerySpec, InvestigationPlan, InvestigationStep, QueryUnderstanding
from ..services.earthquery.sensor_selector import AutonomousSensorSelector
from ..services import llm_client

_LLM_SYSTEM_PROMPT = (
    "You explain, in one plain sentence, why a fixed list of analysis "
    "agents was chosen for a satellite-imagery question. You are given the "
    "already-decided agent list and the rule-based rationale that produced "
    "it. Do not suggest a different plan or add agents not listed."
)


def _dates(assets: list[dict]) -> list[str]:
    return sorted({a.get("capture_date") for a in assets if a.get("capture_date")})


def _sensors(assets: list[dict]) -> set[str]:
    return {a.get("sensor_type", "optical") for a in assets}


def build_investigation_plan(
    query: str,
    assets: list[dict],
    spatial_scope: dict | None = None,
    cloud_fraction: float = 0.0,
) -> tuple[InvestigationPlan, EarthQuerySpec, QueryUnderstanding]:
    """Generates an explicit, machine-observable Investigation Plan using EarthQuery."""
    spec, understanding = EarthQueryCompiler.compile(
        query=query,
        spatial_scope=spatial_scope,
        asset_metadata=assets,
    )
    sensor_decision = AutonomousSensorSelector.select_sensors(
        spec=spec,
        assets=assets,
        cloud_contamination_optical=cloud_fraction,
    )

    steps: list[InvestigationStep] = []
    step_num = 1

    # Step 1: Input Validation / Quality
    steps.append(
        InvestigationStep(
            id=f"step_{step_num}",
            name="Data Quality & Integrity Assessment",
            type="data_quality_check",
            agent="input_validator",
            status="pending",
            summary="Validate raster dimensions, nodata values, spatial CRS, and band mapping integrity.",
            dependencies=[],
        )
    )
    step_num += 1

    # Step 2: Primary Perception / Context
    if "optical" in sensor_decision.selected:
        steps.append(
            InvestigationStep(
                id=f"step_{step_num}",
                name="Optical Scene Perception & Context",
                type="scene_perception",
                agent="perception",
                modality="optical",
                status="pending",
                summary="Compute scene profile, spectral reflectance, and optical VQA grounding.",
                dependencies=[f"step_{step_num-1}"],
            )
        )
        step_num += 1

    # Step 3: Temporal / Change Analysis if applicable
    dates = _dates(assets)
    if spec.temporal.enabled or len(dates) >= 2 or "temporal_comparison" in spec.required_operations:
        steps.append(
            InvestigationStep(
                id=f"step_{step_num}",
                name="Bi-temporal Change Detection",
                type="change_detection",
                agent="change_agent",
                modality="optical",
                status="pending",
                summary="Execute bi-temporal coregistration, Siamese U-Net or index-delta change inference.",
                dependencies=[f"step_1"],
            )
        )
        step_num += 1
        steps.append(
            InvestigationStep(
                id=f"step_{step_num}",
                name="Temporal VQA Narrative Reasoning",
                type="temporal_vqa",
                agent="change_vqa",
                modality="optical",
                status="pending",
                summary="Synthesize visual change trajectory and bi-temporal phenomenon narrative.",
                dependencies=[f"step_{step_num-1}"],
            )
        )
        step_num += 1

    # Step 4: SAR Analysis if selected
    if "sar" in sensor_decision.selected or "sar" in _sensors(assets):
        steps.append(
            InvestigationStep(
                id=f"step_{step_num}",
                name="SAR Polarimetric & Roughness Analysis",
                type="sar_analysis",
                agent="sar_agent",
                modality="sar",
                status="pending",
                summary="Analyze VV/VH backscatter, evaluate specular water reflectance, and estimate ENL quality.",
                dependencies=[f"step_1"],
            )
        )
        step_num += 1

    # Step 5: Grounding / Object Detection
    if any(op in spec.required_operations for op in ("building_detection", "object_detection")) or \
       spec.intent in ("building_count", "object_grounding", "flood_impact_change"):
        steps.append(
            InvestigationStep(
                id=f"step_{step_num}",
                name="Zero-Shot Object Grounding",
                type="object_grounding",
                agent="grounding",
                modality="optical",
                status="pending",
                summary="Detect target object categories and vectorize footprint polygons.",
                dependencies=[f"step_1"],
            )
        )
        step_num += 1

    # Step 6: Multimodal Fusion
    if "optical" in sensor_decision.selected and "sar" in sensor_decision.selected:
        steps.append(
            InvestigationStep(
                id=f"step_{step_num}",
                name="Multimodal Optical-SAR Fusion",
                type="multimodal_fusion",
                agent="multimodal",
                status="pending",
                summary="Cross-validate optical reflectance against SAR backscatter to compute sensor agreement.",
                dependencies=["step_1"],
            )
        )
        step_num += 1

    # Step 7: GIS Spatial Reasoning
    if spec.requires_gis or "spatial_intersection" in spec.required_operations or spec.requires_numeric_result:
        steps.append(
            InvestigationStep(
                id=f"step_{step_num}",
                name="Deterministic Geospatial Reasoning & Intersection",
                type="spatial_intersection",
                agent="gis_code_agent",
                status="pending",
                summary="Execute sandboxed GIS computation (polygon intersection, buffer, area, or counts).",
                dependencies=[s.id for s in steps if s.type in ("change_detection", "object_grounding", "sar_analysis")],
            )
        )
        step_num += 1

    # Step 8: Hypothesis Engine (if investigative)
    if spec.intent in ("hypothesis_investigation", "change_explanation"):
        steps.append(
            InvestigationStep(
                id=f"step_{step_num}",
                name="Hypothesis Generation & Evidence Evaluation",
                type="hypothesis_evaluation",
                agent="hypothesis_engine",
                status="pending",
                summary="Generate causal hypotheses (flood, urban, vegetation, artifact) and score against collected evidence.",
                dependencies=[s.id for s in steps if s.id != f"step_{step_num}"],
            )
        )
        step_num += 1

    # Step 9: Domain Knowledge RAG
    steps.append(
        InvestigationStep(
            id=f"step_{step_num}",
            name="Operational Protocol & SOP Retrieval",
            type="rag_retrieval",
            agent="rag",
            status="pending",
            summary="Retrieve authoritative disaster management, remote sensing, and SOP protocols.",
            dependencies=[],
        )
    )
    step_num += 1

    # Step 10: Verification & Conflict Detection
    steps.append(
        InvestigationStep(
            id=f"step_{step_num}",
            name="Multimodal Evidence Verification",
            type="verification",
            agent="verifier",
            status="pending",
            summary="Check inter-model consistency, compute task-specific confidence, and flag evidence conflicts.",
            dependencies=[s.id for s in steps[:-1]],
        )
    )

    plan = InvestigationPlan(
        investigation_id=f"inv_{id(spec)}",
        mode="investigate" if len(steps) > 4 else "ask",
        steps=steps,
        sensor_selection=sensor_decision,
        query_understanding=understanding,
    )
    return plan, spec, understanding


def build_plan(query: str, assets: list[dict]) -> list[str]:
    """Return ordered agent list per §12.2 and EarthQuery investigation specification."""
    plan_obj, spec, _ = build_investigation_plan(query, assets)
    
    # Map step agents to orchestrator node names
    agent_map = {
        "input_validator": "input_validator",
        "perception": "perception",
        "change_agent": "change_agent",
        "change_vqa": "change_vqa",
        "sar_agent": "sar_agent",
        "grounding": "grounding",
        "multimodal": "multimodal",
        "gis_code_agent": "gis_code",
        "hypothesis_engine": "hypothesis_engine",
        "rag": "rag",
        "verifier": "verifier",
    }
    
    ordered_nodes = []
    # Perception always runs early
    if any(s.agent == "perception" for s in plan_obj.steps):
        ordered_nodes.append("perception")

    for s in plan_obj.steps:
        node = agent_map.get(s.agent)
        if node and node not in ("input_validator", "verifier") and node not in ordered_nodes:
            ordered_nodes.append(node)

    # Ensure backwards compatibility with expected test agent names
    dates = _dates(assets)
    if len(dates) >= 2 and "change_agent" not in ordered_nodes:
        ordered_nodes.append("change_agent")
        if "change_vqa" not in ordered_nodes:
            ordered_nodes.append("change_vqa")

    q = (query or "").lower()
    if any(t in q for t in ("percent", "%", "area", "km2", "km²", "how much", "threshold", "more than", "how many", "count")) and "gis_code" not in ordered_nodes:
        ordered_nodes.append("gis_code")

    if any(t in q for t in ("how many", "where", "find", "locate", "detect", "show me", "count", "buildings", "building")) and "grounding" not in ordered_nodes:
        ordered_nodes.append("grounding")

    sensors = _sensors(assets)
    if "optical" in sensors and "sar" in sensors and "multimodal" not in ordered_nodes:
        ordered_nodes.append("multimodal")

    if any(t in q for t in ("ndvi", "ndwi", "sar", "flood", "water", "sop", "protocol", "disaster", "hazard", "vegetation")) and "rag" not in ordered_nodes:
        ordered_nodes.append("rag")

    return ordered_nodes


def plan_rationale(query: str, assets: list[dict]) -> dict:
    """Why each agent was included — surfaces EarthQuery compiler understanding."""
    spec, understanding = EarthQueryCompiler.compile(query, asset_metadata=assets)
    dates = _dates(assets)
    sensors = sorted(_sensors(assets))
    sensor_decision = AutonomousSensorSelector.select_sensors(spec, assets)

    return {
        "dates": dates,
        "sensors": sensors,
        "bi_temporal": len(dates) >= 2 or spec.temporal.enabled,
        "intent": spec.intent,
        "phenomenon": spec.phenomenon,
        "target_objects": spec.target_objects,
        "required_operations": spec.required_operations,
        "query_understanding": understanding.model_dump(),
        "sensor_selection": sensor_decision.model_dump(),
    }


def narrate_plan(query: str, plan: list[str], rationale: dict) -> str | None:
    """Optional one-sentence LLM narration of the investigation plan."""
    if not llm_client.is_available():
        return None
    user_prompt = (
        f"Question: {query!r}\nInvestigation plan: {plan}\n"
        f"EarthQuery understanding: {rationale.get('query_understanding', {})}"
    )
    return llm_client.complete(_LLM_SYSTEM_PROMPT, user_prompt, max_tokens=120)

