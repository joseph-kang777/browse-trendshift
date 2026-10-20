"""HTTP API for the web UI, and the built UI itself (web/dist).

    uv run server.py            # http://localhost:8600
"""

import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from trendsearch import INDEX_DIR, Hit, Searcher

WEB_DIST = Path("web/dist")
app = FastAPI(title="Trendshift Finder")

_lock = threading.Lock()
_searcher: Searcher | None = None
_version = 0.0


def searcher() -> Searcher:
    """Current Searcher; rebuilt when the daily update writes a new index (meta.json is written last)."""
    global _searcher, _version
    mtime = (INDEX_DIR / "meta.json").stat().st_mtime
    with _lock:
        if _searcher is None or mtime != _version:
            _searcher, _version = Searcher(), mtime
        return _searcher


def hit_json(h: Hit) -> dict:
    r = h.repo
    keys = ("full_name", "description", "language", "stars", "tags", "appearances", "best_rank",
            "first_seen", "last_seen", "readme_excerpt", "created_at")
    return {**{k: r.get(k) for k in keys}, "similarity": round(h.similarity, 4), "score": round(h.score, 4)}


def filters(language, since, min_stars, popularity_weight, readme_weight) -> dict:
    return dict(language=language or None, since=since or None, min_stars=min_stars,
                popularity_weight=popularity_weight, readme_weight=readme_weight)


@app.get("/api/meta")
def meta():
    s = searcher()
    return {
        "count": len(s.repos),
        "latest_day": max(r["last_seen"] for r in s.repos),
        "first_day": min(r["first_seen"] for r in s.repos),
        "languages": s.languages(),
    }


@app.get("/api/repos")
def repo_names():
    """Names for the repo picker, most-trended first."""
    s = searcher()
    return [r["full_name"] for r in sorted(s.repos, key=lambda r: -r["appearances"])]


@app.get("/api/search")
def search(
    q: str = Query(min_length=1),
    k: int = Query(20, ge=1, le=100),
    language: str = "",
    since: str = "",
    min_stars: int = 0,
    popularity_weight: float = 0.01,
    readme_weight: float = 0.5,
):
    hits = searcher().search(q, k, **filters(language, since, min_stars, popularity_weight, readme_weight))
    return [hit_json(h) for h in hits]


@app.get("/api/similar")
def similar(
    repo: str,
    k: int = Query(20, ge=1, le=100),
    language: str = "",
    since: str = "",
    min_stars: int = 0,
    popularity_weight: float = 0.01,
    readme_weight: float = 0.5,
):
    try:
        hits = searcher().similar_to(repo, k, **filters(language, since, min_stars, popularity_weight, readme_weight))
    except KeyError:
        raise HTTPException(404, f"{repo} is not in the index")
    return [hit_json(h) for h in hits]


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = (WEB_DIST / path).resolve()
        inside = f.is_relative_to(WEB_DIST.resolve())  # no ../ escapes out of dist
        return FileResponse(f if path and inside and f.is_file() else WEB_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn

    searcher()  # load the model before accepting requests
    uvicorn.run(app, host="127.0.0.1", port=8600)
