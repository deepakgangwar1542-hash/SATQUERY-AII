"""Geospatial & Disaster Response SOP Vector Store (RAG Layer).

Stores curated Standard Operating Procedures from international geospatial
authorities (UN-SPIDER, FEMA, Copernicus EMS, FAO). Uses dense sentence
embeddings to retrieve operational protocols and action recommendations for
detected anomalies.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from ..models import loaders
from ..services.job_store import DATA_DIR

RAG_DIR = DATA_DIR / "rag"
INDEX_PATH = RAG_DIR / "sop_index.json"

# Curated Geospatial & Disaster Response Standard Operating Procedures
CURATED_SOPS = [
    {
        "sop_id": "SOP-VEG-01",
        "title": "Bi-Temporal Deforestation & Canopy Loss Verification Protocol",
        "authority": "FAO / Copernicus Global Forest Watch",
        "domain": "forestry_and_land_cover",
        "keywords": ["vegetation", "deforestation", "forest", "tree", "canopy", "ndvi", "logging", "clearing"],
        "trigger_condition": "NDVI decrease exceeding 0.20 (20%) across bi-temporal observation window.",
        "summary": "Protocol for distinguishing anthropogenic deforestation from natural seasonal senescence.",
        "action_protocols": [
            "Confirm bi-temporal cloud contamination < 10% and verify geometric coregistration.",
            "Differentiate seasonal phenology: verify if adjacent control parcels exhibit similar spectral decline.",
            "If canopy loss > 1 km², flag parcel as priority for high-resolution validation.",
            "Estimate biomass degradation and notify environmental monitoring unit."
        ],
    },
    {
        "sop_id": "SOP-FLD-02",
        "title": "Flood Inundation Extent & Emergency Water Shift Protocol",
        "authority": "UN-SPIDER / FEMA Guidelines",
        "domain": "hydrology_and_disaster",
        "keywords": ["flood", "water", "inundation", "lake", "river", "overflow", "submerged", "ndwi"],
        "trigger_condition": "NDWI increase > 0.15 or SAR dual-pol backscatter drop below -18 dB indicating standing water.",
        "summary": "Rapid mapping procedure for flood emergency response and evacuation planning.",
        "action_protocols": [
            "Delineate maximum standing water perimeter using combined optical NDWI and SAR cross-polarization.",
            "Overlay transportation network to identify flooded access corridors and severed evacuation routes.",
            "Identify critical facilities (hospitals, power substations) within a 500m buffer of flooded zones.",
            "Generate standardized GeoJSON vector boundary for first-responder deployment units."
        ],
    },
    {
        "sop_id": "SOP-INF-03",
        "title": "Critical Infrastructure & Industrial Facility Grounding Protocol",
        "authority": "EPA / USACE Engineering Standards",
        "domain": "infrastructure_and_defense",
        "keywords": ["tank", "storage", "industrial", "facility", "building", "structure", "aircraft", "oil", "fuel"],
        "trigger_condition": "Zero-shot visual grounding localization of high-value industrial or transportation assets.",
        "summary": "Guidelines for auditing industrial storage tanks, containment perimeters, and defense structures.",
        "action_protocols": [
            "Verify secondary containment dikes around identified petroleum/chemical storage tanks.",
            "Calculate minimum 100m blast / separation radius from nearest residential or transport vectors.",
            "Compare historical imagery footprints to detect unauthorized facility expansions.",
            "Log exact WGS84 centroids and bounding contour geometries in geospatial registry."
        ],
    },
    {
        "sop_id": "SOP-FIRE-04",
        "title": "Wildfire Burn Scar Severity & Progression Assessment",
        "authority": "Copernicus Emergency Management Service (EMS)",
        "domain": "wildfire_and_hazards",
        "keywords": ["fire", "burn", "wildfire", "scar", "smoke", "thermal", "nbr"],
        "trigger_condition": "Normalized Burn Ratio (NBR) drop > 0.25 between pre-fire and post-fire rasters.",
        "summary": "Standard burn severity classification and post-fire erosion risk assessment.",
        "action_protocols": [
            "Classify burn severity into low, moderate, and high risk strata based on dNBR.",
            "Intersect steep slope topography (> 15 degrees) to identify post-fire mudslide risk zones.",
            "Identify watershed reservoirs downstream of burned catchments to alert water utilities.",
            "Prioritize aerial reseeding and slope stabilization measures."
        ],
    },
    {
        "sop_id": "SOP-AGR-05",
        "title": "Agricultural Drought & Vegetation Health Anomaly Protocol",
        "authority": "USDA / WMO Drought Monitoring Network",
        "domain": "agriculture_and_food_security",
        "keywords": ["drought", "crop", "agriculture", "soil", "dry", "yield", "stress", "vci"],
        "trigger_condition": "Vegetation Condition Index (VCI) < 35% indicating agricultural water stress.",
        "summary": "Operational assessment of cropland moisture deficit and seasonal crop failure risk.",
        "action_protocols": [
            "Assess historical multi-year NDVI percentiles to establish baseline drought anomalies.",
            "Correlate surface soil moisture proxies with crop phenological growth stages.",
            "Issue early warning advisory if regional moisture deficit persists beyond 21 days.",
            "Estimate potential yield impact across cultivated acreage."
        ],
    },
]

_CACHED_EMBEDDINGS: np.ndarray | None = None


def _get_sop_text(sop: dict) -> str:
    """Format SOP into a dense representation for semantic indexing."""
    actions = " ".join(sop.get("action_protocols", []))
    keywords = " ".join(sop.get("keywords", []))
    return f"{sop['title']}. {sop['summary']} Trigger: {sop['trigger_condition']} Keywords: {keywords} Protocols: {actions}"


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _build_or_load_index() -> np.ndarray:
    """Ensure SOP embeddings are computed and cached."""
    global _CACHED_EMBEDDINGS
    if _CACHED_EMBEDDINGS is not None:
        return _CACHED_EMBEDDINGS

    RAG_DIR.mkdir(parents=True, exist_ok=True)
    embedder, _ = loaders.load_embedding_model()

    texts = [_get_sop_text(sop) for sop in CURATED_SOPS]

    if embedder is not None:
        try:
            vecs = embedder.encode(texts, convert_to_numpy=True)
            _CACHED_EMBEDDINGS = vecs
            return vecs
        except Exception:
            pass

    # Fallback to keyword-based embedding if sentence-transformers is loading
    dim = 64
    vecs = []
    for sop in CURATED_SOPS:
        v = np.zeros(dim, dtype=np.float32)
        words = _get_sop_text(sop).lower().split()
        for i, w in enumerate(words[:dim]):
            v[i % dim] += hash(w) % 100 / 100.0
        vecs.append(v)
    _CACHED_EMBEDDINGS = np.array(vecs)
    return _CACHED_EMBEDDINGS


def retrieve_sops(query: str, top_k: int = 2) -> list[dict[str, Any]]:
    """Retrieve the most relevant SOP guidelines for a given query or observation.

    Returns a list of dicts with:
    - sop_id, title, authority, trigger_condition, action_protocols, similarity_score.
    """
    if not query or not query.strip():
        return []

    matrix = _build_or_load_index()
    embedder, _ = loaders.load_embedding_model()

    q_vec: np.ndarray | None = None
    if embedder is not None:
        try:
            q_vec = embedder.encode([query], convert_to_numpy=True)[0]
        except Exception:
            q_vec = None

    if q_vec is None:
        dim = 64
        q_vec = np.zeros(dim, dtype=np.float32)
        for i, w in enumerate(query.lower().split()[:dim]):
            q_vec[i % dim] += hash(w) % 100 / 100.0

    scores = []
    for i, sop_vec in enumerate(matrix):
        score = _cosine_similarity(q_vec, sop_vec)

        # Keyword boost if direct keywords appear in query
        q_lower = query.lower()
        keyword_hits = sum(1 for kw in CURATED_SOPS[i]["keywords"] if kw in q_lower)
        score += keyword_hits * 0.15

        scores.append((score, CURATED_SOPS[i]))

    # Rank by score
    scores.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, sop in scores[:top_k]:
        results.append({
            "sop_id": sop["sop_id"],
            "title": sop["title"],
            "authority": sop["authority"],
            "domain": sop["domain"],
            "trigger_condition": sop["trigger_condition"],
            "action_protocols": sop["action_protocols"],
            "relevance_score": round(float(min(1.0, max(0.0, score))), 3),
        })

    return results
