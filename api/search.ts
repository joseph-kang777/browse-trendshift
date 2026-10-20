import { embedQuery, json, parseFilters, searchVector } from "./_lib/search"

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams
  const q = (params.get("q") ?? "").trim()
  if (!q || q.length > 500) return json({ detail: "q must be 1-500 characters" }, 422)
  try {
    return json(searchVector(await embedQuery(q), parseFilters(params)))
  } catch (e) {
    return json({ detail: String((e as Error).message ?? e) }, 502)
  }
}
