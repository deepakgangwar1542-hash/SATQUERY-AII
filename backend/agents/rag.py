"""RAG Knowledge Agent (FR-13).

Corpus: curated, versioned markdown under <repo>/knowledge/{remote_sensing,
sensors, disaster} — authored reference material, not scraped (FR-13 AC1).
Retrieval: sentence-transformers embeddings via models.loaders when available,
else scikit-learn TF-IDF (documented open alternative, FR-13 AC2).
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"
CHUNK_MIN = 120
CHUNK_MAX = 900


@lru_cache(maxsize=1)
def _corpus() -> list[dict]:
    chunks: list[dict] = []
    if not KNOWLEDGE_DIR.exists():
        return chunks
    for md in sorted(KNOWLEDGE_DIR.rglob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        section = None
        buf: list[str] = []
        for line in text.splitlines():
            if line.startswith("#"):
                if buf:
                    _add(chunks, md, section, " ".join(buf))
                buf, section = [], line.lstrip("# ").strip() or None
            else:
                buf.append(line)
        if buf:
            _add(chunks, md, section, " ".join(buf))
    return chunks


def _add(chunks: list[dict], path: Path, section: str | None, text: str) -> None:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < CHUNK_MIN:
        return
    for i in range(0, min(len(text), CHUNK_MAX * 4), CHUNK_MAX):
        part = text[i:i + CHUNK_MAX]
        if len(part) < CHUNK_MIN and chunks:
            chunks[-1]["text"] += " " + part
        else:
            chunks.append({
                "text": part,
                "source": str(path.relative_to(KNOWLEDGE_DIR.parent)),
                "section": section,
            })


@lru_cache(maxsize=1)
def _tfidf():
    from sklearn.feature_extraction.text import TfidfVectorizer
    docs = [c["text"] for c in _corpus()] or ["empty knowledge base"]
    vec = TfidfVectorizer(stop_words="english", max_features=4096)
    mat = vec.fit_transform(docs)
    return vec, mat


def retrieve(query: str, k: int = 3) -> dict:
    chunks = _corpus()
    if not chunks:
        return {"passages": [], "note": "knowledge_base_empty"}
    emb, _reason = None, None
    try:
        from ..models import loaders
        emb, _reason = loaders.load_embedding_model()
    except Exception:
        emb = None
    if emb is not None:
        import numpy as np
        vecs = emb.encode([c["text"] for c in chunks], normalize_embeddings=True)
        qv = emb.encode([query], normalize_embeddings=True)
        scores = (np.asarray(vecs) @ np.asarray(qv).T).ravel()
    else:
        vec, mat = _tfidf()
        scores = (mat @ vec.transform([query]).T).toarray().ravel()
    top = sorted(zip(scores, chunks), key=lambda t: t[0], reverse=True)[:k]
    passages = [
        {"text": c["text"], "source": c["source"], "section": c["section"],
         "score": round(float(s), 4)}
        for s, c in top if s > 0.01
    ]
    return {"passages": passages,
            "mode": "embeddings" if emb is not None else "tfidf_fallback"}
