"""EarthQuery Compiler — Translates natural-language queries into typed investigation specifications.

Supports the full SIH26167 Earth-observation intent taxonomy without relying solely on keywords.
Uses structured LLM generation when available, backed by deterministic semantic extraction.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ...services import llm_client
from .schema import EarthQuerySpec, QueryUnderstanding, TemporalSpec

TAXONOMY_INTENTS = [
    "flood_impact_change",
    "image_question",
    "image_caption",
    "object_detection",
    "object_grounding",
    "land_cover_analysis",
    "flood_detection",
    "water_detection",
    "vegetation_change",
    "urban_change",
    "building_count",
    "temporal_change",
    "change_explanation",
    "optical_sar_comparison",
    "multimodal_analysis",
    "area_measurement",
    "spatial_intersection",
    "distance_query",
    "buffer_query",
    "affected_objects",
    "anomaly_detection",
    "historical_comparison",
    "hypothesis_investigation",
]

MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"
]

_LLM_COMPILER_SYSTEM_PROMPT = f"""You are the EarthQuery Compiler for SatQuery AI, an autonomous Earth-observation investigation system.
Convert natural language user questions into a strictly valid JSON EarthQuery investigation specification.

Taxonomy intents:
{json.dumps(TAXONOMY_INTENTS)}

