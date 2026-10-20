export type Meta = {
  count: number
  latest_day: string
  first_day: string
  languages: string[]
}

export type Result = {
  full_name: string
  description: string
  language: string
  stars: number
  tags: string[]
  appearances: number
  best_rank: number
  first_seen: string
  last_seen: string
  readme_excerpt: string
  created_at: string
  similarity: number
  score: number
}

export type Filters = {
  k: number
  language: string
  since: string
  min_stars: number
  popularity_weight: number
  readme_weight: number
}

async function get<T>(path: string, params: Record<string, string | number> = {}): Promise<T> {
  const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]))
  const res = await fetch(`/api/${path}?${qs}`)
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? res.statusText)
  return res.json()
}

export const api = {
  meta: () => get<Meta>("meta"),
  repos: () => get<string[]>("repos"),
  search: (q: string, f: Filters) => get<Result[]>("search", { q, ...f }),
  similar: (repo: string, f: Filters) => get<Result[]>("similar", { repo, ...f }),
}
