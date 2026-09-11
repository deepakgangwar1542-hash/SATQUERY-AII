# Sentinel-1 — SAR fundamentals for fusion work

C-band (5.4 GHz) synthetic-aperture radar; imaging in all weather, day and
night. GRD products distributed as VV+VH (dual pol) or VV-only.

## Backscatter intuition (VV, dB)

| Surface | Typical VV |
|---|---|
| Calm open water | −25 … −18 dB (specular reflection away) |
| Bare smooth soil | −18 … −14 dB |
| Vegetation | −14 … −9 dB (volume scattering) |
| Urban / structures | −8 … +2 dB (double-bounce) |

VH (cross-pol) sits ~5–9 dB below VV over most natural surfaces; the VV−VH
ratio rises with vegetation structure and urban density.

## Interpretation rules of thumb

- Flood mapping: water gain → sharp VV DROP; confirm with NDWI optical gain.
- Deforestation/land clearing: forest → bare ⇒ VV drop of 3–6 dB plus VH drop.
- New construction: strong VV RISE (double-bounce) plus coherence loss.
- Wind-roughened water raises VV toward bare-soil levels — a known false
  negative for flood mapping.

## Preprocessing chain (training-time)

Apply orbit file → thermal-noise removal → calibration to γ⁰ → speckle
filtering (e.g., Lee 5×5) → terrain flattening → dB conversion. For quick
demo inference on already-dB GRD patches, clipping to [−35, 5] dB suffices.

## Speckle caveat

SAR intensity is inherently speckled; single-pixel comparisons are noise.
Compare region statistics (means over ≥ 30–50 px) or apply multilooking.
SAR reliability scoring should account for speckle-dominated areas.
