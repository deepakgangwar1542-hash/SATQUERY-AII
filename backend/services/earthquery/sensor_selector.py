"""Autonomous Sensor Selection Component — Evaluates task requirements, sensor availability,
and data quality (e.g. cloud contamination) to dynamically select sensors.
"""
from __future__ import annotations

from typing import Any
from .schema import EarthQuerySpec, SensorSelection


class AutonomousSensorSelector:
    """Dynamically selects optical, SAR, or both sensors based on task and quality."""

    @classmethod
    def select_sensors(
        cls,
        spec: EarthQuerySpec,
        assets: list[dict[str, Any]],
        cloud_contamination_optical: float = 0.0,
    ) -> SensorSelection:
        available_sensors = {a.get("sensor_type", "optical") for a in assets}
        has_optical = "optical" in available_sensors or not available_sensors
        has_sar = "sar" in available_sensors

        selected: list[str] = []
        primary = "optical"
        reasons: list[str] = []

        is_flood_task = spec.intent in ("flood_detection", "flood_impact_change", "water_detection")
        is_cloudy = cloud_contamination_optical > 0.20

        # Sensor Reliability Baseline
        opt_reliability = round(max(0.1, 1.0 - cloud_contamination_optical), 3)
        sar_reliability = 0.88 if has_sar else 0.0
        reliabilities = {}
        if has_optical:
            reliabilities["optical"] = opt_reliability
        if has_sar:
            reliabilities["sar"] = sar_reliability

        if is_flood_task:
            if has_sar and has_optical:
                selected = ["sar", "optical"]
                if is_cloudy:
                    primary = "sar"
                    reasons.append(
                        f"Optical imagery exhibits significant cloud contamination ({cloud_contamination_optical*100:.1f}%); "
                        "SAR selected as primary all-weather penetration sensor, optical retained for contextual reference."
                    )
                else:
                    primary = "sar"
                    reasons.append(
                        "Flood analysis benefits from dual-sensor fusion: SAR provides high-contrast specular "
                        "water delineation, while optical provides contextual land-cover semantics."
                    )
            elif has_sar:
                selected = ["sar"]
                primary = "sar"
                reasons.append("SAR selected for all-weather flood surface roughness detection.")
            else:
                selected = ["optical"]
                primary = "optical"
                if is_cloudy:
                    reasons.append(
                        f"Optical imagery contains cloud contamination ({cloud_contamination_optical*100:.1f}%), "
                        "and no SAR asset is present; proceeding with degraded optical confidence."
                    )
                else:
                    reasons.append("Optical sensor selected using multispectral water indices (NDWI).")

        elif spec.intent in ("hypothesis_investigation", "anomaly_detection"):
            if has_optical and has_sar:
                selected = ["optical", "sar"]
                primary = "optical" if not is_cloudy else "sar"
                reasons.append("Investigation query requires multimodal cross-validation between optical reflectance and SAR backscatter.")
            elif has_optical:
                selected = ["optical"]
                primary = "optical"
                reasons.append("Optical imagery selected for scene inspection.")
            else:
                selected = ["sar"]
                primary = "sar"
                reasons.append("SAR backscatter selected for surface roughness examination.")

        elif spec.intent in ("building_count", "object_grounding", "object_detection"):
            selected = ["optical"]
            primary = "optical"
            reasons.append("High-resolution optical spectral bands selected for zero-shot object detection and geometric delineation.")
            if has_sar and is_cloudy:
                selected.append("sar")
                reasons.append("SAR cross-pol added to verify built-up double-bounce scattering under optical cloud cover.")

        else:
            # Default general routing
            if has_optical and has_sar:
                selected = ["optical", "sar"]
                primary = "optical" if not is_cloudy else "sar"
                reasons.append("Optical and SAR assets fused for comprehensive multimodal earth observation.")
            elif has_sar:
                selected = ["sar"]
                primary = "sar"
                reasons.append("Single-modality SAR asset available.")
            else:
                selected = ["optical"]
                primary = "optical"
                reasons.append("Optical multispectral imagery selected.")

        return SensorSelection(
            selected=selected,
            primary=primary,
            reason=" ".join(reasons),
            sensor_reliability=reliabilities,
            cloud_contamination_optical=round(cloud_contamination_optical, 3),
            optical_suitability=opt_reliability,
            sar_suitability=sar_reliability if has_sar else 0.2,
        )

    @classmethod
    def select_sensor(
        cls,
        spec: EarthQuerySpec,
        optical_available: bool = True,
        sar_available: bool = True,
        optical_cloud_coverage: float = 0.0,
        assets: list[dict[str, Any]] | None = None,
    ) -> SensorSelection:
        """Convenience method accepting explicit booleans and percentage cloud cover."""
        if assets is None:
            assets = []
            if optical_available:
                assets.append({"sensor_type": "optical"})
            if sar_available:
                assets.append({"sensor_type": "sar"})
        cloud_frac = optical_cloud_coverage / 100.0 if optical_cloud_coverage > 1.0 else optical_cloud_coverage
        return cls.select_sensors(spec, assets, cloud_contamination_optical=cloud_frac)

