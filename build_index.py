"""Build the embedding index from data/daily/*.json.

    uv run build_index.py                                   # BAAI/bge-m3
    uv run build_index.py --model intfloat/multilingual-e5-small   # smaller/faster
    uv run build_index.py --backend cloudflare              # embed new text on Workers AI (no torch)
"""

import argparse
import os

from trendsearch import DEFAULT_MODEL, MODELS, build_index

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=list(MODELS), default=DEFAULT_MODEL)
    ap.add_argument("--backend", choices=["local", "cloudflare"], default=os.environ.get("EMBED_BACKEND", "local"))
    args = ap.parse_args()
    print(f"indexed {build_index(args.model, args.backend)} repositories")
