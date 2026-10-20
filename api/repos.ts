import { index, json } from "./_lib/search"

/** Names for the repo picker, most-trended first. */
export function GET() {
  const names = [...index().repos].sort((a, b) => b.appearances - a.appearances).map((r) => r.full_name)
  return json(names)
}
