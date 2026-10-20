"""Download trendshift.io daily trending repositories for every date.

Trendshift's homepage loads past days through a Next.js Server Action
(`getRepositoryRecommendationsByDate(date, language)`). We call it directly,
one request per day, and cache each day as data/daily/YYYY-MM-DD.json so
re-running only fetches missing days.

    uv run scrape.py                      # 2024-01-01 .. today
    uv run scrape.py --start 2025-01-01 --end 2025-01-31
"""

import argparse
import datetime as dt
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

BASE = "https://trendshift.io"
FIRST_DATE = dt.date(2024, 1, 1)  # date picker on the site starts here
DAILY_DIR = Path("data/daily")
ACTION_NAME = "getRepositoryRecommendationsByDate"
# Fallback if discovery fails; the id changes when the site is redeployed.
FALLBACK_ACTION_ID = "60ecd1b65963ced79feccf911fdc86fcf7301e6eec"
REFETCH_DAYS = 3  # today + the two days before
HEADERS = {"User-Agent": "Mozilla/5.0 (browse-trendshift personal research)"}


def discover_action_id(session: requests.Session) -> str:
    """Find the server action id by scanning the homepage JS chunks."""
    html = session.get(BASE + "/", timeout=30).text
    chunks = sorted(set(re.findall(r"/_next/static/chunks/[\w.-]+\.js", html)))
    pattern = re.compile(r'"([0-9a-f]{40,})"[^"]{0,120}"' + ACTION_NAME + '"')
    for chunk in chunks:
        m = pattern.search(session.get(BASE + chunk, timeout=30).text)
        if m:
            return m.group(1)
    print(f"! could not discover action id, using fallback {FALLBACK_ACTION_ID}")
    return FALLBACK_ACTION_ID


def parse_rsc(body: str) -> list[dict]:
    """The response is an RSC stream: lines like `0:{...}` and `1:[...]`."""
    # split on "\n" only: splitlines() also breaks on U+2028 etc. inside descriptions
    for line in body.split("\n"):
        key, _, payload = line.partition(":")
        if key == "1" and payload.startswith("["):
            return json.loads(payload)
    raise ValueError(f"unexpected response: {body[:200]!r}")


def fetch_day(session: requests.Session, action_id: str, day: dt.date, retries: int = 3) -> list[dict]:
    headers = {
        "Next-Action": action_id,
        "Accept": "text/x-component",
        "Content-Type": "text/plain;charset=UTF-8",
    }
    body = json.dumps([day.isoformat(), "all"])
    for attempt in range(retries):
        try:
            r = session.post(BASE + "/", headers=headers, data=body, timeout=30)
            r.raise_for_status()
            r.encoding = "utf-8"  # text/x-component has no charset; requests would guess latin-1
            return parse_rsc(r.text)
        except (requests.RequestException, ValueError) as e:
            if attempt == retries - 1:
                raise
            print(f"  retry {day} ({e})")
            time.sleep(2 * (attempt + 1))
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=dt.date.fromisoformat, default=FIRST_DATE)
    ap.add_argument("--end", type=dt.date.fromisoformat, default=dt.datetime.now(dt.UTC).date())
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--refresh", action="store_true", help="re-download days already cached")
    args = ap.parse_args()

    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    days = [args.start + dt.timedelta(n) for n in range((args.end - args.start).days + 1)]
    today = dt.datetime.now(dt.UTC).date()
    # Trendshift recomputes rankings during the day and still revises a day's list the next UTC day
    # (seen 2026-10-19), so always refetch the last few days.
    todo = [d for d in days if args.refresh or d >= today - dt.timedelta(REFETCH_DAYS - 1)
            or not (DAILY_DIR / f"{d}.json").exists()]
    print(f"{len(days)} days in range, {len(todo)} to fetch")
    if not todo:
        return

    session = requests.Session()
    session.headers.update(HEADERS)
    action_id = discover_action_id(session)
    print(f"server action id: {action_id}")

    failed = []
    with ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(fetch_day, session, action_id, d): d for d in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            day = futures[fut]
            try:
                items = fut.result()
            except Exception as e:  # keep going; report at the end
                failed.append(day)
                print(f"x {day}: {e}")
                continue
            (DAILY_DIR / f"{day}.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            if i % 50 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} done")

    if failed:
        print(f"{len(failed)} days failed: {sorted(failed)[:10]} ... rerun to retry")


if __name__ == "__main__":
    main()
