import { useCallback, useEffect, useMemo, useState } from "react"
import { ChevronDown, ExternalLink, GitFork, Languages, Moon, Search, SearchX, Sparkles, Star, Sun } from "lucide-react"

import { api, type Filters, type Meta, type Result } from "@/api"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox"
import { DotLoader } from "@/components/ui/dot-loader"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group"
import { Kbd } from "@/components/ui/kbd"
import { Label } from "@/components/ui/label"
import { Panel } from "@/components/ui/panel"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Tag } from "@/components/ui/tag"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

type Mode = "query" | "similar"
type Request = { mode: Mode; text: string }

const PERIODS = [
  { value: "all", label: "periodAll", days: 0 },
  { value: "365", label: "period365", days: 365 },
  { value: "180", label: "period180", days: 180 },
  { value: "90", label: "period90", days: 90 },
  { value: "30", label: "period30", days: 30 },
] as const

const ALL_LANGUAGES = "__all__"

function daysBefore(day: string, days: number) {
  const d = new Date(day + "T00:00:00Z")
  d.setUTCDate(d.getUTCDate() - days)
  return d.toISOString().slice(0, 10)
}

function compact(n: number) {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(n)
}

export function App() {
  const { t } = useI18n()
  const [meta, setMeta] = useState<Meta | null>(null)
  const [repoNames, setRepoNames] = useState<string[]>([])
  // ?q=… or ?like=owner/repo, so a search can be bookmarked or shared
  const [request, setRequest] = useState<Request | null>(() => {
    const p = new URLSearchParams(location.search)
    const like = p.get("like")
    if (like) return { mode: "similar", text: like }
    const q = p.get("q")
    return q ? { mode: "query", text: q } : null
  })
  const [mode, setMode] = useState<Mode>(request?.mode ?? "query")
  const [query, setQuery] = useState(request?.mode === "query" ? request.text : "")
  const [results, setResults] = useState<Result[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [language, setLanguage] = useState(ALL_LANGUAGES)
  const [period, setPeriod] = useState("all")
  const [minStars, setMinStars] = useState(0)
  const [readmeWeight, setReadmeWeight] = useState(0.5)
  const [popularity, setPopularity] = useState(0.01)
  const [k, setK] = useState(20)

  useEffect(() => {
    api.meta().then(setMeta).catch((e) => setError(String(e.message ?? e)))
    api.repos().then(setRepoNames).catch(() => {})
  }, [])

  const filters: Filters = useMemo(() => {
    const days = PERIODS.find((p) => p.value === period)?.days ?? 0
    return {
      k,
      language: language === ALL_LANGUAGES ? "" : language,
      since: days && meta ? daysBefore(meta.latest_day, days) : "",
      min_stars: minStars,
      popularity_weight: popularity,
      readme_weight: readmeWeight,
    }
  }, [k, language, period, minStars, popularity, readmeWeight, meta])

  useEffect(() => {
    if (!request) return
    const url = new URL(location.href)
    url.search = new URLSearchParams({ [request.mode === "query" ? "q" : "like"]: request.text }).toString()
    history.replaceState(null, "", url)
  }, [request])

  // Re-run whenever the request or any filter changes.
  useEffect(() => {
    if (!request) return
    let cancelled = false
    setLoading(true)
    setError(null)
    const call = request.mode === "query" ? api.search(request.text, filters) : api.similar(request.text, filters)
    call
      .then((r) => !cancelled && setResults(r))
      .catch((e) => !cancelled && setError(String(e.message ?? e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [request, filters])

  const runQuery = useCallback((text: string) => {
    const t = text.trim()
    if (!t) return
    setMode("query")
    setQuery(t)
    setRequest({ mode: "query", text: t })
  }, [])

  const runSimilar = useCallback((name: string) => {
    setMode("similar")
    setRequest({ mode: "similar", text: name })
    window.scrollTo({ top: 0, behavior: "smooth" })
  }, [])

  return (
    <div className="mx-auto flex max-w-[1280px] flex-col gap-5 px-4 py-5 lg:px-8">
      <Header meta={meta} />

      <div className="grid items-start gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        <Panel title={t.filters} className="lg:sticky lg:top-5">
          <div className="flex flex-col gap-5 p-3 pt-1">
            <Field label={t.language}>
              <Select value={language} onValueChange={(v) => setLanguage((v as string) ?? ALL_LANGUAGES)}>
                <SelectTrigger size="sm" className="w-full">
                  <SelectValue>{(v: string) => (v === ALL_LANGUAGES ? t.all : v)}</SelectValue>
                </SelectTrigger>
                <SelectContent alignItemWithTrigger={false} className="max-h-80">
                  <SelectItem value={ALL_LANGUAGES}>{t.all}</SelectItem>
                  {meta?.languages.map((l) => (
                    <SelectItem key={l} value={l}>
                      {l}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>

            <Field label={t.period} hint={filters.since ? t.since(filters.since) : undefined}>
              <ToggleGroup
                value={[period]}
                onValueChange={(v: string[]) => v[0] && setPeriod(v[0])}
                spacing={1}
                className="flex-wrap"
              >
                {PERIODS.map((p) => (
                  <ToggleGroupItem key={p.value} value={p.value} size="sm" className="text-[12px]">
                    {t[p.label]}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </Field>

            <Field label={t.minStars} value={minStars ? `★ ${compact(minStars)}` : t.noLimit}>
              <ToggleGroup value={[String(minStars)]} onValueChange={(v: string[]) => v[0] && setMinStars(+v[0])} spacing={1}>
                {[0, 1000, 5000, 20000].map((n) => (
                  <ToggleGroupItem key={n} value={String(n)} size="sm" className="text-[12px]">
                    {n ? compact(n) : "0"}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </Field>

            <SliderField
              label={t.readmeWeight}
              value={readmeWeight}
              format={(v) => `${Math.round(v * 100)}%`}
              min={0}
              max={1}
              step={0.1}
              onChange={setReadmeWeight}
              hint={t.readmeHint}
            />
            <SliderField
              label={t.popularity}
              value={popularity}
              format={(v) => v.toFixed(3)}
              min={0}
              max={0.05}
              step={0.005}
              onChange={setPopularity}
              hint={t.popularityHint}
            />
            <SliderField label={t.resultCount} value={k} format={String} min={5} max={50} step={5} onChange={setK} />
          </div>
        </Panel>

        <main className="flex min-w-0 flex-col gap-4">
          <Tabs value={mode} onValueChange={(v) => setMode(v as Mode)}>
            <TabsList>
              <TabsTrigger value="query">
                <Sparkles /> {t.tabQuery}
              </TabsTrigger>
              <TabsTrigger value="similar">
                <GitFork /> {t.tabSimilar}
              </TabsTrigger>
            </TabsList>
          </Tabs>

          {mode === "query" ? (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                runQuery(query)
              }}
            >
              <InputGroup className="h-11">
                <InputGroupAddon>
                  <Search />
                </InputGroupAddon>
                <InputGroupInput
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t.queryPlaceholder}
                  className="text-[15px]"
                />
                <InputGroupAddon align="inline-end">
                  <Kbd className="hidden sm:inline-flex">Enter</Kbd>
                  <InputGroupButton type="submit" variant="default" size="sm" disabled={!query.trim()}>
                    {t.search}
                  </InputGroupButton>
                </InputGroupAddon>
              </InputGroup>
            </form>
          ) : (
            <RepoPicker
              names={repoNames}
              value={request?.mode === "similar" ? request.text : null}
              onPick={runSimilar}
            />
          )}

          {!request && mode === "query" && (
            <div className="flex flex-wrap gap-1.5">
              {t.examples.map((ex) => (
                <Button key={ex} variant="outline" size="sm" className="text-[12.5px]" onClick={() => runQuery(ex)}>
                  {ex}
                </Button>
              ))}
            </div>
          )}

          <ResultsHeader request={request} count={results?.length} loading={loading} />

          {error ? (
            <Empty className="glass-panel rounded-md">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <SearchX />
                </EmptyMedia>
                <EmptyTitle>{t.errorTitle}</EmptyTitle>
                <EmptyDescription>{error}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : loading && !results ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-32 rounded-xl" />
              ))}
            </div>
          ) : results && results.length === 0 ? (
            <Empty className="glass-panel rounded-md">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <SearchX />
                </EmptyMedia>
                <EmptyTitle>{t.emptyTitle}</EmptyTitle>
                <EmptyDescription>{t.emptyHint}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <ol className={cn("flex flex-col gap-3 transition-opacity", loading && "opacity-60")}>
              {results?.map((r, i) => (
                <li key={r.full_name}>
                  <ResultCard rank={i + 1} result={r} onSimilar={runSimilar} />
                </li>
              ))}
            </ol>
          )}
        </main>
      </div>
    </div>
  )
}

function Header({ meta }: { meta: Meta | null }) {
  const { t, lang, setLang } = useI18n()
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"))
  const toggle = () => {
    const next = !dark
    document.documentElement.classList.toggle("dark", next)
    try {
      localStorage.setItem("tf:theme", next ? "dark" : "light")
    } catch {
      /* private mode: theme just isn't remembered */
    }
    setDark(next)
  }
  return (
    <header className="flex items-center gap-3">
      <div className="glass-chosen flex size-9 items-center justify-center rounded-md">
        <Search className="size-4" />
      </div>
      <div className="mr-auto min-w-0">
        <h1 className="text-[17px] font-semibold tracking-tight">Trendshift Finder</h1>
        <p className="truncate text-[12.5px] text-muted-foreground">
          {meta ? (
            <>
              {t.subtitle(meta.count.toLocaleString())} ·{" "}
              <span className="tabular-nums">
                {meta.first_day} ~ {meta.latest_day}
              </span>
            </>
          ) : (
            t.loadingIndex
          )}
        </p>
      </div>
      <Button variant="ghost" size="sm" onClick={() => setLang(lang === "ko" ? "en" : "ko")}>
        <Languages /> {t.switchLang}
      </Button>
      <Button variant="ghost" size="icon" aria-label={dark ? t.lightMode : t.darkMode} onClick={toggle}>
        {dark ? <Sun /> : <Moon />}
      </Button>
    </header>
  )
}

function RepoPicker({ names, value, onPick }: { names: string[]; value: string | null; onPick: (n: string) => void }) {
  const { t } = useI18n()
  const [input, setInput] = useState(value ?? "")
  useEffect(() => setInput(value ?? ""), [value])
  // 5k names is too many to render; show the best 50 matches (prefix matches of the repo name first).
  const items = useMemo(() => {
    const q = input.trim().toLowerCase()
    if (!q) return names.slice(0, 50)
    const scored = names
      .map((n) => {
        const lower = n.toLowerCase()
        const i = lower.indexOf(q)
        if (i < 0) return null
        const repoStart = lower.indexOf("/") + 1
        return { n, s: i === repoStart ? 0 : i === 0 ? 1 : 2 }
      })
      .filter((x): x is { n: string; s: number } => x !== null)
    return scored.sort((a, b) => a.s - b.s).slice(0, 50).map((x) => x.n)
  }, [names, input])

  return (
    <Combobox
      items={items}
      value={value}
      inputValue={input}
      onInputValueChange={setInput}
      onValueChange={(v) => v && onPick(v as string)}
      filter={null}
      autoHighlight
    >
      <ComboboxInput placeholder={t.pickerPlaceholder} className="h-11 text-[15px]" showClear />
      <ComboboxContent>
        <ComboboxEmpty>{t.pickerEmpty}</ComboboxEmpty>
        <ComboboxList>
          {(item: string) => (
            <ComboboxItem key={item} value={item} className="font-mono text-[12.5px]">
              {item}
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  )
}

function ResultsHeader({ request, count, loading }: { request: Request | null; count?: number; loading: boolean }) {
  const { t } = useI18n()
  if (!request) return null
  return (
    <div className="flex h-5 items-center gap-2 text-[12.5px] text-muted-foreground">
      {request.mode === "query" ? (
        <span className="truncate text-foreground">{t.similarToQuery(request.text)}</span>
      ) : (
        <span className="truncate">
          <span className="font-mono text-foreground">{request.text}</span>{t.similarToRepo}
        </span>
      )}
      {count !== undefined && !loading && <span className="tabular-nums">· {t.count(count)}</span>}
      {loading && <DotLoader />}
    </div>
  )
}

function ResultCard({ rank, result: r, onSimilar }: { rank: number; result: Result; onSimilar: (n: string) => void }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [owner, name] = r.full_name.split("/")
  return (
    <Card size="sm" className="gap-3">
      <CardHeader className="gap-1.5">
        <div className="flex min-w-0 items-start gap-3">
          <span className="mt-0.5 w-5 shrink-0 text-right text-[12px] text-muted-foreground tabular-nums">{rank}</span>
          <div className="min-w-0 flex-1">
            <CardTitle className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <a
                href={`https://github.com/${r.full_name}`}
                target="_blank"
                rel="noreferrer"
                className="group inline-flex min-w-0 items-center gap-1 text-[15px] hover:underline"
              >
                <span className="truncate">
                  <span className="font-normal text-muted-foreground">{owner}/</span>
                  {name}
                </span>
                <ExternalLink className="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
              </a>
              {r.language && (
                <Badge variant="outline" className="font-mono text-[11px]">
                  {r.language}
                </Badge>
              )}
            </CardTitle>
            <CardDescription className="mt-1 line-clamp-2 text-[13.5px]">
              {r.description || <span className="italic">{t.noDescription}</span>}
            </CardDescription>
          </div>
          <Similarity value={r.similarity} />
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-3 pl-12">
        {r.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {r.tags.map((t) => (
              <Tag key={t}>{t}</Tag>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted-foreground">
          <span className="inline-flex items-center gap-1 tabular-nums">
            <Star className="size-3.5" /> {r.stars.toLocaleString()}
          </span>
          <span className="tabular-nums">
            {t.trendedDays(r.appearances, r.best_rank)}
          </span>
          <span className="tabular-nums">
            {r.first_seen === r.last_seen ? r.first_seen : `${r.first_seen} ~ ${r.last_seen}`}
          </span>
          <span className="ml-auto flex gap-1">
            {r.readme_excerpt && (
              <Button variant="ghost" size="xs" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
                README
                <ChevronDown className={cn("transition-transform", open && "rotate-180")} />
              </Button>
            )}
            <Button variant="ghost" size="xs" onClick={() => onSimilar(r.full_name)}>
              <GitFork /> {t.similar}
            </Button>
          </span>
        </div>

        {open && (
          <p className="glass-panel rounded-md p-3 text-[12.5px] leading-relaxed whitespace-pre-line text-foreground/80">
            {r.readme_excerpt}
            {r.readme_excerpt.length >= 400 && "…"}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

/** bge-m3 cosine scores for relevant hits sit around 0.45–0.8; stretch that range over the bar. */
function Similarity({ value }: { value: number }) {
  const { t } = useI18n()
  const pct = Math.max(0, Math.min(1, (value - 0.35) / 0.5)) * 100
  return (
    <div className="flex w-16 shrink-0 flex-col items-end gap-1" title={t.cosine}>
      <span className="text-[13px] font-medium tabular-nums">{value.toFixed(3)}</span>
      <span className="h-1 w-full overflow-hidden rounded-full bg-muted">
        <span className="block h-full rounded-full bg-primary/80" style={{ width: `${pct}%` }} />
      </span>
    </div>
  )
}

function Field({
  label,
  value,
  hint,
  children,
}: {
  label: string
  value?: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-2">
        <Label className="text-[12px] text-muted-foreground">{label}</Label>
        {value && <span className="text-[12px] tabular-nums">{value}</span>}
      </div>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  )
}

function SliderField({
  label,
  value,
  format,
  min,
  max,
  step,
  onChange,
  hint,
}: {
  label: string
  value: number
  format: (v: number) => string
  min: number
  max: number
  step: number
  onChange: (v: number) => void
  hint?: string
}) {
  // Track the thumb locally and only commit on release, so dragging doesn't fire a search per step.
  const [local, setLocal] = useState(value)
  useEffect(() => setLocal(value), [value])
  return (
    <Field label={label} value={format(local)} hint={hint}>
      <Slider
        value={[local]}
        min={min}
        max={max}
        step={step}
        onValueChange={(v) => setLocal(Array.isArray(v) ? v[0] : v)}
        onValueCommitted={(v) => onChange(Array.isArray(v) ? v[0] : v)}
      />
    </Field>
  )
}
