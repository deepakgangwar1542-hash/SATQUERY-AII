"""Grounding Agent — detection + segmentation (FR-4).

Primary path: Grounding DINO (text-conditioned detection) + SAM2 (masks) via
models.loaders. Fallback path: a deterministic index-threshold segmenter —
picks NDVI/NDWI/brightness thresholds from the referring expression, extracts
connected components as polygon masks, and converts them to WGS84 via the
raster affine transform (FR-4 AC1). Degrades visibly, never silently: the
mode is reported in evidence and lowers confidence.
"""
from __future__ import annotations

import uuid

import numpy as np
from rasterio.features import shapes as raster_shapes
from shapely.affinity import scale as shp_scale
from shapely.geometry import box as shp_box, shape
from shapely.ops import unary_union

from ..geospatial import raster as graster
from ..geospatial import ndvi as gndvi
from ..models import loaders

MAX_OBJECTS = 200


def _class_from_expression(expression: str) -> tuple[str, str]:
    """Map the referring expression to (class_label, detection_rule).
    Detection rule: which index threshold approximates the requested class."""
    e = (expression or "").lower()
    if "water" in e or "river" in e or "lake" in e or "flood" in e:
        return "water", "ndwi_gt_0"
    if "vegetation" in e or "tree" in e or "forest" in e or "crop" in e or "field" in e:
        return "vegetation", "ndvi_gt_03"
    if "building" in e or "road" in e or "urban" in e or "bare" in e or "construction" in e:
        return "built_or_bare", "ndvi_lt_015"
    return "object", "ndvi_lt_015"


def _fallback_objects(image: str, expression: str,
                      band_mapping: dict | None = None) -> dict:
    report = graster.validate_raster(image)
    data = graster.read_raster(image)
    mapping = band_mapping or report.get("band_mapping_guess") or {}
    arr, transform, crs = data["array"], data["transform"], data["crs"]
    label, rule = _class_from_expression(expression)

    try:
        if rule == "ndwi_gt_0":
            idx = gndvi.compute_ndwi(arr, mapping)
            mask = idx > 0.0
        elif rule == "ndvi_gt_03":
            idx = gndvi.compute_ndvi(arr, mapping)
            mask = idx > 0.3
        else:
            idx = gndvi.compute_ndvi(arr, mapping)
            mask = (idx < 0.15) & (graster.to_reflectance(arr[0]) > 0.08)
    except (KeyError, ValueError):
        return {"objects": [], "note": "band_mapping_unresolved", "mode": "index_threshold"}

    mask = np.isfinite(idx) & mask
    objects = []
    geoms = []
    for geom, _val in raster_shapes(mask.astype("uint8"), mask=mask, transform=transform):
        g = shape(geom)
        if g.area < 12 * abs(transform.a * transform.e):  # drop <12-pixel speckle
            continue
        geoms.append(g)
    if geoms:
        # merge tiny fragments, keep the largest up to MAX_OBJECTS
        geoms = sorted(geoms, key=lambda g: g.area, reverse=True)[:MAX_OBJECTS]
        from shapely.ops import transform as shp_transform
        for g in geoms:
            # pixel bbox in raster CRS (row/col order swap via transform)
            minx, miny, maxx, maxy = g.bounds
            inv = ~transform
            c0, r0 = inv * (minx, miny)
            c1, r1 = inv * (maxx, maxy)
            objects.append({
                "id": f"obj_{uuid.uuid4().hex[:6]}",
                "class_label": label,
                "bbox_pixel": [round(min(c0, c1)), round(min(r0, r1)),
                               round(max(c0, c1)), round(max(r0, r1))],
                "geometry_wgs84": None,  # filled below after reprojection
                "mask_encoding": "polygon",
                "confidence": 0.5,
                "_crs_geom": g,
            })
        import geopandas as gpd
        gdf = gpd.GeoDataFrame(
            [o for o in objects], geometry=[o.pop("_crs_geom") for o in objects],
            crs=crs).to_crs(4326)
        from shapely.geometry import mapping as geom_mapping
        for o, geom in zip(objects, gdf.geometry):
            o["geometry_wgs84"] = geom_mapping(geom)
    note = None if objects else "no matching objects found"  # FR-4 AC2
    return {"objects": objects, "note": note, "mode": "index_threshold",
            "rule": rule, "class_label": label}


