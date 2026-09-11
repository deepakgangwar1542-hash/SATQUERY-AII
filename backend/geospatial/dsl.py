"""EarthQuery GIS DSL — Validated Intermediate Representation (IR) for deterministic geospatial operations (FR-12, Section 16).

Supports:
- BUILDING_COUNT
- FLOOD_EXTENT
- CHANGE_AREA
- CHANGE_PERCENT
- OBJECT_COUNT
- SPATIAL_INTERSECTION
- BUFFER_QUERY
- DISTANCE_QUERY
- TEMPORAL_COMPARISON
- VEGETATION_CHANGE
- WATER_CHANGE
- URBAN_EXPANSION
- AFFECTED_OBJECTS
- AREA_STATISTICS
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class GISOperationType(str, Enum):
    BUILDING_COUNT = "BUILDING_COUNT"
    FLOOD_EXTENT = "FLOOD_EXTENT"
    CHANGE_AREA = "CHANGE_AREA"
    CHANGE_PERCENT = "CHANGE_PERCENT"
    OBJECT_COUNT = "OBJECT_COUNT"
    SPATIAL_INTERSECTION = "SPATIAL_INTERSECTION"
    BUFFER_QUERY = "BUFFER_QUERY"
    DISTANCE_QUERY = "DISTANCE_QUERY"
    TEMPORAL_COMPARISON = "TEMPORAL_COMPARISON"
    VEGETATION_CHANGE = "VEGETATION_CHANGE"
    WATER_CHANGE = "WATER_CHANGE"
    URBAN_EXPANSION = "URBAN_EXPANSION"
    AFFECTED_OBJECTS = "AFFECTED_OBJECTS"
    AREA_STATISTICS = "AREA_STATISTICS"


class GISOperationNode(BaseModel):
    id: str
    op: GISOperationType
    inputs: list[str] = Field(default_factory=list, description="IDs of input layers or operations")
    params: dict[str, Any] = Field(default_factory=dict)


class GISExecutionPlanIR(BaseModel):
    """Validated Intermediate Representation pipeline of GIS operations."""
    query: str
    nodes: list[GISOperationNode]

    def validate_dag(self) -> bool:
        """Validates that operation dependencies exist and form an acyclic graph."""
        available_ids = {"input_optical", "input_sar", "input_mask", "input_buildings"}
        for node in self.nodes:
            for inp in node.inputs:
                if inp not in available_ids:
                    raise ValueError(f"GIS DSL validation error: missing dependency '{inp}' for node '{node.id}'")
            available_ids.add(node.id)
        return True


def compile_query_to_gis_ir(query: str, spec: Any) -> GISExecutionPlanIR:
    """Compiles an EarthQuerySpec into a validated GIS Execution Plan IR."""
    nodes: list[GISOperationNode] = []
    q_lower = query.lower()

    if spec.intent == "flood_impact_change" or ("flood" in q_lower and "building" in q_lower):
        # 1. Flood Extent
        nodes.append(
            GISOperationNode(
                id="flood_mask",
                op=GISOperationType.FLOOD_EXTENT,
                inputs=["input_sar"],
                params={"threshold_db": -18.0},
            )
        )
        # 2. Building Footprints
        nodes.append(
            GISOperationNode(
                id="building_layer",
                op=GISOperationType.OBJECT_COUNT,
                inputs=["input_optical"],
                params={"class_label": "building"},
            )
        )
        # 3. Spatial Intersection
        nodes.append(
            GISOperationNode(
                id="affected_buildings",
                op=GISOperationType.SPATIAL_INTERSECTION,
                inputs=["flood_mask", "building_layer"],
                params={"predicate": "intersects"},
            )
        )
        # 4. Count
        nodes.append(
            GISOperationNode(
                id="final_count",
                op=GISOperationType.BUILDING_COUNT,
                inputs=["affected_buildings"],
                params={},
            )
        )

    elif spec.intent in ("building_count", "object_grounding") or "how many" in q_lower:
        nodes.append(
            GISOperationNode(
                id="building_layer",
                op=GISOperationType.OBJECT_COUNT,
                inputs=["input_optical"],
                params={"class_label": spec.target_objects[0] if spec.target_objects else "building"},
            )
        )

    elif "buffer" in q_lower or "within" in q_lower:
        import re
        dist_match = re.search(r"(\d+)\s*(m|meter|km)", q_lower)
        dist_m = 500.0
        if dist_match:
            val = float(dist_match.group(1))
            dist_m = val * 1000.0 if dist_match.group(2) == "km" else val
        nodes.append(
            GISOperationNode(
                id="buffered_zone",
                op=GISOperationType.BUFFER_QUERY,
                inputs=["input_mask"],
                params={"distance_m": dist_m},
            )
        )
        nodes.append(
            GISOperationNode(
                id="affected_objects",
                op=GISOperationType.AFFECTED_OBJECTS,
                inputs=["buffered_zone", "input_buildings"],
                params={},
            )
        )

    else:
        # Default area statistics / change area
        nodes.append(
            GISOperationNode(
                id="change_area",
                op=GISOperationType.CHANGE_AREA,
                inputs=["input_mask"],
                params={},
            )
        )

    ir = GISExecutionPlanIR(query=query, nodes=nodes)
    return ir


GISOperationIR = GISExecutionPlanIR


class EarthQueryGISDSL:
    """DSL Compiler for EarthQuery geospatial operations."""

    def compile(self, query: str, spec: Any = None) -> GISExecutionPlanIR:
        if spec is None:
            from ..services.earthquery.compiler import EarthQueryCompiler
            spec, _ = EarthQueryCompiler().compile(query)
        elif isinstance(spec, tuple):
            spec = spec[0]
        return compile_query_to_gis_ir(query, spec)

