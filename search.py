"""Find trending repos matching what you need.

    uv run search.py "로컬에서 돌리는 음성 인식"
    uv run search.py "rag framework" --lang Python --since 2025-06-01 -k 10
    uv run search.py --like langgenius/dify
"""

import argparse
import sys

from trendsearch import Searcher


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", help="what you are looking for (any language)")
    ap.add_argument("--like", help="find repos similar to this owner/repo")
    ap.add_argument("-k", type=int, default=15)
    ap.add_argument("--lang", help="exact language, e.g. Python")
    ap.add_argument("--since", help="only repos that trended on/after YYYY-MM-DD")
    ap.add_argument("--min-stars", type=int, default=0)
    ap.add_argument("--readme-weight", type=float, default=0.5, help="0 = name/description only, 1 = README only")
    args = ap.parse_args()
    if not args.query and not args.like:
        ap.error("give a query or --like owner/repo")

    s = Searcher()
    filters = dict(language=args.lang, since=args.since, min_stars=args.min_stars, readme_weight=args.readme_weight)
    hits = s.similar_to(args.like, args.k, **filters) if args.like else s.search(args.query, args.k, **filters)

    for n, h in enumerate(hits, 1):
        r = h.repo
        print(f"{n:2}. {r['full_name']}  [{r['language'] or '-'}] ★{r['stars']:,}  sim={h.similarity:.3f}")
        if r["description"]:
            print(f"    {r['description'][:160]}")
        print(f"    trended {r['appearances']}d (best #{r['best_rank']}, {r['first_seen']} ~ {r['last_seen']})"
              f"  https://github.com/{r['full_name']}")


if __name__ == "__main__":
    main()