def ground_objects(image: str, expression: str,
                   band_mapping: dict | None = None) -> dict:
    """FR-4. Returns {objects: DetectedObject[], note, mode, confidence}."""
    det, reason = loaders.load_detector()
    if det is not None:
        try:
            return _dino_objects(det, image, expression, band_mapping)
        except Exception:
            pass  # §12.3: fall back rather than fail the job
    out = _fallback_objects(image, expression, band_mapping)
    out.setdefault("confidence", 0.45 if out["objects"] else 0.3)
    out["degraded_reason"] = reason
    out["uncertainty"] = [{
        "signal": "grounding_degraded",
        "severity": "medium",
        "explanation": f"Grounding ran in index-threshold fallback mode "
                       f"({reason}); detections are coarse index segments, "
                       "not model detections.",
    }]
    return out


def _dino_objects(det: dict, image: str, expression: str,
                  band_mapping: dict | None = None) -> dict:
    """Grounding DINO path (requires a locally fetched checkpoint)."""
    import numpy as np
    import torch  # type: ignore
    from PIL import Image

    arr = graster.read_raster(image)["array"]
    if arr.shape[0] >= 3:
        rgb = arr[[2, 1, 0]] if arr.shape[0] >= 3 else arr[:3]
    else:
        rgb = np.repeat(arr[:1], 3, axis=0)

    refl = graster.to_reflectance(rgb)
    img = Image.fromarray(
        (np.clip(refl, 0, 1) * 255).astype("uint8").transpose(1, 2, 0))

    prompt = expression.strip().rstrip(".").lower()
    if not prompt:
        prompt = "object"
    text_query = f"{prompt} ."

    device = det.get("device", "cpu")
    processor = det["processor"]
    model = det["model"]

    inputs = processor(images=img, text=text_query, return_tensors="pt")
    inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    target_sizes = [(img.height, img.width)]
    results = processor.post_process_grounded_object_detection(
        outputs, inputs["input_ids"], threshold=0.25, text_threshold=0.25,
        target_sizes=target_sizes)[0]

    objects = []
    for score, box, label in zip(results["scores"], results["boxes"], results["text_labels"]):
        b = [round(float(v), 2) for v in box.tolist()]
        objects.append({
            "id": f"obj_{uuid.uuid4().hex[:6]}",
            "class_label": str(label).strip(),
            "bbox_pixel": b,
            "geometry_wgs84": None,  # bbox→polygon conversion below
            "mask_encoding": "polygon",
            "confidence": round(float(score), 4),
        })

    if objects:
        # convert pixel boxes → WGS84 polygons via the affine transform
        data = graster.read_raster(image)
        import geopandas as gpd
        from shapely.geometry import mapping as geom_mapping
        geoms = []
        for o in objects:
            x0, y0, x1, y1 = o["bbox_pixel"]
            t = data["transform"]
            corners = [t * (x0, y0), t * (x1, y0), t * (x1, y1), t * (x0, y1)]
            geoms.append(shp_box(min(c[0] for c in corners), min(c[1] for c in corners),
                                 max(c[0] for c in corners), max(c[1] for c in corners)))
        gdf = gpd.GeoDataFrame(objects, geometry=geoms, crs=data["crs"]).to_crs(4326)
        for o, geom in zip(objects, gdf.geometry):
            o["geometry_wgs84"] = geom_mapping(geom)

    return {"objects": objects, "note": None if objects else "no matching objects found",
            "mode": "grounding_dino", "confidence": 0.8 if objects else 0.4,
            "uncertainty": []}
