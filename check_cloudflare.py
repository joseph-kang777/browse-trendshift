"""Check that bge-m3 on Workers AI reproduces the local index's vectors.

    uv run check_cloudflare.py

Embeds a sample of indexed texts on Cloudflare and compares them with the
stored local vectors, then compares top-20 rankings for a few queries.
"""

import json
import random

import numpy as np

from cloudflare_ai import embed
from trendsearch import INDEX_DIR, MODELS, Searcher, _text_key, readme_chunks, repo_text

QUERIES = ["로컬에서 돌리는 음성 인식", "convert PDF documents to markdown", "self-hosted Notion alternative",
           "코드베이스를 지식 그래프로 시각화", "rag framework"]


def main() -> None:
    s = Searcher()
    keys = json.loads((INDEX_DIR / "keys.json").read_text())

    # Rebuild the texts behind a sample of stored vectors (same code path as build_index).
    prefix = MODELS["BAAI/bge-m3"][1]
    rng = random.Random(0)
    sample = rng.sample(range(len(s.repos)), 40)
    texts, local = [], []
    meta_pos = {k: i for i, k in enumerate(keys["meta"])}
    chunk_pos = {k: i for i, k in enumerate(keys["chunks"])}
    for i in sample:
        r = s.repos[i]
        t = prefix + repo_text(r)
        texts.append(t)
        local.append(s.emb[meta_pos[_text_key(t)]])
        for c in readme_chunks(r["id"])[:2]:
            t = f"{prefix}{r['full_name']}: {c}"
            texts.append(t)
            local.append(s.chunk_emb[chunk_pos[_text_key(t)]])
    local = np.stack(local)
    remote = embed(texts)
    cos = (local * remote).sum(1)
    lengths = np.array([len(t) for t in texts])
    print(f"{len(texts)} texts: cosine(local, cloudflare) min {cos.min():.4f} mean {cos.mean():.4f}")
    for lo, hi in [(0, 1000), (1000, 1800), (1800, 10**6)]:
        m = (lengths >= lo) & (lengths < hi)
        if m.any():
            print(f"  {lo:>5}-{hi:<7} chars: n={m.sum():3d} min {cos[m].min():.4f} mean {cos[m].mean():.4f}")

    # Same queries, local vs Cloudflare query vector, against the local index.
    remote_q = embed(QUERIES)
    for q, rq in zip(QUERIES, remote_q):
        a = [h.repo["full_name"] for h in s.search(q, 20)]
        s_model = s.model
        s.model = type("Fixed", (), {"encode": staticmethod(lambda *_a, **_k: rq)})()
        b = [h.repo["full_name"] for h in s.search(q, 20)]
        s.model = s_model
        print(f"top-20 overlap {len(set(a) & set(b)):2d}/20, same top-5 order: {a[:5] == b[:5]}  {q}")


if __name__ == "__main__":
    main()