Output JSON schema must match:
{{
  "intent": "<one of taxonomy intents>",
  "phenomenon": "<e.g. flooding, vegetation_loss, urban_expansion, anomaly, or null>",
  "target_objects": ["<e.g. buildings, roads, water, vegetation>"],
  "temporal": {{
    "enabled": true|false,
    "start": "<start date/month or null>",
    "end": "<end date/month or null>",
    "comparison_type": "bitemporal"|"multitemporal"|"annual"|"none"
  }},
  "required_operations": ["<e.g. temporal_comparison, flood_detection, building_detection, spatial_intersection, count, area>"],
  "preferred_modalities": ["optical"|"sar"],
  "evidence_requirements": ["before_image"|"after_image"|"flood_mask"|"building_mask"|"change_mask"],
  "requires_numeric_result": true|false,
  "requires_visual_evidence": true,
  "requires_verification": true,
  "requires_sar": true|false,
  "requires_gis": true|false,
  "confidence_policy": "flood_detection"|"building_count"|"change_detection"|"object_grounding"|"general"
}}
Return ONLY JSON, no markdown formatting or commentary.
"""


class EarthQueryCompiler:
    """Compiles natural language into an EarthQuerySpec and QueryUnderstanding."""

    @classmethod
    def compile(
        cls,
        query: str,
        spatial_scope: dict[str, Any] | None = None,
        asset_metadata: list[dict[str, Any]] | None = None,
    ) -> tuple[EarthQuerySpec, QueryUnderstanding]:
        clean_q = (query or "").strip()

        # 1. Try LLM-backed compiler if API is configured
        if llm_client.is_available() and len(clean_q) > 8:
            try:
                prompt = f"Query: {clean_q}\nSpatial scope present: {bool(spatial_scope)}\nAssets: {asset_metadata}"
                raw = llm_client.complete(_LLM_COMPILER_SYSTEM_PROMPT, prompt, max_tokens=600)
                if raw:
                    match = re.search(r"\{.*\}", raw, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))
                        data["location"] = spatial_scope
                        spec = EarthQuerySpec(**data)
                        understanding = cls._build_understanding(clean_q, spec)
                        return spec, understanding
            except Exception:
                pass  # Fall through to robust deterministic semantic compiler

        # 2. Deterministic Semantic Compiler Fallback
        spec = cls._semantic_parse(clean_q, spatial_scope, asset_metadata or [])
        understanding = cls._build_understanding(clean_q, spec)
        return spec, understanding

    @classmethod
    def _extract_temporal(cls, q: str) -> TemporalSpec:
        q_lower = q.lower()
        temporal = TemporalSpec()

        # Check month pairs e.g. "between June and August"
        between_match = re.search(
            r"between\s+([A-Za-z]+|\d{4}-\d{2}-\d{2})\s+and\s+([A-Za-z]+|\d{4}-\d{2}-\d{2})",
            q,
            re.IGNORECASE,
        )
        from_to_match = re.search(
            r"from\s+([A-Za-z]+|\d{4}-\d{2}-\d{2})\s+to\s+([A-Za-z]+|\d{4}-\d{2}-\d{2})",
            q,
            re.IGNORECASE,
        )

        match = between_match or from_to_match
        if match:
            s_raw, e_raw = match.group(1).capitalize(), match.group(2).capitalize()
            temporal.enabled = True
            temporal.start = s_raw
            temporal.end = e_raw
            temporal.comparison_type = "bitemporal"
            return temporal

        if any(w in q_lower for w in ("last year", "compared with last year", "year over year", "annual")):
            temporal.enabled = True
            temporal.comparison_type = "annual"
            return temporal

        if any(w in q_lower for w in ("before", "after", "change", "increased", "decreased", "between", "timeline", "temporal")):
            temporal.enabled = True
            temporal.comparison_type = "bitemporal"

        return temporal

    @classmethod
    def _semantic_parse(
        cls,
        query: str,
        spatial_scope: dict[str, Any] | None,
        assets: list[dict[str, Any]],
    ) -> EarthQuerySpec:
        q = query.lower()
        temporal = cls._extract_temporal(query)

        # Asset metadata cues
        sensors = {a.get("sensor_type", "optical") for a in assets}
        has_dates = len({a.get("capture_date") for a in assets if a.get("capture_date")}) >= 2
        if has_dates:
            temporal.enabled = True
            if temporal.comparison_type == "none":
                temporal.comparison_type = "bitemporal"

        # Detect targets
        targets = []
        if any(w in q for w in ("building", "buildings", "house", "structures")):
            targets.append("buildings")
        if any(w in q for w in ("road", "roads", "highway")):
            targets.append("roads")
        if any(w in q for w in ("water", "flood", "river", "lake", "inundat")):
            targets.append("water")
        if any(w in q for w in ("vegetation", "crop", "forest", "tree", "canopy")):
            targets.append("vegetation")
        if any(w in q for w in ("tank", "storage tank", "industrial")):
            targets.append("storage tanks")
        if any(w in q for w in ("ship", "vessel", "boat")):
            targets.append("ships")
        if any(w in q for w in ("vehicle", "car", "truck")):
            targets.append("vehicles")

        # Detect phenomenon
        phenomenon = None
        if any(w in q for w in ("flood", "flooding", "inundat", "overflow")):
            phenomenon = "flooding"
        elif any(w in q for w in ("deforest", "vegetation loss", "drought", "canopy loss")):
            phenomenon = "vegetation_loss"
        elif any(w in q for w in ("construction", "urban", "built up", "expansion")):
            phenomenon = "urban_expansion"
        elif any(w in q for w in ("unusual", "anomaly", "anomalies", "abnormal")):
            phenomenon = "anomaly"

        # Detect intent
        is_flood = phenomenon == "flooding" or "flood" in q
        is_count = any(w in q for w in ("how many", "count", "number of", "how much"))
        is_anomaly = any(w in q for w in ("unusual", "anomaly", "anomalies", "find anything unusual"))
        is_hypothesis = any(w in q for w in ("what caused", "why did", "explain the change", "cause of"))
        is_distance = any(w in q for w in ("within", "distance", "meters", "buffer", "km from"))
        is_sar_compare = "sar" in q and "optical" in q

        intent = "image_question"
        ops = []
        mods = ["optical"]
        evid = ["image"]
        numeric = False
        requires_gis = False
        requires_sar = False
        policy = "general"

        if is_flood and ("building" in targets or "buildings" in q) and temporal.enabled:
            intent = "flood_impact_change"
            ops = [
                "temporal_comparison",
                "water_detection",
                "flood_detection",
                "building_detection",
                "spatial_intersection",
                "count",
            ]
            mods = ["sar", "optical"]
            evid = ["before_image", "after_image", "flood_mask", "building_mask", "spatial_intersection"]
            numeric = True
            requires_gis = True
            requires_sar = True
            policy = "flood_detection"

        elif is_hypothesis:
            intent = "hypothesis_investigation"
            ops = ["temporal_comparison", "multimodal_analysis", "hypothesis_generation", "evidence_evaluation"]
            mods = ["optical", "sar"]
            evid = ["change_mask", "multimodal_profile", "hypothesis_evaluation"]
            policy = "change_detection"

        elif is_anomaly:
            intent = "anomaly_detection"
            ops = ["anomaly_scan", "multispectral_anomaly_scan", "temporal_delta", "sar_surface_change", "anomaly_ranking"]
            mods = ["optical", "sar"]
            evid = ["anomaly_heat_map", "anomaly_ranking"]
            policy = "general"

        elif is_flood:
            intent = "flood_detection"
            ops = ["water_detection", "temporal_flood_extent", "flood_mask_vectorization"]
            mods = ["sar", "optical"]
            evid = ["flood_mask", "flood_extent_geojson"]
            requires_sar = True
            requires_gis = True
            policy = "flood_detection"

        elif is_count and any(t in ("building", "buildings") for t in targets):
            intent = "building_count"
            ops = ["object_detection", "building_detection", "segmentation", "count"]
            mods = ["optical"]
            evid = ["building_mask", "object_detections"]
            numeric = True
            requires_gis = True
            policy = "building_count"

        elif is_distance:
            intent = "buffer_query" if "buffer" in q or "within" in q else "distance_query"
            ops = ["spatial_buffer", "spatial_intersection", "count"]
            mods = ["optical"]
            evid = ["buffer_geometry", "spatial_intersection"]
            requires_gis = True
            numeric = True
            policy = "general"

        elif is_sar_compare or "sar" in q:
            intent = "optical_sar_comparison"
            ops = ["sar_speckle_filter", "polarimetric_analysis", "optical_sar_cross_validation"]
            mods = ["optical", "sar"]
            evid = ["optical_scene", "sar_backscatter", "cross_validation_report"]
            requires_sar = True
            policy = "general"

        elif temporal.enabled:
            intent = "temporal_change"
            ops = ["coregistration", "siamese_change_detection", "change_vectorization", "area_statistics"]
            mods = ["optical"]
            evid = ["before_image", "after_image", "change_mask", "change_geojson"]
            requires_gis = True
            policy = "change_detection"

        elif any(w in q for w in ("ground", "locate", "where is", "find", "show me")):
            intent = "object_grounding"
            ops = ["zero_shot_grounding", "polygon_extraction"]
            mods = ["optical"]
            evid = ["bounding_boxes", "grounding_polygons"]
            policy = "object_grounding"

        elif any(w in q for w in ("area", "size", "extent", "hectares", "km2", "square")):
            intent = "area_measurement"
            ops = ["feature_segmentation", "metric_area_calculation"]
            mods = ["optical"]
            evid = ["polygon_extent", "metric_area"]
            numeric = True
            requires_gis = True
            policy = "general"

        return EarthQuerySpec(
            intent=intent,
            location=spatial_scope,
            temporal=temporal,
            phenomenon=phenomenon,
            target_objects=targets or (["objects"] if is_count else []),
            required_operations=ops or ["scene_understanding", "vqa"],
            preferred_modalities=mods,
            evidence_requirements=evid,
            requires_numeric_result=numeric,
            requires_visual_evidence=True,
            requires_verification=True,
            requires_sar=requires_sar or ("sar" in sensors),
            requires_gis=requires_gis or is_count or numeric,
            confidence_policy=policy,
        )

    @classmethod
    def _build_understanding(cls, query: str, spec: EarthQuerySpec) -> QueryUnderstanding:
        target_str = ", ".join(spec.target_objects) if spec.target_objects else None
        requires_change = spec.temporal.enabled or "change" in spec.intent or "temporal" in spec.intent
        summary_parts = [f"Investigating {spec.intent.replace('_', ' ')}"]
        if spec.phenomenon:
            summary_parts.append(f"regarding {spec.phenomenon}")
        if target_str:
            summary_parts.append(f"targeting {target_str}")
        if spec.temporal.enabled:
            if spec.temporal.start and spec.temporal.end:
                summary_parts.append(f"between {spec.temporal.start} and {spec.temporal.end}")
            else:
                summary_parts.append("across temporal sequence")

        return QueryUnderstanding(
            intent=spec.intent,
            phenomenon=spec.phenomenon,
            target=target_str,
            temporal=spec.temporal.enabled,
            requires_change_detection=requires_change,
            requires_sar=spec.requires_sar or "sar" in spec.preferred_modalities,
            requires_gis=spec.requires_gis,
            summary=" ".join(summary_parts) + ".",
        )
