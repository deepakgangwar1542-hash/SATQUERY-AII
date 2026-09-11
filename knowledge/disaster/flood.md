# Disaster response — flood & damage assessment with EO data

## Flood extent (optical + SAR)

1. Acquire closest cloud-free S2 scene before/after the event, plus S1 GRD
   pairs (S1 is the primary flood sensor — ignores clouds).
2. Optical: NDWI water-gain mask (B03/B08, McFeeters).
3. SAR: VV threshold or change (water = VV < −18 dB; ΔVV < −5 dB vs pre-event).
4. Fuse: intersection = high-confidence water; union with disagreement flag
   = uncertain (wind roughening, turbidity, shadow).
5. Report area_km² in a metric CRS, per settlement/river segment if possible.

## Building damage (bi-temporal)

- Optical pair: collapse/changes in texture; NDVI loss if vegetation removed.
- SAR pair: damaged structures lose double-bounce → VV drop in built areas;
  debris fields raise cross-pol VH locally.
- Interpret ONLY over footprints of known buildings (run detection first,
  then restrict change statistics to building masks).

## Common failure modes

| Symptom | Cause |
|---|---|
| Flood "appears" on hillsides | Terrain shadow classified as water |
| Flood extent flickers between passes | Wind roughening / incidence-angle differences |
| Change everywhere | Poor co-registration; always reproject to common grid first |
| Vegetation loss in clouds | Cloud/shadow misread as surface change — apply SCL mask |

## Reporting discipline

State sensor, dates, cloud fraction, thresholds, and resampling method with
every product. Cross-check at least two independent signals before declaring
damage; downgrade confidence when only one sensor supports the claim.
