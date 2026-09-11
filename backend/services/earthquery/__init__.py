"""EarthQuery Package — Structured Intent Compilation, Investigation Planning, and Sensor Selection."""
from .schema import (
    EarthQuerySpec,
    QueryUnderstanding,
    TemporalSpec,
    SensorSelection,
    ModelSelectionDecision,
    Claim,
    EvidenceItem,
    HypothesisItem,
    HypothesisEvaluation,
    InvestigationStep,
    InvestigationPlan,
)
from .compiler import EarthQueryCompiler

__all__ = [
    "EarthQuerySpec",
    "QueryUnderstanding",
    "TemporalSpec",
    "SensorSelection",
    "ModelSelectionDecision",
    "Claim",
    "EvidenceItem",
    "HypothesisItem",
    "HypothesisEvaluation",
    "InvestigationStep",
    "InvestigationPlan",
    "EarthQueryCompiler",
]
