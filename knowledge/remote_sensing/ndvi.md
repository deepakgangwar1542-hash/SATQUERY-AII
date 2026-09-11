# NDVI — Normalized Difference Vegetation Index

NDVI exploits the strong contrast between red-band absorption (chlorophyll)
and NIR-band reflectance (leaf cell structure) of healthy vegetation:

    NDVI = (NIR − Red) / (NIR + Red + ε)

For Sentinel-2 L2A: NIR = B08 (10 m), Red = B04 (10 m); ε ≈ 1e-8 avoids
division by zero. Values range −1..+1:

| Range | Typical meaning |
|---|---|
| < 0 | Water, snow, cloud shadow |
| 0 – 0.2 | Bare soil, rock, built-up |
| 0.2 – 0.4 | Sparse grass / shrub |
| 0.4 – 0.8 | Moderate-to-dense vegetation |
| > 0.8 | Very dense, vigorous vegetation (rare) |

## Change analysis between two dates

Pixel-wise relative decrease (the definition SatQuery uses for
"decreased by more than X%"):

    ((NDVI_before − NDVI_after) / (|NDVI_before| + ε)) > X/100

Guard: pixels with |NDVI_before| < 0.05 are excluded — near-zero denominators
amplify sensor noise into fake "changes".

## Caveats

- Soil background and atmospheric residue influence low-vegetation pixels;
  prefer S2 L2A (BOA) over L1C (TOA) for change work.
- NDVI saturates over dense canopies; for biomass studies consider indices
  like EVI or red-edge bands (B05–B07).
- Never assume a fixed band position: resolve B04/B08 from metadata each time
  (stacking order varies between products).
