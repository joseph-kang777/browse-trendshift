import { json, parseFilters, similarTo } from "./_lib/search"

export function GET(request: Request) {
  const params = new URL(request.url).searchParams
  const repo = params.get("repo") ?? ""
  const hits = similarTo(repo, parseFilters(params))
  return hits ? json(hits) : json({ detail: `${repo} is not in the index` }, 404)
}
