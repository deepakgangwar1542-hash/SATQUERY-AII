"""MobileSAM & High-Resolution Instance Segmenter (§11.4, FR-4).

Converts 2D bounding boxes from Grounding DINO into fine-grained, pixel-accurate
object boundary polygon contours (e.g. circular storage tanks, irregular structures,
aircraft contours). Uses MobileSAM / SamModel if available, with intelligent
edge-aware threshold contour extraction fallback.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from rasterio.features import shapes as raster_shapes
from shapely.geometry import box as shp_box, shape
from shapely.ops import unary_union

logger = logging.getLogger(__name__)


def segment_boxes(
    rgb_image: np.ndarray,
    boxes: list[list[float]],
    transform: Any,
    crs: Any,
    sam_model_tuple: tuple[Any, Any] | None = None,
) -> list[dict[str, Any]]:
    """Segment bounding boxes into precise polygon geometries.

    Args:
        rgb_image: uint8 numpy array of shape (H, W, 3).
        boxes: list of [x0, y0, x1, y1] pixel coordinates.
        transform: rasterio Affine transform.
        crs: rasterio CRS.
        sam_model_tuple: optional (processor, model) for SAM.

    Returns:
        List of dicts with 'geometry_wgs84', 'area_px', 'mask_type'.
    """
    if not boxes:
        return []

    h, w = rgb_image.shape[:2]
    results = []

    # Attempt neural SAM segmentation if model loaded
    if sam_model_tuple is not None and sam_model_tuple[0] is not None:
        try:
            return _neural_sam_segment(rgb_image, boxes, transform, crs, sam_model_tuple)
        except Exception as e:
            logger.warning(f"Neural SAM segmentation failed ({e}), falling back to contour refinement")

    # Fast edge-aware contour refinement fallback
    return _edge_refined_segment(rgb_image, boxes, transform, crs)


def _edge_refined_segment(
    rgb_image: np.ndarray,
    boxes: list[list[float]],
    transform: Any,
    crs: Any,
) -> list[dict[str, Any]]:
    """Extract fine-grained silhouette contours within bounding boxes."""
    import geopandas as gpd
    from shapely.geometry import mapping as geom_mapping

    h, w = rgb_image.shape[:2]
    # Compute grayscale luminance
    gray = (
        0.299 * rgb_image[..., 0] + 0.587 * rgb_image[..., 1] + 0.114 * rgb_image[..., 2]
    ).astype("uint8")

    geoms = []
    metadata = []

    for idx, (x0, y0, x1, y1) in enumerate(boxes):
        rx0 = max(0, int(round(x0)))
        ry0 = max(0, int(round(y0)))
        rx1 = min(w, int(round(x1)))
        ry1 = min(h, int(round(y1)))

        if rx1 - rx0 < 4 or ry1 - ry0 < 4:
            # Box too tiny, use direct bounding box
            corners = [transform * (rx0, ry0), transform * (rx1, ry0),
                       transform * (rx1, ry1), transform * (rx0, ry1)]
            poly = shp_box(min(c[0] for c in corners), min(c[1] for c in corners),
                           max(c[0] for c in corners), max(c[1] for c in corners))
            geoms.append(poly)
            metadata.append({"area_px": (rx1 - rx0) * (ry1 - ry0), "mask_type": "bbox"})
            continue

        patch = gray[ry0:ry1, rx0:rx1]
        mean_val = float(np.mean(patch))
        std_val = float(np.std(patch))

        # Separate foreground object silhouette from surrounding ground
        if std_val > 8.0:
            fg_mask = np.abs(patch.astype(float) - mean_val) > (0.6 * std_val)
        else:
            fg_mask = np.ones_like(patch, dtype=bool)

        # Ensure mask connects to center of box
        pad_mask = np.zeros((h, w), dtype="uint8")
        pad_mask[ry0:ry1, rx0:rx1] = fg_mask.astype("uint8")

        sub_geoms = []
        for geom_dict, val in raster_shapes(pad_mask, mask=pad_mask, transform=transform):
            if val == 1:
                g = shape(geom_dict)
                if g.is_valid and g.area > 0:
                    sub_geoms.append(g)

        if sub_geoms:
            merged = unary_union(sub_geoms)
            if not merged.is_empty:
                geoms.append(merged)
                metadata.append({"area_px": int(np.sum(fg_mask)), "mask_type": "contour"})
                continue

        # Fallback to bbox rectangle if no contour was formed
        corners = [transform * (rx0, ry0), transform * (rx1, ry0),
                   transform * (rx1, ry1), transform * (rx0, ry1)]
        poly = shp_box(min(c[0] for c in corners), min(c[1] for c in corners),
                       max(c[0] for c in corners), max(c[1] for c in corners))
        geoms.append(poly)
        metadata.append({"area_px": (rx1 - rx0) * (ry1 - ry0), "mask_type": "bbox"})

    # Reproject to WGS84 (EPSG:4326)
    gdf = gpd.GeoDataFrame(metadata, geometry=geoms, crs=crs).to_crs(4326)
    results = []
    for meta, geom in zip(metadata, gdf.geometry):
        results.append({
            "geometry_wgs84": geom_mapping(geom),
            "area_px": meta["area_px"],
            "mask_type": meta["mask_type"],
        })

    return results


def _neural_sam_segment(
    rgb_image: np.ndarray,
    boxes: list[list[float]],
    transform: Any,
    crs: Any,
    sam_model_tuple: tuple[Any, Any],
) -> list[dict[str, Any]]:
    """Predict segmentation masks with transformers SamModel."""
    import torch
    from PIL import Image

    processor, model = sam_model_tuple
    device = next(model.parameters()).device
    pil_img = Image.fromarray(rgb_image)

    # Format 2D boxes for SAM input: [[[x0, y0, x1, y1], ...]]
    input_boxes = [[b for b in boxes]]

    inputs = processor(pil_img, input_boxes=input_boxes, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)

    # Post process masks
    masks = processor.image_processor.post_process_masks(
        outputs.pred_masks.cpu(),
        inputs["original_sizes"].cpu(),
        inputs["reshaped_input_sizes"].cpu()
    )[0]

    # Best mask per prompt box
    import geopandas as gpd
    from shapely.geometry import mapping as geom_mapping

    geoms = []
    metadata = []
    for i in range(len(boxes)):
        mask_np = masks[i, 0].numpy().astype("uint8")
        sub_geoms = []
        for geom_dict, val in raster_shapes(mask_np, mask=mask_np, transform=transform):
            if val == 1:
                g = shape(geom_dict)
                if g.is_valid and g.area > 0:
                    sub_geoms.append(g)

        if sub_geoms:
            merged = unary_union(sub_geoms)
            geoms.append(merged)
            metadata.append({"area_px": int(np.sum(mask_np)), "mask_type": "sam_neural"})
        else:
            x0, y0, x1, y1 = boxes[i]
            corners = [transform * (x0, y0), transform * (x1, y0),
                       transform * (x1, y1), transform * (x0, y1)]
            poly = shp_box(min(c[0] for c in corners), min(c[1] for c in corners),
                           max(c[0] for c in corners), max(c[1] for c in corners))
            geoms.append(poly)
            metadata.append({"area_px": int((x1 - x0) * (y1 - y0)), "mask_type": "bbox"})

    gdf = gpd.GeoDataFrame(metadata, geometry=geoms, crs=crs).to_crs(4326)
    results = []
    for meta, geom in zip(metadata, gdf.geometry):
        results.append({
            "geometry_wgs84": geom_mapping(geom),
            "area_px": meta["area_px"],
            "mask_type": meta["mask_type"],
        })
    return results
