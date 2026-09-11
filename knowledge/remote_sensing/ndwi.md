# NDWI — Normalized Difference Water Index (McFeeters)

Open-surface water absorbs strongly in the NIR while reflecting in green:

    NDWI = (Green − NIR) / (Green + NIR + ε)

For Sentinel-2: Green = B03, NIR = B08. NDWI > 0 is the conventional
open-water class; values ≤ 0 indicate vegetation/soil/buildings.

## Distinguishing water from shadow

Dark built areas and terrain shadow can also score NDWI > 0. Practical
refinements:

- Require Blue band reflectance above a floor (deep shadow is dark in ALL
  bands; water retains some green/blue reflectance).
- Cross-check with SAR: standing water appears as a very dark, smooth VV
  backscatter target (typically < −18 dB) — shadow does not change the radar
  return.
- For turbid/flooded vegetation, consider the XU index variant
  (Green − SWIR1)/(Green + SWIR1) using B11.

## Flood mapping workflow

1. NDWI before / NDWI after on a co-registered pair.
2. Water gain = (NDWI_after > 0) & (NDWI_before ≤ 0).
3. Cross-validate with S1 VV decrease over the same footprint — flood water
   drops VV by ~5–8 dB versus dry land.
