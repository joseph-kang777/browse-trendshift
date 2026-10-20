"""Embed text with BAAI/bge-m3 on Cloudflare Workers AI.

Same model as the local index, so the hosted search (and the daily GitHub Actions
update) can embed without torch. The free allocation (10,000 neurons/day, about
9M bge-m3 input tokens) covers queries and the daily update easily.

Credentials come from the environment or .env:
    CLOUDFLARE_ACCOUNT_ID=...
    CLOUDFLARE_API_TOKEN=...   # permission: Workers AI Read
"""

import os
import time
from pathlib import Path

import numpy as np
import requests

MODEL = "@cf/baai/bge-m3"
BATCH = 50
MAX_CHARS = 2000  # keep requests well under the model's input limit; we embed the start of each chunk


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _endpoint() -> tuple[str, dict]:
    load_dotenv()
    try:
        account, token = os.environ["CLOUDFLARE_ACCOUNT_ID"], os.environ["CLOUDFLARE_API_TOKEN"]
    except KeyError as e:
        raise SystemExit(f"{e.args[0]} is not set (environment or .env)") from None
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{MODEL}"
    return url, {"Authorization": f"Bearer {token}"}


def embed(texts: list[str], progress: bool = False) -> np.ndarray:
    """Normalized float32 vectors, one row per text."""
    url, headers = _endpoint()
    session = requests.Session()
    out = []
    for start in range(0, len(texts), BATCH):
        batch = [t[:MAX_CHARS] for t in texts[start:start + BATCH]]
        for attempt in range(4):
            r = session.post(url, headers=headers, json={"text": batch}, timeout=120)
            if r.status_code < 500 and r.status_code != 429:
                break
            time.sleep(2 ** attempt)
        body = r.json()
        if not body.get("success"):
            raise RuntimeError(f"Workers AI error {r.status_code}: {body.get('errors')}")
        out.append(np.asarray(body["result"]["data"], np.float32))
        if progress and (start // BATCH) % 20 == 0:
            print(f"  embedded {start + len(batch)}/{len(texts)}", flush=True)
    vecs = np.concatenate(out) if out else np.empty((0, 1024), np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
