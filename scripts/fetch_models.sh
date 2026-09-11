#!/usr/bin/env bash
# Fetch open-weight model checkpoints into models/checkpoints/ (PRD §7.5/§19).
# Nothing here is bundled into Docker images silently; run it explicitly.
#
# Requirements: pip install huggingface_hub
#
# License verification (§14.4): after fetching, open each model card / LICENSE
# and record the result in models/registry.yaml (license_verified: true|false)
# and LICENSE_AUDIT.md. Apache-2.0 entries below were permissive at time of
# writing — re-verify before any deployment.
set -euo pipefail

CKPT_DIR="$(dirname "$0")/../models/checkpoints"
mkdir -p "$CKPT_DIR"

python - <<'EOF'
from huggingface_hub import snapshot_download
import os

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models", "checkpoints")

targets = [
    # (hf_id, local subdir, note)
    ("IDEA-Research/grounding-dino-tiny", "grounding_dino",
     "text-conditioned detection (Apache-2.0)"),
    ("facebook/sam2-hiera-small", "sam2",
     "promptable segmentation (Apache-2.0)"),
    ("sentence-transformers/all-MiniLM-L6-v2", "embeddings",
     "RAG embeddings (Apache-2.0)"),
    # Perception VLM: pick ONE —
    #   satlasprithvi (Prithvi-EO family, Apache-2.0):
    # ("nasa-cisto-data-science-group/satlasprithvi-swin-b", "vlm", "geospatial VLM")
    #   or a general Apache-2.0 VLM checkpoint of your choice.
]
for hf_id, sub, note in targets:
    print(f"fetching {hf_id} -> {sub}  ({note})")
    snapshot_download(repo_id=hf_id,
                      local_dir=os.path.join(root, sub),
                      ignore_patterns=["*.pth", "*.onnx", "*.msgpack",
                                       "*.h5", "*.ot", "flax*"])
print("done — update registry.yaml license_verified after reviewing each LICENSE")
EOF
