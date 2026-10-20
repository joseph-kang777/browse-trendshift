"""Build the embedding index from data/daily/*.json.

    uv run build_index.py                                   # BAAI/bge-m3
    uv run build_index.py --model intfloat/multilingual-e5-small   # smaller/faster
"""

import argparse

from trendsearch import DEFAULT_MODEL, MODELS, build_index

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=list(MODELS), default=DEFAULT_MODEL)
    print(f"indexed {build_index(ap.parse_args().model)} repositories")
