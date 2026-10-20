"""Aggregate scraped daily data into one record per repo and search it by similarity."""

import functools
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DAILY_DIR = Path("data/daily")
INDEX_DIR = Path("data/index")
README_DIR = Path("data/readme")
CHUNK_CHARS = 1200  # ~300-500 tokens
MAX_CHUNKS = 8  # the start of a README says what the project is; skip long tails
# Multilingual models so Korean queries match English repo descriptions.
# name -> (query prefix, passage prefix)
MODELS = {
    "BAAI/bge-m3": ("", ""),
    "intfloat/multilingual-e5-small": ("query: ", "passage: "),
}
DEFAULT_MODEL = "BAAI/bge-m3"


def aggregate(daily_dir: Path = DAILY_DIR) -> list[dict]:
    """Merge every day's entries into one record per repository."""
    repos: dict[int, dict] = {}
    for path in sorted(daily_dir.glob("*.json")):  # chronological, so later days overwrite
        day = path.stem
        for item in json.loads(path.read_text(encoding="utf-8")):
            rid = item["repository_id"]
            r = repos.setdefault(rid, {
                "id": rid,
                "dates": [],
                "best_rank": item["rank"],
                "tags": {},
                "description": "",
            })
            r["full_name"] = item["full_name"]
            r["language"] = item.get("repository_language") or item.get("language") or ""
            r["stars"] = item.get("repository_stars") or 0
            r["created_at"] = item.get("repository_created_at") or ""
            if item.get("repository_description"):
                r["description"] = item["repository_description"]
            for t in item.get("tags") or []:
                r["tags"][t["slug"]] = t["display_name"]
            if day not in r["dates"]:
                r["dates"].append(day)
            r["best_rank"] = min(r["best_rank"], item["rank"])

    out = []
    for r in repos.values():
        r["tags"] = sorted(r["tags"].values())
        r["appearances"] = len(r["dates"])
        r["first_seen"], r["last_seen"] = r["dates"][0], r["dates"][-1]
        out.append(r)
    return out


def repo_text(r: dict) -> str:
    name = r["full_name"].split("/")[-1].replace("-", " ").replace("_", " ")
    parts = [f"{name} ({r['full_name']})"]
    if r["description"]:
        parts.append(r["description"])
    if r["tags"]:
        parts.append("Topics: " + ", ".join(r["tags"]))
    if r["language"]:
        parts.append("Language: " + r["language"])
    return ". ".join(parts)


_README_NOISE = [
    (re.compile(r"```.*?```|~~~.*?~~~", re.S), " "),  # code blocks
    (re.compile(r"<!--.*?-->", re.S), " "),
    (re.compile(r"\[!\[.*?\]\(.*?\)\]\(.*?\)"), " "),  # linked badges
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),  # images / badges
    (re.compile(r"\[([^\]]*)\]\([^)]*\)"), r"\1"),  # [text](url) -> text
    (re.compile(r"<[^>]+>"), " "),  # html tags
    (re.compile(r"https?://\S+"), " "),
    (re.compile(r"^\s*[|:\- ]+\s*$", re.M), " "),  # table separators
    (re.compile(r"[#*_`>|=]+"), " "),  # markdown punctuation
    (re.compile(r"[ \t]+"), " "),
    (re.compile(r"\n\s*\n+"), "\n"),
]


def clean_readme(text: str) -> str:
    for pattern, repl in _README_NOISE:
        text = pattern.sub(repl, text)
    return text.strip()


def readme_chunks(repo_id: int) -> list[str]:
    path = README_DIR / f"{repo_id}.md"
    if not path.exists():
        return []
    text = clean_readme(path.read_text(encoding="utf-8", errors="replace"))
    chunks, cur = [], ""
    for para in text.split("\n"):
        if cur and len(cur) + len(para) > CHUNK_CHARS:
            chunks.append(cur)
            if len(chunks) == MAX_CHUNKS:
                return chunks
            cur = ""
        cur = (cur + "\n" + para).strip()[: CHUNK_CHARS * 2]
    if len(cur) > 40:  # drop near-empty READMEs
        chunks.append(cur)
    return chunks[:MAX_CHUNKS]


