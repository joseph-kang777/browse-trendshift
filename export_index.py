"""Export data/index as a compact read-only index for the hosted (Vercel) search.

    uv run export_index.py            # -> deploy-index/

Vectors are stored as int8 with one float32 scale per row (about 4x smaller than
float32; scores change by ~0.001). Read by api/_lib/search.ts.
"""

import json
from pathlib import Path

import numpy as np

from trendsearch import INDEX_DIR

OUT = Path("deploy-index")
REPO_KEYS = ("full_name", "description", "language", "stars", "tags", "appearances", "best_rank",
             "first_seen", "last_seen", "readme_excerpt", "created_at", "has_readme")


def quantize(vecs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    scale = np.abs(vecs).max(axis=1) / 127
    scale[scale == 0] = 1
    return np.round(vecs / scale[:, None]).astype(np.int8), scale.astype(np.float32)


def main() -> None:
    meta = json.loads((INDEX_DIR / "meta.json").read_text())
    repos = json.loads((INDEX_DIR / "repos.json").read_text(encoding="utf-8"))
    emb = np.load(INDEX_DIR / "embeddings.npy")
    chunk_emb = np.load(INDEX_DIR / "chunk_embeddings.npy")
    chunk_owner = np.load(INDEX_DIR / "chunk_owner.npy").astype(np.int32)

    # Mean README chunk per repo, for repo-to-repo similarity (same as Searcher.readme_mean).
    sums = np.zeros_like(emb)
    np.add.at(sums, chunk_owner, chunk_emb)
    mean = sums / np.maximum(np.bincount(chunk_owner, minlength=len(repos)), 1)[:, None]

    OUT.mkdir(exist_ok=True)
    for name, vecs in (("meta", emb), ("chunks", chunk_emb), ("mean", mean)):
        q, scale = quantize(vecs)
        (OUT / f"{name}.i8").write_bytes(q.tobytes())
        (OUT / f"{name}.scale").write_bytes(scale.astype("<f4").tobytes())
    (OUT / "chunk_owner.i32").write_bytes(chunk_owner.astype("<i4").tobytes())
    (OUT / "repos.json").write_text(
        json.dumps([{k: r.get(k) for k in REPO_KEYS} for r in repos], ensure_ascii=False), encoding="utf-8")
    (OUT / "info.json").write_text(json.dumps({
        "model": meta["model"],
        "dim": int(emb.shape[1]),
        "count": len(repos),
        "chunks": int(len(chunk_owner)),
        "latest_day": max(r["last_seen"] for r in repos),
        "first_day": min(r["first_seen"] for r in repos),
        "languages": sorted({r["language"] for r in repos if r["language"]}),
    }))
    size = sum(f.stat().st_size for f in OUT.iterdir())
    print(f"exported {len(repos)} repos, {len(chunk_owner)} chunks to {OUT}/ ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
