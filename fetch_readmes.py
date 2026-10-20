"""Download the GitHub README of every repo found in data/daily.

raw.githubusercontent.com has no API quota, so try common README filenames
there first and only fall back to the REST API (5000 req/h with a token)
for the rest. Cached as data/readme/<repo id>.md; repos without a README
(deleted, private, none) get an empty <repo id>.missing marker.

    uv run fetch_readmes.py
    uv run fetch_readmes.py --retry-missing
"""

import argparse
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from trendsearch import README_DIR, aggregate

RAW_NAMES = ["README.md", "readme.md", "Readme.md", "README.MD", "README.rst", "README", "README.txt"]
MAX_BYTES = 200_000  # some READMEs are huge changelogs; we only embed the start anyway


def github_token() -> str | None:
    if tok := os.environ.get("GITHUB_TOKEN"):
        return tok
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def fetch_readme(session: requests.Session, full_name: str, token: str | None) -> str | None:
    for name in RAW_NAMES:
        r = session.get(f"https://raw.githubusercontent.com/{full_name}/HEAD/{name}", timeout=30)
        if r.status_code == 200:
            r.encoding = "utf-8"
            return r.text[:MAX_BYTES]
        if r.status_code not in (404,):
            r.raise_for_status()
    if token:  # unusual filename/location (e.g. docs/README.md); the API knows
        r = session.get(
            f"https://api.github.com/repos/{full_name}/readme",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.raw+json"},
            timeout=30,
        )
        if r.status_code == 200:
            r.encoding = "utf-8"
            return r.text[:MAX_BYTES]
        if r.status_code not in (403, 404, 451):  # 403: blocked (e.g. DMCA)
            r.raise_for_status()
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--retry-missing", action="store_true")
    args = ap.parse_args()

    README_DIR.mkdir(parents=True, exist_ok=True)
    repos = aggregate()
    todo = [
        r for r in repos
        if not (README_DIR / f"{r['id']}.md").exists()
        and (args.retry_missing or not (README_DIR / f"{r['id']}.missing").exists())
    ]
    print(f"{len(repos)} repos, {len(todo)} READMEs to fetch")
    token = github_token()
    print("GitHub token:", "yes" if token else "no (raw.githubusercontent only)")

    session = requests.Session()
    session.headers["User-Agent"] = "browse-trendshift"
    missing, failed = 0, 0
    with ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(fetch_readme, session, r["full_name"], token): r for r in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            r = futures[fut]
            try:
                text = fut.result()
            except requests.RequestException as e:
                failed += 1
                print(f"x {r['full_name']}: {e}")
                continue
            if text is None:
                missing += 1
                (README_DIR / f"{r['id']}.missing").touch()
            else:
                (README_DIR / f"{r['id']}.md").write_text(text, encoding="utf-8")
            if i % 250 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} done ({missing} without README, {failed} failed)", flush=True)
    if failed:
        print("rerun to retry failed repos")


if __name__ == "__main__":
    main()
