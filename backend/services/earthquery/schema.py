"""EarthQuery Schema Layer — Pydantic models for structured investigation specifications,
query understanding, evidence, claims, sensor decisions, and hypotheses.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class TemporalSpec(BaseModel):
    enabled: bool = False
    start: str | None = None
    end: str | None = None
    period_months: list[str] = Field(default_factory=list)
    comparison_type: Literal["bitemporal", "multitemporal", "annual", "none"] = "none"


class EarthQuerySpec(BaseModel):
    """Structured investigation specification compiled from natural language."""
    intent: str = Field(description="Taxonomy intent e.g. flood_impact_change, building_count")
    location: dict[str, Any] | None = Field(default=None, description="GeoJSON geometry or spatial reference")
    temporal: TemporalSpec = Field(default_factory=TemporalSpec)
    phenomenon: str | None = Field(default=None, description="Phenomenon e.g. flooding, vegetation_loss")
    target_objects: list[str] = Field(default_factory=list, description="Target object categories e.g. buildings")
    required_operations: list[str] = Field(default_factory=list, description="Ordered GIS/analysis operations")
    preferred_modalities: list[str] = Field(default_factory=lambda: ["optical"], description="e.g. optical, sar")
    evidence_requirements: list[str] = Field(default_factory=list, description="Artifact types required")
    requires_numeric_result: bool = False
    requires_visual_evidence: bool = True
    requires_verification: bool = True
    requires_sar: bool = False
    requires_gis: bool = False
    confidence_policy: str = "general"


class QueryUnderstanding(BaseModel):
    """High-level query understanding surfaced to client and orchestrator."""
    intent: str
    phenomenon: str | None = None
    target: str | None = None
    temporal: bool = False
    requires_change_detection: bool = False
    requires_sar: bool = False
    requires_gis: bool = False
    summary: str = ""


class SensorSelection(BaseModel):
    selected: list[str] = Field(default_factory=list)
    primary: str = "optical"
    reason: str = ""
    sensor_reliability: dict[str, float] = Field(default_factory=dict)
    cloud_contamination_optical: float = 0.0
    optical_suitability: float = 0.85
    sar_suitability: float = 0.85


class ModelSelectionDecision(BaseModel):
    task: str
    model_name: str
    modality: str
    version: str = "1.0.0"
    mode: Literal["neural", "heuristic_fallback", "deterministic_gis"] = "neural"
    reason: str = ""
    gpu_used: bool = False


class Claim(BaseModel):
    id: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    numeric_value: float | int | None = None
    metric_unit: str | None = None


class EvidenceItem(BaseModel):
    evidence_id: str = ""
    id: str | None = None
    type: str
    source: str  # optical | sar | fusion | gis | rag
    modality: str = ""
    model: str
    confidence: float
    artifact: str | None = None
    artifact_path: str | None = None
    spatial_scope: Any | None = None
    temporal_scope: str | None = None
    contribution: str | None = None
    interpretation: str | None = None
    limitations: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.evidence_id and self.id:
            self.evidence_id = self.id
        elif not self.id and self.evidence_id:
            self.id = self.evidence_id
        if not self.modality:
            self.modality = self.source


class HypothesisItem(BaseModel):
    id: str
    label: str
    description: str
    required_evidence: list[str] = Field(default_factory=list)
    support: float = 0.0
    evidence_ids: list[str] = Field(default_factory=list)


class HypothesisEvaluation(BaseModel):
    hypotheses: list[HypothesisItem] = Field(default_factory=list)
    most_supported: str | None = None
    interpretation: str = ""


class InvestigationStep(BaseModel):
    id: str
    name: str
    type: str
    agent: str
    modality: str | None = None
    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"
    summary: str | None = None
    dependencies: list[str] = Field(default_factory=list)


class InvestigationPlan(BaseModel):
    investigation_id: str
    mode: Literal["ask", "investigate", "explore"] = "investigate"
    steps: list[InvestigationStep] = Field(default_factory=list)
    current_iteration: int = 1
    max_iterations: int = 3
    sensor_selection: SensorSelection | None = None
    query_understanding: QueryUnderstanding | None = None
