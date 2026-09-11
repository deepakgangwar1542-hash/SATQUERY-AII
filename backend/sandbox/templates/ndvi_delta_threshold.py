"""Sandbox template: NDVI-delta threshold analysis (intent `ndvi_delta_threshold`).

Runs INSIDE the sandbox with no network. Reads input/params.json and the
approved input rasters; writes output/result.json and output/output.geojson.

Formula (PRD §10.2):
    NDVI = (NIR - Red) / (NIR + Red + eps),  NIR = B08, Red = B04
    relative decrease = (before - after) / (|before| + eps) > threshold_fraction
Pixels with |NDVI_before| < min_magnitude are excluded (divide-by-near-zero
guard, documented per PRD §10.2).
"""
import json

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes as raster_shapes
from shapely.geometry import shape

EPS = 1e-8


def _band_index(mapping, name):
    if mapping and name in mapping:
        return int(mapping[name])
    raise KeyError(f"band {name} missing from mapping {mapping}")


with open("input/params.json", encoding="utf-8") as fh:
    params = json.load(fh)

threshold_fraction = abs(float(params.get("threshold_pct", -20.0))) / 100.0
min_magnitude = float(params.get("min_magnitude", 0.05))
mapping = params.get("band_mapping") or {}

with rasterio.open(params["optical_before"]) as src_b:
    arr_b = src_b.read().astype("float32")
    transform, crs = src_b.transform, src_b.crs
with rasterio.open(params["optical_after"]) as src_a:
    arr_a = src_a.read().astype("float32")

nir_b, red_b = arr_b[_band_index(mapping, "B08") - 1], arr_b[_band_index(mapping, "B04") - 1]
nir_a, red_a = arr_a[_band_index(mapping, "B08") - 1], arr_a[_band_index(mapping, "B04") - 1]
ndvi_b = (nir_b - red_b) / (nir_b + red_b + EPS)
ndvi_a = (nir_a - red_a) / (nir_a + red_a + EPS)

rel = (ndvi_b - ndvi_a) / (np.abs(ndvi_b) + EPS)
loss = (rel > threshold_fraction) & (np.abs(ndvi_b) >= min_magnitude)
rel_gain = (ndvi_a - ndvi_b) / (np.abs(ndvi_b) + EPS)
gain = (rel_gain > threshold_fraction) & (np.abs(ndvi_b) >= min_magnitude)
valid = np.isfinite(ndvi_b) & np.isfinite(ndvi_a)

polygons = []
for mask, cls in ((loss, "vegetation_loss"), (gain, "vegetation_gain")):
    m = (mask & valid).astype("uint8")
    for geom, _val in raster_shapes(m, mask=m.astype(bool), transform=transform):
        polygons.append({"change_class": cls, "geometry": shape(geom)})

pixel_area_m2 = abs(transform.a * transform.e)
n_valid = int(valid.sum())
n_loss = int((loss & valid).sum())
n_gain = int((gain & valid).sum())

result = {
    "intent": "ndvi_delta_threshold",
    "threshold_pct": params.get("threshold_pct", -20.0),
    "min_magnitude_guard": min_magnitude,
    "compared_pixels": n_valid,
    "statistics": {
        "area_km2": round(n_loss * pixel_area_m2 / 1e6, 6),
        "percent_of_aoi": round(100.0 * n_loss / n_valid, 3) if n_valid else 0.0,
        "class_breakdown": {
            "vegetation_loss_km2": round(n_loss * pixel_area_m2 / 1e6, 6),
            "vegetation_gain_km2": round(n_gain * pixel_area_m2 / 1e6, 6),
            "total_compared_km2": round(n_valid * pixel_area_m2 / 1e6, 6),
        },
    },
    "crs": str(crs),
}
with open("output/result.json", "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2)

if polygons:
    gdf = gpd.GeoDataFrame(polygons, geometry="geometry", crs=crs).to_crs(4326)
    fc = json.loads(gdf.to_json())
else:
    fc = {"type": "FeatureCollection", "features": []}
with open("output/output.geojson", "w", encoding="utf-8") as fh:
    json.dump(fc, fh)
