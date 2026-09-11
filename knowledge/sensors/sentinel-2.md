# Sentinel-2 — bands, products, and conventions

Copernicus Sentinel-2 (MSI) multispectral mission, 290 km swath, 5-day
revisit (two satellites).

## Key bands (L2A surface reflectance, scaled ×10000 DN)

| Band | Center | Resolution | Use |
|---|---|---|---|
| B02 Blue | 490 nm | 10 m | true color, water |
| B03 Green | 560 nm | 10 m | NDWI |
| B04 Red | 665 nm | 10 m | NDVI |
| B08 NIR | 842 nm | 10 m | NDVI / NDWI |
| B8A NIR narrow | 865 nm | 20 m | red-edge analyses |
| B11 SWIR1 | 1610 nm | 20 m | fire scars, moisture |
| B12 SWIR2 | 2190 nm | 20 m | burnt area |
| SCL | — | 20 m | scene classification / QA |

## Band-order pitfall

There is NO universal stacking order for "a Sentinel-2 GeoTIFF": SAFE
products order bands by wavelength, analysis stacks vary (4-band RGB+NIR,
12-band L2A, BigEarthNet uses 12 bands in a specific order…). Any code that
hardcodes `array[3]` as NIR is a latent bug. Resolve bands from
`descriptions`/`tags` when present, else the §10.6 convention table, else
require an explicit user mapping.

## Cloud handling

Prefer the SCL band (classes 8/9/10 = cloud medium/high/cirrus, 3 = shadow)
when present; fall back to a brightness/NIR heuristic and report cloud
fraction so sensor reliability can be penalized (§10.5).

## License

Copernicus Sentinel data: free and open; attribution to ESA/Copernicus is
required in published outputs.