@functools.cache  # the app rebuilds Searcher when the index changes; keep one model in memory
def load_model(name: str):
    import torch
    from sentence_transformers import SentenceTransformer  # slow import, keep lazy
    return SentenceTransformer(name, device="cuda" if torch.cuda.is_available() else "cpu")


def build_index(model_name: str = DEFAULT_MODEL, backend: str = "local") -> int:
    """backend "cloudflare" embeds new text with bge-m3 on Workers AI instead of loading the model."""
    if backend == "cloudflare" and model_name != "BAAI/bge-m3":
        raise ValueError("Workers AI only hosts BAAI/bge-m3")
    repos = aggregate()
    prefix = MODELS[model_name][1]
    chunk_texts, chunk_owner = [], []
    for i, r in enumerate(repos):
        chunks = readme_chunks(r["id"])
        r["has_readme"] = bool(chunks)
        r["readme_excerpt"] = chunks[0][:400] if chunks else ""
        for c in chunks:
            # prefix the repo name so a chunk like "Installation ..." stays tied to its project
            chunk_texts.append(f"{prefix}{r['full_name']}: {c}")
            chunk_owner.append(i)

    meta_texts = [prefix + repo_text(r) for r in repos]
    meta_keys = [_text_key(t) for t in meta_texts]
    chunk_keys = [_text_key(t) for t in chunk_texts]

    # Reuse vectors of texts embedded by the previous build; only new/changed text hits the model.
    cache = _load_vector_cache(model_name)
    todo = sorted({k: t for k, t in zip(meta_keys + chunk_keys, meta_texts + chunk_texts) if k not in cache}.items(),
                  key=lambda kt: -len(kt[1]))  # longest first keeps batches evenly padded -> faster
    print(f"{len(cache)} cached vectors, {len(todo)} texts to embed")
    if todo and backend == "cloudflare":
        from cloudflare_ai import embed
        cache.update(zip((k for k, _ in todo), embed([t for _, t in todo], progress=len(todo) > 500)))
    elif todo:
        model = load_model(model_name)
        model.max_seq_length = 512
        vecs = model.encode([t for _, t in todo], batch_size=32, normalize_embeddings=True,
                            show_progress_bar=len(todo) > 500).astype(np.float32)
        cache.update(zip((k for k, _ in todo), vecs))

    dim = next(iter(cache.values())).shape[0]
    meta_emb = np.stack([cache[k] for k in meta_keys])
    chunk_emb = np.stack([cache[k] for k in chunk_keys]) if chunk_keys else np.empty((0, dim), np.float32)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    # Write to temp files, then swap in; meta.json goes last since the app watches it.
    _atomic_write(INDEX_DIR / "repos.json", lambda p: p.write_text(json.dumps(repos, ensure_ascii=False), encoding="utf-8"))
    _atomic_write(INDEX_DIR / "embeddings.npy", lambda p: np.save(p, meta_emb))
    _atomic_write(INDEX_DIR / "chunk_embeddings.npy", lambda p: np.save(p, chunk_emb))
    _atomic_write(INDEX_DIR / "chunk_owner.npy", lambda p: np.save(p, np.array(chunk_owner, np.int32)))
    _atomic_write(INDEX_DIR / "keys.json", lambda p: p.write_text(json.dumps({"meta": meta_keys, "chunks": chunk_keys})))
    _atomic_write(INDEX_DIR / "meta.json", lambda p: p.write_text(json.dumps(
        {"model": model_name, "count": len(repos), "chunks": len(chunk_texts),
         "latest_day": max(r["last_seen"] for r in repos)})))
    return len(repos)


