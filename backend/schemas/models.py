"""Pydantic schemas mirroring PRD §9.3 shared sub-schemas."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ValidationReport(BaseModel):
    format: str | None = None
    width: int | None = None
    height: int | None = None
    bands: int | None = None
    crs: str | None = None
    resolution_m: list[float] | None = None
    bounds: list[float] | None = None
    bounds_wgs84: list[float] | None = None
    nodata: float | None = None
    sensor_type: str | None = None
    band_mapping_guess: dict[str, int] | None = None
    band_mapping_confidence: str | None = None
    valid: bool = False
    errors: list[str] = Field(default_factory=list)


class AssetRef(BaseModel):
    asset_id: str
    capture_date: str | None = None
    sensor_type: Literal["optical", "sar"] = "optical"
    band_mapping: dict[str, int] | None = None  # explicit user override (§10.2)


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    region: dict[str, Any] | None = None       # GeoJSON geometry (FR-14 AC2)
    assets: list[AssetRef] = Field(min_length=1)


class ChangeDetectionRequest(BaseModel):
    image_before_asset_id: str
    image_after_asset_id: str
    region: dict[str, Any] | None = None
    threshold_pct: float = -20.0


class SpatialQueryRequest(BaseModel):
    predicate: Literal["within_distance", "contains", "intersects", "adjacent"]
    target_asset_id: str
    reference_geometry: dict[str, Any]
    distance_m: float = 100.0
    object_class: str | None = None


class ExecuteAnalysisRequest(BaseModel):
    intent: str
    params: dict[str, Any] = Field(default_factory=dict)
    asset_ids: list[str] = Field(min_length=1)


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    agents: list[dict] = Field(default_factory=list)
    progress_pct: int = 0
    error: str | None = None


class DetectedObject(BaseModel):
    id: str
    class_label: str
    bbox_pixel: list[float]
    geometry_wgs84: dict[str, Any]
    mask_encoding: Literal["polygon", "rle"] = "polygon"
    confidence: float
