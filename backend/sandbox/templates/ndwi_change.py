"""Sandbox template: NDWI water change (intent `ndwi_change`).

NDWI (McFeeters, PRD §10.2) = (Green - NIR) / (Green + NIR + eps),
Green = B03, NIR = B08. Reports water loss and water gain polygons between
two dates using the same relative-change formula and near-zero guard as
ndvi_delta_threshold.
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

g_b, n_b = arr_b[_band_index(mapping, "B03") - 1], arr_b[_band_index(mapping, "B08") - 1]
g_a, n_a = arr_a[_band_index(mapping, "B03") - 1], arr_a[_band_index(mapping, "B08") - 1]
ndwi_b = (g_b - n_b) / (g_b + n_b + EPS)
ndwi_a = (g_a - n_a) / (g_a + n_a + EPS)

water_b, water_a = ndwi_b > 0.0, ndwi_a > 0.0
valid = np.isfinite(ndwi_b) & np.isfinite(ndwi_a)
loss = water_b & ~water_a & valid      # water → land
gain = ~water_b & water_a & valid      # land → water

polygons = []
for mask, cls in ((loss, "water_loss"), (gain, "water_gain")):
    m = mask.astype("uint8")
    for geom, _val in raster_shapes(m, mask=m.astype(bool), transform=transform):
        polygons.append({"change_class": cls, "geometry": shape(geom)})

pixel_area_m2 = abs(transform.a * transform.e)
n_loss, n_gain = int(loss.sum()), int(gain.sum())
result = {
    "intent": "ndwi_change",
    "statistics": {
        "area_km2": round(n_loss * pixel_area_m2 / 1e6, 6),
        "percent_of_aoi": round(100.0 * n_loss / (valid.sum() or 1), 3),
        "class_breakdown": {
            "water_loss_km2": round(n_loss * pixel_area_m2 / 1e6, 6),
            "water_gain_km2": round(n_gain * pixel_area_m2 / 1e6, 6),
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
