# SatQuery AI — Autonomous Multimodal Earth Observation Investigation System

[![SIH26167 Compliant](https://img.shields.io/badge/SIH26167-Autonomous%20Geospatial%20AI-0284c7.svg)](https://github.com/deepakgangwar1542-hash/SATQUERY-AII)
[![License](https://img.shields.io/badge/License-Apache%202.0%20%2F%20MIT-emerald.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Cesium](https://img.shields.io/badge/CesiumJS-Self--Hosted-indigo.svg)](https://cesium.com/)

**SatQuery AI** transforms satellite intelligence from a static tool-driven dashboard into an **autonomous Earth-observation investigation system**:
> *"Don't tell SatQuery which tool to use. Tell SatQuery what you want to know."*

Instead of brittle keyword dispatching, SatQuery compiles user queries into structured investigation specifications, dynamically selects sensors based on atmospheric and task conditions, coordinates specialist neural and radar models, computes spatial metrics deterministically via sandboxed GIS, verifies evidence consistency, and provides interactive visual proof through an **Evidence Lens** and **Provenance Graph**.

Queries can be typed or **spoken** (browser Web Speech API). Every result surfaces *how* the query was interpreted (the compiled `earthquery_spec` and query understanding), a **6-component confidence breakdown**, and a **clickable execution-provenance chain** built from the real agent trace — no step or number is fabricated.

---

## 1. Product Philosophy & Core Architecture

```
                       USER QUERY
                           ↓
                  EARTHQUERY COMPILER
            (22+ Intent Taxonomy & IR Specs)
                           ↓
                 INVESTIGATION PLANNER
          (Autonomous Graph of Evidence Steps)
                           ↓
                    SENSOR SELECTION
      (Optical / SAR / Fusion based on Cloud Contamination)
                           ↓
                    MODEL REGISTRY
        (Real Checkpoints vs Disclosed Fallbacks)
                           ↓
                  HYPOTHESIS GENERATION
         (Candidate Explanations for Alteration)
                           ↓
                   SPECIALIST ANALYSIS
        ├─ Optical Perception & Zero-Shot Grounding
        ├─ Neural Siamese U-Net Change Detection (LEVIR-CD)
        ├─ Polarimetric SAR Analysis (VV/VH, ENL, Inundation)
        └─ Domain Knowledge Retrieval (SOPs & Guidelines)
                           ↓
              DETERMINISTIC GEOSPATIAL REASONING
       (Exact Shapely/GeoPandas Intersections & Metrics)
                           ↓
                    EVIDENCE FUSION
             (Typed Multi-Source Provenance)
                           ↓
              VERIFICATION & CONFLICT LOOP
                 /                   \
            [CONFLICT]            [AGREE]
                ↓                    ↓
         SELF-CORRECTING           ANSWER
           RE-PLANNING               ↓
                ↓             EVIDENCE-GROUNDED
          VERIFY AGAIN          INTERACTIVE PROOF
                               (Evidence Lens)
```

---

## 2. Key Capabilities & Innovations

### A. EarthQuery Compiler (`backend/services/earthquery/compiler.py`)
- Translates natural language into a validated Pydantic specification (`EarthQuerySpec`).
- Supports 22+ task intents: `flood_impact_change`, `hypothesis_investigation`, `anomaly_detection`, `building_count`, `temporal_change`, `optical_sar_comparison`, `urban_change`, `vegetation_change`, etc.
- Extracts temporal scopes (e.g., `"Between June and August"`), target objects, required operations, and verification policies.

### B. Autonomous Sensor Selection (`backend/services/earthquery/sensor_selector.py`)
- Dynamically selects sensors without hardcoding:
  - **High cloud cover (>20%)**: Elevates all-weather **SAR** (Sentinel-1 / radar) to primary sensor.
  - **Specular water / flood tasks**: Dual-sensor fusion (SAR backscatter drop for water delineation + optical for land-cover context).
  - **Zero-shot feature delineation**: High-resolution optical spectral bands.

### C. True Neural Change Detection with Honest Fallback (`backend/agents/change.py`)
- **Neural Inference**: Runs genuine PyTorch inference using `SiameseChangeNet` with weights from `models/checkpoints/change_detector/siamese_unet_levircd.pt`, producing calibrated probability maps and vectorized change polygons.
- **Honest Fallback**: If checkpoint or PyTorch is unavailable, degrades to `mode: "heuristic_fallback"` with model name `ndvi_delta_fallback`. **Never labels heuristic output as a neural model.**

### D. SAR Intelligence Specialist (`backend/agents/sar.py`)
- Physics-based radar remote sensing:
  - Equivalent Number of Looks (ENL) and speckle estimation.
  - Polarimetric cross-ratio (VV/VH) and noise floor analysis.
  - Specular reflection thresholding (< -18 dB) for open water.
  - Bi-temporal SAR backscatter drop (> 3.5 dB) for confirmed all-weather flood inundation.
  - Clear documentation of physical radar limitations (shadow, layover, dense canopy double-bounce).

### E. Multi-Hypothesis Engine (`backend/agents/hypothesis_engine.py`)
- For complex queries like *"What caused the major change in this region?"*, evaluates competing hypotheses:
  - **H1**: Flooding & Hydrological Inundation
  - **H2**: Urban Development & Construction
  - **H3**: Vegetation Loss & Agricultural Clearance
  - **H4**: Acquisition Artifact & Cloud Contamination
- Calculates evidence support scores deterministically and reports correlation without false causal certainty.

### F. Deterministic Geospatial Reasoning (`backend/geospatial/engine.py` & `dsl.py`)
- LLMs are prohibited from hallucinating numerical counts or areas.
- Sandboxed GIS engine performs exact spatial intersections (`intersects`, `buffer`, metric UTM area projections) using Shapely and GeoPandas.
- Verified intermediate representation (IR) supporting `BUILDING_COUNT`, `FLOOD_EXTENT`, `SPATIAL_INTERSECTION`, `BUFFER_QUERY`, etc.

### G. Evidence Lens & Provenance Graph (Frontend)
- **Claim-to-Evidence Linking**: Every claim in the final answer is linked to verifiable backend `EvidenceItem` IDs.
- **Show Evidence**: Inspect exact raster overlays, GeoJSON footprints, SAR metrics, and sensor selection rationales directly on the 3D Cesium globe.
- **Evidence Provenance Graph**: Interactive DAG visualizer tracing Query → Sensor Selection → Model Inference → GIS Intersection → Final Answer.

---

## 3. Quickstart (Local Development)

### 1. Backend Setup
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt

# Run server with live reload
uvicorn backend.main:app --port 8000 --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run build      # Verifies TypeScript & Vite production build
npm run dev        # Starts interactive UI at http://localhost:5173
```

### 3. Running Automated Tests
```bash
# Run all unit tests (compiler, sensor selector, SAR, hypothesis, GIS engine)
.venv\Scripts\python -m pytest tests/unit/ -v

# Run contract and integration tests
.venv\Scripts\python -m pytest tests/contract/ tests/integration/ -v
```

---

## 4. Primary Product Modes

The user interface exposes 3 contextual modes:
1. **ASK**: Direct questions with grounding and VQA evidence.
2. **INVESTIGATE**: Autonomous multi-step investigation, sensor selection, SAR/optical fusion, and GIS intersection.
3. **EXPLORE**: Interactive 3D Cesium globe exploration with temporal slider and Click-to-Ask Earth region queries.

---

## 5. End-to-End Demo Workflows

### Demo Query 1 (Flood Impact & Affected Buildings)
```
"Between June and August, identify areas where flooding increased and tell me how many buildings were affected."
```
1. **Compiler**: Identifies `flood_impact_change`, extracts June → August temporal window, targets `buildings`.
2. **Sensor Selection**: Detects optical cloud coverage; prioritizes SAR for specular water penetration while keeping optical for building footprint context.
3. **Model Execution**: Runs `predict_siamese_change()` on neural Siamese U-Net (or honest fallback) + SAR bi-temporal backscatter analysis.
4. **GIS Reasoning**: Projects to metric UTM CRS; intersects flood polygon mask with detected building footprints.
5. **Output**: Computes exact numeric building count deterministically and presents claims linked to Evidence Lens.

### Demo Query 2 (Hypothesis Investigation)
```
"What caused the major change in this region?"
```
1. **Compiler**: Identifies `hypothesis_investigation` intent.
2. **Hypothesis Engine**: Formulates candidate hypotheses (H1 Flooding, H2 Urban Development, H3 Vegetation Loss, H4 Artifact).
3. **Evidence Fusion**: Scores hypotheses against collected SAR water drop, optical spectral indices, and building detections.
4. **Output**: Ranks hypotheses with support scores and transparent limitations.

### Demo Query 3 (Anomaly Hunter)
```
"Find anything unusual in this region."
```
1. **Compiler**: Identifies `anomaly_detection` intent.
2. **Scanner**: Runs multispectral spectral anomaly scans and polarimetric backscatter analysis.
3. **Output**: Surfaces ranked anomalies with clickable investigation workflows.

---

## 6. Honest Model vs. Fallback Disclosure

| Specialist Capability | Active Checkpoint / Engine | Honest Fallback Mode |
|---|---|---|
| **Change Detection** | `siamese_unet_levircd.pt` (PyTorch) | `ndvi_delta_fallback` (`mode: "heuristic_fallback"`) |
| **Object Grounding** | `GroundingDINO` checkpoint (HF Hub) | Color/spectral index thresholding with geometric polygonization |
| **VQA / Captioning** | Local VLM checkpoint / HuggingFace | Scene profile analyzer with explicit perceptual limitations |
| **SAR Analysis** | Calibrated Sentinel-1 physics engine (VV/VH) | Single-polarization backscatter thresholding (< -18 dB) |
| **Geospatial Math** | Shapely & GeoPandas metric UTM projection | Deterministic WGS84 bounding intersection |

---

## 7. License & Compliance

Built for SIH26167 with 100% permissive runtime dependencies (MIT, Apache-2.0, BSD-3-Clause). Self-hosted CesiumJS requires zero proprietary cloud tokens.