def _text_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _load_vector_cache(model_name: str) -> dict[str, np.ndarray]:
    """text key -> vector from the existing index, if it was built with the same model."""
    try:
        if json.loads((INDEX_DIR / "meta.json").read_text())["model"] != model_name:
            return {}
        keys = json.loads((INDEX_DIR / "keys.json").read_text())
        cache = dict(zip(keys["meta"], np.load(INDEX_DIR / "embeddings.npy")))
        cache.update(zip(keys["chunks"], np.load(INDEX_DIR / "chunk_embeddings.npy")))
        return cache
    except (OSError, KeyError, ValueError):
        return {}


def _atomic_write(path: Path, write) -> None:
    tmp = path.with_name(path.stem + ".tmp" + path.suffix)  # keep suffix so np.save doesn't add .npy
    write(tmp)
    os.replace(tmp, path)


@dataclass
class Hit:
    repo: dict
    similarity: float
    score: float


class Searcher:
    def __init__(self):
        meta = json.loads((INDEX_DIR / "meta.json").read_text())
        self.query_prefix = MODELS[meta["model"]][0]
        self.model = load_model(meta["model"])
        self.repos = json.loads((INDEX_DIR / "repos.json").read_text(encoding="utf-8"))
        self.emb = np.load(INDEX_DIR / "embeddings.npy")
        self.chunk_emb = np.load(INDEX_DIR / "chunk_embeddings.npy")
        self.chunk_owner = np.load(INDEX_DIR / "chunk_owner.npy")
        self.has_readme = np.array([r["has_readme"] for r in self.repos])
        # Mean README chunk per repo, for repo-to-repo similarity.
        sums = np.zeros_like(self.emb)
        np.add.at(sums, self.chunk_owner, self.chunk_emb)
        counts = np.bincount(self.chunk_owner, minlength=len(self.repos))
        self.readme_mean = sums / np.maximum(counts, 1)[:, None]

    def languages(self) -> list[str]:
        return sorted({r["language"] for r in self.repos if r["language"]})

    def search(
        self,
        query: str,
        k: int = 20,
        language: str | None = None,
        since: str | None = None,
        min_stars: int = 0,
        popularity_weight: float = 0.01,
        readme_weight: float = 0.5,
    ) -> list[Hit]:
        q = self.model.encode(self.query_prefix + query, normalize_embeddings=True)
        meta_sims = self.emb @ q
        # best-matching README chunk per repo
        readme_sims = np.full(len(self.repos), -1.0, np.float32)
        np.maximum.at(readme_sims, self.chunk_owner, self.chunk_emb @ q)
        sims = np.where(self.has_readme, (1 - readme_weight) * meta_sims + readme_weight * readme_sims, meta_sims)
        return self._rank(sims, k, language, since, min_stars, popularity_weight)

    def similar_to(self, full_name: str, k: int = 20, readme_weight: float = 0.5, **filters) -> list[Hit]:
        """Repos similar to one already in the index."""
        pos = next((i for i, r in enumerate(self.repos) if r["full_name"].lower() == full_name.lower()), None)
        if pos is None:
            raise KeyError(full_name)
        w = np.where(self.has_readme, readme_weight, 0.0)[:, None]
        profile = (1 - w) * self.emb + w * self.readme_mean
        profile /= np.linalg.norm(profile, axis=1, keepdims=True)
        sims = profile @ profile[pos]
        sims[pos] = -1  # exclude itself
        return self._rank(sims, k, **filters)

    def _rank(self, sims, k, language=None, since=None, min_stars=0, popularity_weight=0.01) -> list[Hit]:
        hits = []
        for i in np.argsort(-sims)[: max(k * 20, 200)]:  # filter a generous candidate pool
            r = self.repos[i]
            if language and r["language"] != language:
                continue
            if since and r["last_seen"] < since:
                continue
            if r["stars"] < min_stars:
                continue
            sim = float(sims[i])
            # Small boost for repos that trended on many days; similarity still dominates.
            score = sim + popularity_weight * math.log1p(r["appearances"])
            hits.append(Hit(r, sim, score))
        hits.sort(key=lambda h: -h.score)
        return hits[:k]
