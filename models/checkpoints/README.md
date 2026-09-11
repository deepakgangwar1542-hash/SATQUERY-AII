# models/checkpoints/

Runtime checkpoints live here, fetched explicitly via `scripts/fetch_models.sh`
(PRD §7.5 — never silently baked into images):

```
checkpoints/
├── grounding_dino/   # IDEA-Research/grounding-dino-tiny (Apache-2.0)
├── sam2/             # facebook/sam2-hiera-small (Apache-2.0)
├── embeddings/       # all-MiniLM-L6-v2 (Apache-2.0)
└── vlm/              # chosen perception VLM (see registry.yaml)
```

Provenance + license flags: `backend/models/registry.yaml` and
`../../LICENSE_AUDIT.md`. With no checkpoints present, every agent runs its
documented deterministic fallback and `/api/v1/health` reports the mode.
