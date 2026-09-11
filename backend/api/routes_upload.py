"""POST /api/v1/upload — GeoTIFF/TIFF ingestion with FR-1 validation."""
from __future__ import annotations

import os

from fastapi import APIRouter, File, Form, UploadFile

from ..geospatial import raster as graster
from ..services import job_store
from ..utils.assets import register_asset
from .errors import problem

router = APIRouter(tags=["upload"])


@router.get("/assets")
def list_assets():
    """Session/instance asset list (extension to the §9.1 table so the UI can
    restore state after a refresh; read-only, no schema impact)."""
    from ..utils.assets import _INDEX
    import json
    if not _INDEX.exists():
        return []
    index = json.loads(_INDEX.read_text(encoding="utf-8"))
    return [
        {"asset_id": aid, "sensor_type": rec.get("sensor_type"),
         "capture_date": rec.get("capture_date"), "name": aid + ".tif",
         "validation": rec.get("validation", {})}
        for aid, rec in index.items()
    ]


@router.post("/upload")
async def upload(file: UploadFile = File(...),
                 sensor_type: str = Form("optical"),
                 capture_date: str | None = Form(None)):
    if sensor_type not in ("optical", "sar"):
        return problem(422, "Validation Error", "sensor_type must be optical|sar")
    asset_id = job_store.new_asset_id()
    dest = job_store.DATA_DIR / "uploads" / f"{asset_id}.tif"
    dest.parent.mkdir(parents=True, exist_ok=True)

    size = 0
    with open(dest, "wb") as fh:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > graster.MAX_UPLOAD_BYTES:
                fh.close()
                os.remove(dest)
                return problem(422, "Validation Error", "file_too_large")
            fh.write(chunk)

    report = graster.validate_raster(dest, sensor_type)
    if not report.get("valid"):
        os.remove(dest)
        return problem(422, "Raster Validation Failed",
                       "; ".join(report.get("errors", ["unknown"])))
    register_asset(asset_id, str(dest), report,
                   {"capture_date": capture_date, "sensor_type": sensor_type})
    report = {**report, "sensor_type": sensor_type}
    return {"asset_id": asset_id, "validation": report}
