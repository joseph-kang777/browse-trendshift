import { index, json } from "./_lib/search"

export function GET() {
  const { count, latest_day, first_day, languages } = index().info
  return json({ count, latest_day, first_day, languages })
}
