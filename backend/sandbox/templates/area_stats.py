"""Sandbox template: single-date index statistics (intent `area_stats`).

Computes mean NDVI/NDWI and class shares (vegetation / water / other) for one
optical raster, per the §10.2 index formulas.
"""
import json

import numpy as np
import rasterio

EPS = 1e-8


def _band_index(mapping, name):
    if mapping and name in mapping:
        return int(mapping[name])
    raise KeyError(f"band {name} missing from mapping {mapping}")


with open("input/params.json", encoding="utf-8") as fh:
    params = json.load(fh)
mapping = params.get("band_mapping") or {}

with rasterio.open(params["optical"]) as src:
    arr = src.read().astype("float32")
    transform, crs = src.transform, src.crs

nir = arr[_band_index(mapping, "B08") - 1]
red = arr[_band_index(mapping, "B04") - 1]
green = arr[_band_index(mapping, "B03") - 1]
ndvi = (nir - red) / (nir + red + EPS)
ndwi = (green - nir) / (green + nir + EPS)

valid = np.isfinite(ndvi) & np.isfinite(ndwi)
pixel_area_m2 = abs(transform.a * transform.e)
n_valid = int(valid.sum())
veg = int(((ndvi > 0.3) & valid).sum())
water = int(((ndwi > 0.0) & valid).sum())

result = {
    "intent": "area_stats",
    "statistics": {
        "mean_ndvi": round(float(np.nanmean(ndvi[valid])), 4) if n_valid else None,
        "mean_ndwi": round(float(np.nanmean(ndwi[valid])), 4) if n_valid else None,
        "class_breakdown": {
            "vegetation_km2": round(veg * pixel_area_m2 / 1e6, 6),
            "water_km2": round(water * pixel_area_m2 / 1e6, 6),
            "total_km2": round(n_valid * pixel_area_m2 / 1e6, 6),
        },
        "vegetation_percent": round(100.0 * veg / n_valid, 2) if n_valid else 0.0,
        "water_percent": round(100.0 * water / n_valid, 2) if n_valid else 0.0,
    },
    "crs": str(crs),
}
with open("output/result.json", "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2)
