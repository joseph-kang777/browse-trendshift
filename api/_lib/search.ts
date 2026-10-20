// Port of trendsearch.Searcher for the hosted deployment: reads the int8 index written by
// export_index.py and embeds queries with bge-m3 on Cloudflare Workers AI.
import { readFileSync } from "node:fs"
import { join } from "node:path"

export type Repo = {
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
  has_readme: boolean
}

export type Info = {
  model: string
  dim: number
  count: number
  chunks: number
  latest_day: string
  first_day: string
  languages: string[]
}

export type Filters = {
  k: number
  language: string
  since: string
  min_stars: number
  popularity_weight: number
  readme_weight: number
}

type Matrix = { q: Int8Array; scale: Float32Array }

type Index = {
  info: Info
  repos: Repo[]
  meta: Matrix
  chunks: Matrix
  mean: Matrix
  chunkOwner: Int32Array
  byName: Map<string, number>
}

const DIR = join(process.cwd(), "deploy-index")
let cached: Index | null = null

function bytes(name: string): ArrayBuffer {
  const buf = readFileSync(join(DIR, name))
  return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer // aligned copy
}

function matrix(name: string): Matrix {
  return { q: new Int8Array(bytes(`${name}.i8`)), scale: new Float32Array(bytes(`${name}.scale`)) }
}

export function index(): Index {
  if (!cached) {
    const repos: Repo[] = JSON.parse(readFileSync(join(DIR, "repos.json"), "utf-8"))
    cached = {
      info: JSON.parse(readFileSync(join(DIR, "info.json"), "utf-8")),
      repos,
      meta: matrix("meta"),
      chunks: matrix("chunks"),
      mean: matrix("mean"),
      chunkOwner: new Int32Array(bytes("chunk_owner.i32")),
      byName: new Map(repos.map((r, i) => [r.full_name.toLowerCase(), i])),
    }
  }
  return cached
}

/** Row-wise dot products of an int8 matrix with a float vector. */
function dots(m: Matrix, v: Float32Array, dim: number): Float32Array {
  const rows = m.scale.length
  const out = new Float32Array(rows)
  for (let r = 0; r < rows; r++) {
    let s = 0
    const base = r * dim
    for (let j = 0; j < dim; j++) s += m.q[base + j] * v[j]
    out[r] = s * m.scale[r]
  }
  return out
}

function row(m: Matrix, r: number, dim: number): Float32Array {
  const out = new Float32Array(dim)
  const s = m.scale[r]
  for (let j = 0; j < dim; j++) out[j] = m.q[r * dim + j] * s
  return out
}

const embedCache = new Map<string, Float32Array>()

export async function embedQuery(text: string): Promise<Float32Array> {
  const hit = embedCache.get(text)
  if (hit) return hit
  const account = process.env.CLOUDFLARE_ACCOUNT_ID
  const token = process.env.CLOUDFLARE_API_TOKEN
  if (!account || !token) throw new Error("CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN are not set")
  const res = await fetch(`https://api.cloudflare.com/client/v4/accounts/${account}/ai/run/@cf/baai/bge-m3`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ text: [text] }),
  })
  const body = await res.json()
  if (!body.success) throw new Error(`Workers AI error ${res.status}: ${JSON.stringify(body.errors)}`)
  const v = Float32Array.from(body.result.data[0] as number[])
  const norm = Math.hypot(...v)
  for (let j = 0; j < v.length; j++) v[j] /= norm
  if (embedCache.size > 500) embedCache.clear()
  embedCache.set(text, v)
  return v
}

export type Hit = Repo & { similarity: number; score: number }

export function searchVector(q: Float32Array, f: Filters): Hit[] {
  const ix = index()
  const dim = ix.info.dim
  const metaSims = dots(ix.meta, q, dim)
  // best-matching README chunk per repo
  const readmeSims = new Float32Array(ix.repos.length).fill(-1)
  const chunkSims = dots(ix.chunks, q, dim)
  for (let c = 0; c < chunkSims.length; c++) {
    const o = ix.chunkOwner[c]
    if (chunkSims[c] > readmeSims[o]) readmeSims[o] = chunkSims[c]
  }
  const w = f.readme_weight
  const sims = metaSims.map((m, i) => (ix.repos[i].has_readme ? (1 - w) * m + w * readmeSims[i] : m))
  return rank(sims, f)
}

export function similarTo(fullName: string, f: Filters): Hit[] | null {
  const ix = index()
  const pos = ix.byName.get(fullName.toLowerCase())
  if (pos === undefined) return null
  const dim = ix.info.dim
  // profile = (1-w)·meta + w·mean README chunk, normalized (README part only for repos that have one)
  const profile = (i: number) => {
    const w = ix.repos[i].has_readme ? f.readme_weight : 0
    const m = row(ix.meta, i, dim)
    const r = row(ix.mean, i, dim)
    for (let j = 0; j < dim; j++) m[j] = (1 - w) * m[j] + w * r[j]
    const n = Math.hypot(...m) || 1
    for (let j = 0; j < dim; j++) m[j] /= n
    return m
  }
  const target = profile(pos)
  const sims = new Float32Array(ix.repos.length)
  for (let i = 0; i < sims.length; i++) {
    const p = profile(i)
    let s = 0
    for (let j = 0; j < dim; j++) s += p[j] * target[j]
    sims[i] = s
  }
  sims[pos] = -1 // exclude itself
  return rank(sims, f)
}

function rank(sims: Float32Array, f: Filters): Hit[] {
  const ix = index()
  const order = Array.from(sims.keys()).sort((a, b) => sims[b] - sims[a])
  const hits: Hit[] = []
  for (const i of order.slice(0, Math.max(f.k * 20, 200))) {
    const r = ix.repos[i]
    if (f.language && r.language !== f.language) continue
    if (f.since && r.last_seen < f.since) continue
    if (r.stars < f.min_stars) continue
    const sim = sims[i]
    // Small boost for repos that trended on many days; similarity still dominates.
    hits.push({ ...r, similarity: round4(sim), score: round4(sim + f.popularity_weight * Math.log1p(r.appearances)) })
  }
  return hits.sort((a, b) => b.score - a.score).slice(0, f.k)
}

const round4 = (x: number) => Math.round(x * 1e4) / 1e4

export function parseFilters(params: URLSearchParams): Filters {
  const num = (key: string, fallback: number) => {
    const v = Number(params.get(key) ?? fallback)
    return Number.isFinite(v) ? v : fallback
  }
  return {
    k: Math.min(100, Math.max(1, Math.round(num("k", 20)))),
    language: params.get("language") ?? "",
    since: params.get("since") ?? "",
    min_stars: num("min_stars", 0),
    popularity_weight: num("popularity_weight", 0.01),
    readme_weight: Math.min(1, Math.max(0, num("readme_weight", 0.5))),
  }
}

export function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } })
}
