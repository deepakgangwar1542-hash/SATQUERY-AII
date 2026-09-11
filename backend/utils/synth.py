"""Synthetic Sentinel-2/Sentinel-1-like GeoTIFF generator.

Used by tests, the eval scripts' smoke mode, and `scripts/make_sample_data.py`
so the whole system round-trips without downloading real Copernicus imagery.
Band layout matches the §10.6 4-band optical convention: B02, B03, B04, B08
(DN 0..10000, like L2A) and a 2-band SAR stack (VV, VH).
"""
from __future__ import annotations

import numpy as np
import rasterio
from rasterio.transform import from_origin


def _optical_scene(seed: int, size: int, vegetation_frac: float = 0.55,
                   water_frac: float = 0.15) -> np.ndarray:
    """4-band scene: vegetation block, water block, bare soil elsewhere."""
    rng = np.random.default_rng(seed)
    bands = rng.normal(1200, 90, size=(4, size, size)).clip(0, 4000)
    veg_h = int(size * vegetation_frac)
    wat_w = int(size * water_frac)
    # vegetation (left block): low Red, high NIR
    bands[0, :, :veg_h] = rng.normal(700, 60, (size, veg_h))      # B02 blue
    bands[1, :, :veg_h] = rng.normal(900, 60, (size, veg_h))      # B03 green
    bands[2, :, :veg_h] = rng.normal(600, 50, (size, veg_h))      # B04 red
    bands[3, :, :veg_h] = rng.normal(3800, 150, (size, veg_h))    # B08 nir
    # water (top strip of the right block): high Blue/Green, low NIR
    bands[0, :wat_w, veg_h:] = rng.normal(1400, 60, (wat_w, size - veg_h))
    bands[1, :wat_w, veg_h:] = rng.normal(1500, 60, (wat_w, size - veg_h))
    bands[2, :wat_w, veg_h:] = rng.normal(800, 50, (wat_w, size - veg_h))
    bands[3, :wat_w, veg_h:] = rng.normal(500, 60, (wat_w, size - veg_h))
    return bands.astype("float32")


def _sar_scene(seed: int, size: int, vegetation_frac: float = 0.55) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vv = rng.normal(-14.0, 1.5, (size, size))   # dB-ish
    vh = vv - rng.normal(8.0, 1.0, (size, size))
    veg_h = int(size * vegetation_frac)
    vv[:, :veg_h] = rng.normal(-11.0, 1.5, (size, veg_h))
    vh[:, :veg_h] = vv[:, :veg_h] - rng.normal(7.0, 1.0, (size, veg_h))
    return np.stack([vv, vh]).astype("float32")


def write_pair(out_dir: str, size: int = 512, changed_frac: float = 0.25,
               crs: str = "EPSG:32643") -> dict[str, str]:
    """Write an optical before/after pair + SAR pair with a known change:
    a rectangle where vegetation is removed (NDVI drops) in the `after` scene.

    Returns {"optical_before", "optical_after", "sar_before", "sar_after"}.
    """
    from pathlib import Path
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    transform = from_origin(310000.0, 4100000.0, 10.0, 10.0)  # 10 m pixels, UTM
    profile = {
        "driver": "GTiff", "width": size, "height": size, "count": 4,
        "dtype": "float32", "crs": crs, "transform": transform,
        "nodata": 0, "compress": "deflate",
    }
    band_names = ["B02", "B03", "B04", "B08"]

    before = _optical_scene(seed=42, size=size)
    after = _optical_scene(seed=43, size=size)
    # Simulate construction/deforestation: vegetation removed in a rectangle.
    h0, h1 = int(size * 0.1), int(size * (0.1 + changed_frac))
    w0, w1 = int(size * 0.05), int(size * 0.45)
    after[0, h0:h1, w0:w1] = 1500.0
    after[1, h0:h1, w0:w1] = 1600.0
    after[2, h0:h1, w0:w1] = 1700.0
    after[3, h0:h1, w0:w1] = 1900.0   # NIR collapses → NDVI drop

    paths: dict[str, str] = {}
    for name, arr in (("optical_before", before), ("optical_after", after)):
        p = out / f"{name}.tif"
        with rasterio.open(p, "w", **profile) as dst:
            dst.write(arr)
            dst.descriptions = tuple(band_names)
            dst.update_tags(1, NAME=band_names[0])
            for i, bname in enumerate(band_names, start=1):
                dst.update_tags(i, BAND_NAME=bname)
            dst.update_tags(SENSOR="SENTINEL-2", PRODUCT="L2A")
        paths[name] = str(p)

    sar_profile = dict(profile, count=2)
    sar_before = _sar_scene(seed=44, size=size)
    sar_after = _sar_scene(seed=45, size=size)
    # Structural change → backscatter shift in the changed rectangle.
    sar_after[0, h0:h1, w0:w1] = -6.0
    sar_after[1, h0:h1, w0:w1] = -13.0
    for name, arr in (("sar_before", sar_before), ("sar_after", sar_after)):
        p = out / f"{name}.tif"
        with rasterio.open(p, "w", **sar_profile) as dst:
            dst.write(arr)
            dst.descriptions = ("VV", "VH")
        paths[name] = str(p)

    return paths
