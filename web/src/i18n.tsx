import { createContext, useCallback, useContext, useEffect, useState } from "react"

export type Lang = "ko" | "en"

const ko = {
  filters: "필터",
  language: "언어",
  all: "전체",
  period: "트렌딩 시기",
  periodAll: "전체",
  period365: "1년",
  period180: "6개월",
  period90: "3개월",
  period30: "1개월",
  since: (d: string) => `${d} 이후`,
  minStars: "최소 스타",
  noLimit: "제한 없음",
  readmeWeight: "README 반영",
  readmeHint: "0% = 이름·설명·태그만",
  popularity: "인기도 가중치",
  popularityHint: "오래 트렌딩된 저장소 우대",
  resultCount: "결과 수",
  tabQuery: "설명으로 찾기",
  tabSimilar: "비슷한 저장소",
  queryPlaceholder: "어떤 프로젝트가 필요한가요? 한국어·영어 모두 됩니다",
  search: "검색",
  examples: [
    "로컬에서 돌리는 음성 인식",
    "PDF 문서를 마크다운으로 변환",
    "코드베이스를 지식 그래프로 시각화",
    "자체 호스팅 가능한 노션 대체",
    "주식 트레이딩 봇 백테스트",
  ],
  errorTitle: "문제가 생겼어요",
  emptyTitle: "조건에 맞는 저장소가 없어요",
  emptyHint: "필터(언어·시기·스타)를 넓혀 보세요.",
  subtitle: (count: string) => `trendshift.io 일간 트렌딩 저장소 ${count}개`,
  loadingIndex: "인덱스 불러오는 중…",
  lightMode: "라이트 모드",
  darkMode: "다크 모드",
  switchLang: "English",
  pickerPlaceholder: "기준 저장소 (owner/repo) — 트렌딩 기간이 긴 순",
  pickerEmpty: "인덱스에 없는 저장소예요.",
  similarToQuery: (q: string) => `“${q}”와 비슷한 저장소`,
  similarToRepo: "와 비슷한 저장소",
  count: (n: number) => `${n}개`,
  noDescription: "설명 없음",
  trendedDays: (days: number, rank: number) => `${days}일 트렌딩 · 최고 #${rank}`,
  similar: "비슷한 저장소",
  cosine: "코사인 유사도",
}

type Messages = typeof ko

const en: Messages = {
  filters: "Filters",
  language: "Language",
  all: "All",
  period: "Trended",
  periodAll: "All",
  period365: "1y",
  period180: "6m",
  period90: "3m",
  period30: "1m",
  since: (d) => `since ${d}`,
  minStars: "Min stars",
  noLimit: "Any",
  readmeWeight: "README weight",
  readmeHint: "0% = name, description, tags only",
  popularity: "Popularity boost",
  popularityHint: "Favors repos that trended longer",
  resultCount: "Results",
  tabQuery: "Describe it",
  tabSimilar: "Similar repos",
  queryPlaceholder: "What kind of project do you need? Any language works",
  search: "Search",
  examples: [
    "Local speech recognition",
    "Convert PDF documents to Markdown",
    "Visualize a codebase as a knowledge graph",
    "Self-hosted Notion alternative",
    "Backtest a stock trading bot",
  ],
  errorTitle: "Something went wrong",
  emptyTitle: "No repositories match",
  emptyHint: "Try widening the filters (language, period, stars).",
  subtitle: (count) => `${count} daily trending repos from trendshift.io`,
  loadingIndex: "Loading index…",
  lightMode: "Light mode",
  darkMode: "Dark mode",
  switchLang: "한국어",
  pickerPlaceholder: "Base repository (owner/repo) — most trended first",
  pickerEmpty: "Not in the index.",
  similarToQuery: (q) => `Repos similar to “${q}”`,
  similarToRepo: " — similar repos",
  count: (n) => `${n} results`,
  noDescription: "No description",
  trendedDays: (days, rank) => `Trended ${days} day${days === 1 ? "" : "s"} · best #${rank}`,
  similar: "Similar",
  cosine: "Cosine similarity",
}

const MESSAGES: Record<Lang, Messages> = { ko, en }

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem("tf:lang")
    if (saved === "ko" || saved === "en") return saved
  } catch {
    /* storage blocked: fall back to the browser language */
  }
  return navigator.language.toLowerCase().startsWith("ko") ? "ko" : "en"
}

const I18nContext = createContext<{ lang: Lang; t: Messages; setLang: (l: Lang) => void }>({
  lang: "ko",
  t: ko,
  setLang: () => {},
})

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang)
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])
  const setLang = useCallback((l: Lang) => {
    try {
      localStorage.setItem("tf:lang", l)
    } catch {
      /* private mode: choice just isn't remembered */
    }
    setLangState(l)
  }, [])
  return <I18nContext.Provider value={{ lang, t: MESSAGES[lang], setLang }}>{children}</I18nContext.Provider>
}

export const useI18n = () => useContext(I18nContext)
