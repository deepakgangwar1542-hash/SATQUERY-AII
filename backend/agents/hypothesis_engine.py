"""Hypothesis Engine — Multi-hypothesis generation and multimodal evidence evaluation (FR-7, Section 11).

Formulates competing explanations for observed Earth phenomena (e.g. major landscape changes)
and deterministically scores each hypothesis against collected optical, SAR, and temporal evidence.
"""
from __future__ import annotations

from typing import Any
from ..services.earthquery.schema import HypothesisItem, HypothesisEvaluation


class HypothesisEngine:
    """Generates candidate hypotheses and calculates evidence support scores."""

    @classmethod
    def evaluate(
        cls,
        query: str,
        evidence_list: list[dict[str, Any]],
        agent_outputs: dict[str, Any],
    ) -> HypothesisEvaluation:
        # 1. Candidate Hypotheses
        hypotheses = [
            HypothesisItem(
                id="H1_FLOOD",
                label="Flooding & Hydrological Inundation",
                description="Landscape alteration driven by surface water expansion, river overflow, or heavy rainfall inundation.",
                required_evidence=["water_increase", "sar_specular_drop", "temporal_change"],
                support=0.0,
                evidence_ids=[],
            ),
            HypothesisItem(
                id="H2_URBAN",
                label="Urban Development & Construction",
                description="Surface modification from new built structures, ground clearing, or infrastructure expansion.",
                required_evidence=["building_detections", "structural_change", "vegetation_loss"],
                support=0.0,
                evidence_ids=[],
            ),
            HypothesisItem(
                id="H3_VEGETATION_LOSS",
                label="Vegetation Loss & Agricultural Clearance",
                description="Decrease in canopy greenness or agricultural harvesting without permanent construction or flooding.",
                required_evidence=["ndvi_decrease", "roughness_constant"],
                support=0.0,
                evidence_ids=[],
            ),
            HypothesisItem(
                id="H4_ARTIFACT",
                label="Acquisition Artifact or Cloud Contamination",
                description="Apparent change caused by cloud cover, cloud shadows, or differences in sensor illumination angles.",
                required_evidence=["high_cloud_fraction", "spectral_anomaly"],
                support=0.0,
                evidence_ids=[],
            ),
        ]

        # 2. Extract Evidence Signals
        change_out = agent_outputs.get("change_agent") or {}
        sar_out = agent_outputs.get("sar_agent") or {}
        mm_out = agent_outputs.get("multimodal") or {}
        perc_out = agent_outputs.get("perception") or {}
        grounding_out = agent_outputs.get("grounding") or {}

        cloud_fraction = perc_out.get("scene_profile", {}).get("cloud_fraction", 0.0)
        has_sar_water = sar_out.get("water_share", 0.0) > 0.05 or sar_out.get("new_flood_inundation_km2", 0.0) > 0.05
        has_change = change_out.get("statistics", {}).get("percent_of_aoi", 0.0) > 2.0
        n_buildings = len(grounding_out.get("objects", []))

        # Check for water evidence
        mm_shares = mm_out.get("prediction", {}).get("class_shares", {})
        water_share = mm_shares.get("water", 0.0) or sar_out.get("water_share", 0.0)
        veg_loss_km2 = change_out.get("statistics", {}).get("class_breakdown", {}).get("vegetation_loss_km2", 0.0)

        # 3. Score Support Scores Mathematically
        # H1: Flooding
        h1_score = 0.1
        h1_ev_ids = []
        if has_sar_water:
            h1_score += 0.50
            h1_ev_ids.append("ev_sar_flood")
        if water_share > 0.10:
            h1_score += 0.25
            h1_ev_ids.append("ev_optical_water")
        if has_change:
            h1_score += 0.15
        hypotheses[0].support = round(min(0.96, h1_score), 2)
        hypotheses[0].evidence_ids = h1_ev_ids

        # H2: Urban
        h2_score = 0.1
        h2_ev_ids = []
        if n_buildings > 5:
            h2_score += 0.45
            h2_ev_ids.append("ev_grounding_buildings")
        if has_change and not has_sar_water:
            h2_score += 0.25
            h2_ev_ids.append("ev_structural_change")
        hypotheses[1].support = round(min(0.90, h2_score), 2)
        hypotheses[1].evidence_ids = h2_ev_ids

        # H3: Vegetation Loss
        h3_score = 0.1
        h3_ev_ids = []
        if veg_loss_km2 > 0.05 and not has_sar_water:
            h3_score += 0.55
            h3_ev_ids.append("ev_vegetation_loss")
        if has_change:
            h3_score += 0.15
        hypotheses[2].support = round(min(0.92, h3_score), 2)
        hypotheses[2].evidence_ids = h3_ev_ids

        # H4: Artifact
        h4_score = 0.05
        h4_ev_ids = []
        if cloud_fraction > 0.25:
            h4_score += 0.65
            h4_ev_ids.append("ev_cloud_contamination")
        hypotheses[3].support = round(min(0.85, h4_score), 2)
        hypotheses[3].evidence_ids = h4_ev_ids

        # Rank by support score
        hypotheses.sort(key=lambda h: h.support, reverse=True)
        top = hypotheses[0]

        interpretation = (
            f"Most observational evidence supports '{top.label}' (support index: {top.support:.2f}). "
            f"Alternative explanations evaluated: {', '.join(f'{h.label} ({h.support:.2f})' for h in hypotheses[1:])}. "
            "Findings represent evidence correlation rather than unverified causal certainty."
        )

        return HypothesisEvaluation(
            hypotheses=hypotheses,
            most_supported=top.label,
            interpretation=interpretation,
        )
