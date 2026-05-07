/**
 * i18n.ts — flat key/value translation dictionary.
 *
 * Rules:
 *  - Stock tickers and company names (name, name_kr) are NEVER translated here.
 *    They are data, not UI strings.
 *  - Only UI chrome strings live here: nav labels, headings, placeholders,
 *    button labels, section titles, filter labels.
 *  - Korean uses 존댓말 (polite speech) throughout.
 */

export type Lang = "en" | "ko";

export type TranslationKey =
  // ── Nav ──────────────────────────────────────────────────────────────────
  | "nav.rankings"
  | "nav.search"
  | "nav.strategies"
  | "nav.alerts"
  | "nav.regime"
  | "nav.openApp"
  | "nav.methodology"
  | "nav.dataSources"
  | "nav.freshness"
  | "nav.disclosures"
  // ── Language toggle ──────────────────────────────────────────────────────
  | "lang.toggle.en"
  | "lang.toggle.ko"
  // ── Landing page ─────────────────────────────────────────────────────────
  | "home.kicker"
  | "home.headline1"
  | "home.headline2"
  | "home.sub"
  | "home.cta.app"
  | "home.cta.methodology"
  | "home.stats.universe.label"
  | "home.stats.universe.value"
  | "home.stats.universe.sub"
  | "home.stats.strategies.label"
  | "home.stats.strategies.value"
  | "home.stats.strategies.sub"
  | "home.stats.data.label"
  | "home.stats.data.value"
  | "home.stats.data.sub"
  | "home.features.kicker"
  | "home.features.headline"
  | "home.features.search.title"
  | "home.features.search.body"
  | "home.features.coverage.title"
  | "home.features.coverage.body"
  | "home.features.chart.title"
  | "home.features.chart.body"
  | "home.features.regime.title"
  | "home.features.regime.body"
  | "home.direction.kicker"
  | "home.direction.headline1"
  | "home.direction.headline2"
  | "home.direction.body"
  | "home.next.kicker"
  | "home.next.headline"
  | "home.next.body"
  | "home.next.cta"
  | "home.footer.disclaimer"
  | "home.leaderboard.kicker"
  | "home.leaderboard.ranked"
  | "home.leaderboard.viewAll"
  | "home.how.title"
  | "home.how.step1.title"
  | "home.how.step1.body"
  | "home.how.step2.title"
  | "home.how.step2.body"
  | "home.how.step3.title"
  | "home.how.step3.body"
  // ── Search page ───────────────────────────────────────────────────────────
  | "search.kicker"
  | "search.headline"
  | "search.sub"
  | "search.placeholder"
  | "search.filter.allMarkets"
  | "search.filter.allTypes"
  | "search.pinned"
  | "search.recent"
  | "search.pinEmpty"
  | "search.recentEmpty"
  | "search.results"
  | "search.fetching"
  | "search.matches"
  | "search.empty"
  | "search.noResults"
  | "search.startPrompt"
  // ── Rankings page ─────────────────────────────────────────────────────────
  | "rankings.kicker"
  | "rankings.headline"
  | "rankings.sub"
  | "rankings.stat.loaded"
  | "rankings.stat.requested"
  | "rankings.stat.topScore"
  | "rankings.stat.average"
  | "rankings.stat.freshness"
  | "rankings.stat.refreshing"
  | "rankings.stat.activeFilters"
  | "rankings.controls.kicker"
  | "rankings.controls.usMarket"
  | "rankings.controls.krMarket"
  | "rankings.controls.resultCount"
  | "rankings.controls.top"
  | "rankings.lens.kicker"
  | "rankings.presets.kicker"
  | "rankings.presets.headline"
  | "rankings.presets.reset"
  | "rankings.presets.advanced"
  | "rankings.filters.conviction"
  | "rankings.filters.coverage"
  | "rankings.filters.finalScore"
  | "rankings.filters.strategyCount"
  | "rankings.filters.technical"
  | "rankings.filters.rsNewHigh"
  | "rankings.filters.anyConviction"
  | "rankings.filters.anyCoverage"
  | "rankings.filters.noMinimum"
  | "rankings.filters.noPassing"
  | "rankings.filters.any"
  | "rankings.filters.required"
  | "rankings.filters.exclude"
  | "rankings.regime.warning"
  | "rankings.leaderboard.eyebrow"
  | "rankings.leaderboard.subtitle"
  | "rankings.leaderboard.showing"
  | "rankings.leaderboard.loadMore"
  | "rankings.leaderboard.refreshing"
  | "rankings.leaderboard.error"
  | "rankings.leaderboard.empty"
  | "rankings.partial.eyebrow"
  | "rankings.partial.title"
  | "rankings.partial.subtitle"
  | "rankings.partial.loadMore"
  | "rankings.partial.error"
  | "rankings.partial.empty"
  | "rankings.explore.eyebrow"
  | "rankings.explore.title"
  | "rankings.explore.subtitle"
  | "rankings.explore.loadMore"
  | "rankings.explore.error"
  | "rankings.explore.empty"
  | "rankings.watchlist.eyebrow"
  | "rankings.watchlist.title"
  | "rankings.watchlist.empty"
  | "rankings.watchlist.signIn"
  // ── Shared UI ─────────────────────────────────────────────────────────────
  | "ui.pin"
  | "ui.pinned"
  | "ui.open"
  | "ui.strategies"
  | "ui.regime"
  | "ui.conviction"
  | "ui.needsScoring"
  | "ui.explore"
  | "ui.allCoverage"
  | "ui.stock"
  // ── Conviction levels ─────────────────────────────────────────────────────
  | "conviction.diamond"
  | "conviction.platinum"
  | "conviction.gold"
  | "conviction.silver"
  | "conviction.bronze"
  | "conviction.unranked"
  // ── Alerts page ───────────────────────────────────────────────────────────
  | "alerts.kicker"
  | "alerts.headline"
  | "alerts.sub"
  // ── Market regime page ────────────────────────────────────────────────────
  | "regime.kicker"
  | "regime.headline"
  | "regime.sub";

type Dictionary = Record<TranslationKey, string>;

export const translations: Record<Lang, Dictionary> = {
  en: {
    // Nav
    "nav.rankings":          "Rankings",
    "nav.search":            "Search",
    "nav.strategies":        "Strategies",
    "nav.alerts":            "Alerts",
    "nav.regime":            "Regime",
    "nav.openApp":           "Open App",
    "nav.methodology":       "Methodology",
    "nav.dataSources":       "Data Sources",
    "nav.freshness":         "Freshness",
    "nav.disclosures":       "Disclosures",
    // Language toggle
    "lang.toggle.en":        "EN",
    "lang.toggle.ko":        "KO",
    // Landing
    "home.kicker":                     "Production research for US + Korea",
    "home.headline1":                  "Search Everything.",
    "home.headline2":                  "Rank What You Can Defend.",
    "home.sub":                        "Consensus Signal Research is a full-market search, ranking, and chart workspace for US and Korean equities. Honest coverage, regime-aware conviction levels, nightly data.",
    "home.cta.app":                    "Open Research App",
    "home.cta.methodology":            "Read methodology",
    "home.stats.universe.label":       "Universe",
    "home.stats.universe.value":       "6,500+",
    "home.stats.universe.sub":         "US + KR equities",
    "home.stats.strategies.label":     "Strategies",
    "home.stats.strategies.value":     "3",
    "home.stats.strategies.sub":       "CANSLIM · Piotroski · Magic Formula",
    "home.stats.data.label":           "Market data",
    "home.stats.data.value":           "Nightly",
    "home.stats.data.sub":             "KR live path, US delayed",
    "home.features.kicker":            "What's inside",
    "home.features.headline":          "Built for how research actually works.",
    "home.features.search.title":      "Full-market search",
    "home.features.search.body":       "Search every covered US and KR symbol, then open a chart workspace even when a stock is not yet fully ranked.",
    "home.features.coverage.title":    "Coverage-aware ranking",
    "home.features.coverage.body":     "The product separates symbols that need more data, scoring, or freshness repair from ranked names so the board stays honest about what it knows.",
    "home.features.chart.title":       "Research chart workspace",
    "home.features.chart.body":        "Move from rankings into a single-stock desk with price structure, relative strength, patterns, and freshness context in one place.",
    "home.features.regime.title":      "Market-state discipline",
    "home.features.regime.body":       "US and KR regime boards stay visible so rank interpretation is grounded in actual market posture instead of blind score chasing.",
    "home.direction.kicker":           "Fresh build direction",
    "home.direction.headline1":        "Public site outside,",
    "home.direction.headline2":        "working desk inside.",
    "home.direction.body":             "The public surface explains methodology, data contracts, freshness, and disclosures. The app is where rankings, symbol search, and instrument workspaces live — kept separate to stay sharp and easy to trust at launch.",
    "home.next.kicker":                "Next action",
    "home.next.headline":              "Try the production shell",
    "home.next.body":                  "The app shell exposes canonical routes, a search-first entry, and coverage-aware instrument pages. Rankings update nightly.",
    "home.next.cta":                   "Open search",
    "home.footer.disclaimer":          "Not investment advice.",
    "home.leaderboard.kicker":         "Live research desk",
    "home.leaderboard.ranked":         "ranked",
    "home.leaderboard.viewAll":        "View full rankings",
    "home.how.title":                  "How it works",
    "home.how.step1.title":            "Ingest",
    "home.how.step1.body":             "We pull price, volume, fundamentals and filings for 6,500+ US and Korean equities every trading day.",
    "home.how.step2.title":            "Score",
    "home.how.step2.body":             "Five independent models — CANSLIM, Piotroski, Minervini, Weinstein and Dual Momentum — grade each name 0–100.",
    "home.how.step3.title":            "Rank",
    "home.how.step3.body":             "A conviction-weighted consensus score surfaces the names where multiple strategies agree. No single-model noise.",
    // Search
    "search.kicker":           "Symbol Search",
    "search.headline":         "Search the covered universe first.",
    "search.sub":              "Search by ticker, company, Korean name, or exchange. The result list shows whether a symbol needs price data, needs fundamentals, needs scoring, is stale, or is fully ranked.",
    "search.placeholder":      "AAPL, Samsung, semiconductors, NYSE…",
    "search.filter.allMarkets":"All Markets",
    "search.filter.allTypes":  "All Types",
    "search.pinned":           "Pinned symbols",
    "search.recent":           "Recent searches",
    "search.pinEmpty":         "Pin symbols from a result row to keep them nearby.",
    "search.recentEmpty":      "Your recent search trail will appear here.",
    "search.results":          "Results",
    "search.fetching":         "Searching…",
    "search.matches":          "matches",
    "search.empty":            "No matching symbols were found in the current covered universe.",
    "search.noResults":        "No matching symbols were found in the current covered universe.",
    "search.startPrompt":      "Start with a ticker, company, or Korean name.",
    // Rankings
    "rankings.kicker":                  "Production rankings desk",
    "rankings.headline":                "Signal Board",
    "rankings.sub":                     "Ranked names stay score-backed. Partial and explore rows sit underneath so we can surface more of the US/KR universe without pretending incomplete data is ranked.",
    "rankings.stat.loaded":             "Loaded",
    "rankings.stat.requested":          "requested",
    "rankings.stat.topScore":           "Top score",
    "rankings.stat.average":            "Average",
    "rankings.stat.freshness":          "Freshness",
    "rankings.stat.refreshing":         "Refreshing view",
    "rankings.stat.activeFilters":      "active filters",
    "rankings.controls.kicker":         "Market and result controls",
    "rankings.controls.usMarket":       "US Market",
    "rankings.controls.krMarket":       "Korea Market",
    "rankings.controls.resultCount":    "Result count",
    "rankings.controls.top":            "Top",
    "rankings.lens.kicker":             "Current lens",
    "rankings.presets.kicker":          "Strategy presets",
    "rankings.presets.headline":        "Gentle filters, not a black box.",
    "rankings.presets.reset":           "Reset filters",
    "rankings.presets.advanced":        "Advanced filter panel",
    "rankings.filters.conviction":      "Conviction",
    "rankings.filters.coverage":        "Coverage",
    "rankings.filters.finalScore":      "Final score",
    "rankings.filters.strategyCount":   "Strategy count",
    "rankings.filters.technical":       "Technical",
    "rankings.filters.rsNewHigh":       "RS New High",
    "rankings.filters.anyConviction":   "Any conviction",
    "rankings.filters.anyCoverage":     "Any coverage",
    "rankings.filters.noMinimum":       "No minimum",
    "rankings.filters.noPassing":       "No minimum",
    "rankings.filters.any":             "Any",
    "rankings.filters.required":        "Required",
    "rankings.filters.exclude":         "Exclude",
    "rankings.regime.warning":          "ranked instruments have an active regime warning.",
    "rankings.leaderboard.eyebrow":     "Ranked results",
    "rankings.leaderboard.subtitle":    "These rows are backed by stored consensus scores. Use filters to narrow the ranked board without changing the underlying order.",
    "rankings.leaderboard.showing":     "Showing",
    "rankings.leaderboard.loadMore":    "Load more ranked names",
    "rankings.leaderboard.refreshing":  "Refreshing the desk",
    "rankings.leaderboard.error":       "Rankings are temporarily unavailable.",
    "rankings.leaderboard.empty":       "No ranked instruments match this lens yet. Try removing thresholds or browse the incomplete universe below.",
    "rankings.partial.eyebrow":         "Partial rows",
    "rankings.partial.title":           "Ready for scoring",
    "rankings.partial.subtitle":        "These symbols have enough persisted coverage to be interesting, but they are not part of the ranked board until scoring runs.",
    "rankings.partial.loadMore":        "Load more partial rows",
    "rankings.partial.error":           "Partial rows are unavailable, but ranked results are unaffected.",
    "rankings.partial.empty":           "No needs-scoring symbols are available for this market yet.",
    "rankings.explore.eyebrow":         "Explore more",
    "rankings.explore.title":           "Known but incomplete",
    "rankings.explore.subtitle":        "Discovery-only rows from the covered universe. They do not affect ranking totals and never claim a score they do not have.",
    "rankings.explore.loadMore":        "Load more explore rows",
    "rankings.explore.error":           "Explore More is unavailable, but ranked results are unaffected.",
    "rankings.explore.empty":           "No additional discoverable rows match this market and asset type.",
    "rankings.watchlist.eyebrow":       "Your watchlist",
    "rankings.watchlist.title":         "Pinned instruments",
    "rankings.watchlist.empty":         "No pinned instruments for this market yet. Pin a row from the board below.",
    "rankings.watchlist.signIn":        "Sign in to sync your watchlist across devices.",
    // Shared
    "ui.pin":          "Pin",
    "ui.pinned":       "Pinned",
    "ui.open":         "Open",
    "ui.strategies":   "strategies",
    "ui.regime":       "regime",
    "ui.conviction":   "conviction",
    "ui.needsScoring": "Needs scoring",
    "ui.explore":      "Explore",
    "ui.allCoverage":  "All coverage",
    "ui.stock":        "STOCK",
    // Conviction
    "conviction.diamond":  "Diamond",
    "conviction.platinum": "Platinum",
    "conviction.gold":     "Gold",
    "conviction.silver":   "Silver",
    "conviction.bronze":   "Bronze",
    "conviction.unranked": "Unranked",
    // Alerts
    "alerts.kicker":   "Push alerts",
    "alerts.headline": "Conviction alerts",
    "alerts.sub":      "Get notified when an instrument crosses a conviction level.",
    // Regime
    "regime.kicker":   "Market posture",
    "regime.headline": "Market regime",
    "regime.sub":      "US and KR regime boards updated nightly.",
  },

  ko: {
    // Nav
    "nav.rankings":          "랭킹",
    "nav.search":            "검색",
    "nav.strategies":        "전략",
    "nav.alerts":            "알림",
    "nav.regime":            "시장 국면",
    "nav.openApp":           "앱 열기",
    "nav.methodology":       "방법론",
    "nav.dataSources":       "데이터 출처",
    "nav.freshness":         "데이터 현황",
    "nav.disclosures":       "고지사항",
    // Language toggle
    "lang.toggle.en":        "EN",
    "lang.toggle.ko":        "KO",
    // Landing
    "home.kicker":                     "미국 + 한국 주식 리서치 플랫폼",
    "home.headline1":                  "모든 종목을 검색하고.",
    "home.headline2":                  "근거 있는 순위만 제시합니다.",
    "home.sub":                        "Consensus Signal Research는 미국과 한국 주식 시장을 위한 전종목 검색·랭킹·차트 워크스페이스입니다. 투명한 커버리지, 시장 국면 반영 신뢰 등급, 매일 밤 업데이트.",
    "home.cta.app":                    "리서치 앱 열기",
    "home.cta.methodology":            "방법론 읽기",
    "home.stats.universe.label":       "종목 수",
    "home.stats.universe.value":       "6,500+",
    "home.stats.universe.sub":         "미국 + 한국 주식",
    "home.stats.strategies.label":     "전략 수",
    "home.stats.strategies.value":     "3",
    "home.stats.strategies.sub":       "CANSLIM · 피오트로스키 · 마법 공식",
    "home.stats.data.label":           "시장 데이터",
    "home.stats.data.value":           "매일 밤",
    "home.stats.data.sub":             "한국 실시간, 미국 지연",
    "home.features.kicker":            "주요 기능",
    "home.features.headline":          "실제 리서치 방식에 맞게 설계했습니다.",
    "home.features.search.title":      "전종목 검색",
    "home.features.search.body":       "미국·한국 커버리지 내 모든 종목을 검색하고, 아직 완전히 랭크되지 않은 종목도 차트 워크스페이스에서 열 수 있습니다.",
    "home.features.coverage.title":    "커버리지 기반 랭킹",
    "home.features.coverage.body":     "데이터·스코어링·최신성이 부족한 종목과 완전히 랭크된 종목을 분리하여 보드의 정직성을 유지합니다.",
    "home.features.chart.title":       "리서치 차트 워크스페이스",
    "home.features.chart.body":        "랭킹에서 개별 종목 데스크로 이동하면 가격 구조, 상대 강도, 패턴, 최신성 컨텍스트를 한 화면에서 확인할 수 있습니다.",
    "home.features.regime.title":      "시장 국면 규율",
    "home.features.regime.body":       "미국·한국 시장 국면 보드를 항상 표시하여, 점수 추적이 아닌 실제 시장 흐름에 근거한 순위 해석을 지원합니다.",
    "home.direction.kicker":           "제품 방향",
    "home.direction.headline1":        "공개 사이트는 외부에,",
    "home.direction.headline2":        "실무 데스크는 내부에.",
    "home.direction.body":             "공개 페이지에서는 방법론·데이터 계약·최신성·고지사항을 설명합니다. 앱에서는 랭킹·종목 검색·차트 워크스페이스를 제공합니다.",
    "home.next.kicker":                "다음 단계",
    "home.next.headline":              "프로덕션 앱 체험",
    "home.next.body":                  "앱 셸은 정규 경로, 검색 우선 진입, 커버리지 인식 종목 페이지를 제공합니다. 랭킹은 매일 밤 업데이트됩니다.",
    "home.next.cta":                   "검색 열기",
    "home.footer.disclaimer":          "투자 조언이 아닙니다.",
    "home.leaderboard.kicker":         "실시간 리서치 데스크",
    "home.leaderboard.ranked":         "랭크됨",
    "home.leaderboard.viewAll":        "전체 랭킹 보기",
    "home.how.title":                  "작동 방식",
    "home.how.step1.title":            "수집",
    "home.how.step1.body":             "매 거래일마다 미국·한국 주식 6,500개 이상의 가격, 거래량, 재무 지표, 공시 데이터를 수집합니다.",
    "home.how.step2.title":            "채점",
    "home.how.step2.body":             "CANSLIM, 피오트로스키, 미너비니, 와인스타인, 듀얼 모멘텀 — 5가지 독립 모델이 각 종목을 0~100점으로 평가합니다.",
    "home.how.step3.title":            "순위",
    "home.how.step3.body":             "신뢰 가중 컨센서스 점수가 여러 전략이 동의하는 종목을 상위로 올립니다. 단일 모델 노이즈 없음.",
    // Search
    "search.kicker":           "종목 검색",
    "search.headline":         "커버리지 내 종목을 먼저 검색하세요.",
    "search.sub":              "티커, 회사명, 한국어 이름, 거래소로 검색할 수 있습니다. 결과 목록에서 가격 데이터·펀더멘털·스코어링 필요 여부, 최신성, 완전 랭크 상태를 확인할 수 있습니다.",
    "search.placeholder":      "AAPL, 삼성전자, 반도체, NYSE…",
    "search.filter.allMarkets":"전체 시장",
    "search.filter.allTypes":  "전체 유형",
    "search.pinned":           "고정 종목",
    "search.recent":           "최근 검색",
    "search.pinEmpty":         "결과 행에서 종목을 고정하면 여기에 표시됩니다.",
    "search.recentEmpty":      "최근 검색한 종목이 여기에 표시됩니다.",
    "search.results":          "결과",
    "search.fetching":         "검색 중…",
    "search.matches":          "개 결과",
    "search.empty":            "현재 커버리지에서 일치하는 종목을 찾을 수 없습니다.",
    "search.noResults":        "현재 커버리지에서 일치하는 종목을 찾을 수 없습니다.",
    "search.startPrompt":      "티커, 회사명, 또는 한국어 이름으로 시작하세요.",
    // Rankings
    "rankings.kicker":                  "프로덕션 랭킹 데스크",
    "rankings.headline":                "시그널 보드",
    "rankings.sub":                     "랭크된 종목은 점수로 뒷받침됩니다. 불완전한 데이터를 랭크된 것처럼 표시하지 않고, 파셜·탐색 행을 별도로 제공합니다.",
    "rankings.stat.loaded":             "로드됨",
    "rankings.stat.requested":          "요청",
    "rankings.stat.topScore":           "최고 점수",
    "rankings.stat.average":            "평균",
    "rankings.stat.freshness":          "최신성",
    "rankings.stat.refreshing":         "새로고침 중",
    "rankings.stat.activeFilters":      "개 필터 적용 중",
    "rankings.controls.kicker":         "시장 및 결과 설정",
    "rankings.controls.usMarket":       "미국 시장",
    "rankings.controls.krMarket":       "한국 시장",
    "rankings.controls.resultCount":    "결과 수",
    "rankings.controls.top":            "상위",
    "rankings.lens.kicker":             "현재 필터",
    "rankings.presets.kicker":          "전략 프리셋",
    "rankings.presets.headline":        "블랙박스가 아닌 투명한 필터.",
    "rankings.presets.reset":           "필터 초기화",
    "rankings.presets.advanced":        "고급 필터 패널",
    "rankings.filters.conviction":      "신뢰 등급",
    "rankings.filters.coverage":        "커버리지",
    "rankings.filters.finalScore":      "최종 점수",
    "rankings.filters.strategyCount":   "전략 수",
    "rankings.filters.technical":       "기술적 지표",
    "rankings.filters.rsNewHigh":       "RS 신고가",
    "rankings.filters.anyConviction":   "전체 신뢰 등급",
    "rankings.filters.anyCoverage":     "전체 커버리지",
    "rankings.filters.noMinimum":       "최소값 없음",
    "rankings.filters.noPassing":       "최소값 없음",
    "rankings.filters.any":             "전체",
    "rankings.filters.required":        "필수",
    "rankings.filters.exclude":         "제외",
    "rankings.regime.warning":          "개 종목에 시장 국면 경고가 있습니다.",
    "rankings.leaderboard.eyebrow":     "랭크된 결과",
    "rankings.leaderboard.subtitle":    "이 행들은 저장된 컨센서스 점수로 뒷받침됩니다. 필터를 사용하여 기본 순서를 바꾸지 않고 보드를 좁힐 수 있습니다.",
    "rankings.leaderboard.showing":     "표시 중",
    "rankings.leaderboard.loadMore":    "랭크 종목 더 보기",
    "rankings.leaderboard.refreshing":  "데스크 새로고침 중",
    "rankings.leaderboard.error":       "랭킹을 일시적으로 사용할 수 없습니다.",
    "rankings.leaderboard.empty":       "이 필터에 맞는 랭크 종목이 없습니다. 임계값을 제거하거나 아래의 불완전 종목을 탐색해 보세요.",
    "rankings.partial.eyebrow":         "파셜 행",
    "rankings.partial.title":           "스코어링 대기 중",
    "rankings.partial.subtitle":        "커버리지는 충분하지만 스코어링이 완료되지 않아 랭크 보드에 포함되지 않은 종목입니다.",
    "rankings.partial.loadMore":        "파셜 행 더 보기",
    "rankings.partial.error":           "파셜 행을 사용할 수 없지만 랭크 결과에는 영향이 없습니다.",
    "rankings.partial.empty":           "이 시장에서 스코어링이 필요한 종목이 아직 없습니다.",
    "rankings.explore.eyebrow":         "더 탐색",
    "rankings.explore.title":           "알려졌지만 불완전",
    "rankings.explore.subtitle":        "커버리지 내 탐색 전용 행입니다. 랭킹 합계에 영향을 주지 않으며, 없는 점수를 주장하지 않습니다.",
    "rankings.explore.loadMore":        "탐색 행 더 보기",
    "rankings.explore.error":           "탐색 더 보기를 사용할 수 없지만 랭크 결과에는 영향이 없습니다.",
    "rankings.explore.empty":           "이 시장 및 자산 유형에 맞는 추가 탐색 행이 없습니다.",
    "rankings.watchlist.eyebrow":       "내 관심 종목",
    "rankings.watchlist.title":         "고정 종목",
    "rankings.watchlist.empty":         "이 시장에 고정된 종목이 없습니다. 아래 보드에서 행을 고정하세요.",
    "rankings.watchlist.signIn":        "기기 간 관심 종목 동기화를 위해 로그인하세요.",
    // Shared
    "ui.pin":          "고정",
    "ui.pinned":       "고정됨",
    "ui.open":         "열기",
    "ui.strategies":   "개 전략",
    "ui.regime":       "시장 국면",
    "ui.conviction":   "신뢰 등급",
    "ui.needsScoring": "스코어링 필요",
    "ui.explore":      "탐색",
    "ui.allCoverage":  "전체 커버리지",
    "ui.stock":        "주식",
    // Conviction
    "conviction.diamond":  "다이아몬드",
    "conviction.platinum": "플래티넘",
    "conviction.gold":     "골드",
    "conviction.silver":   "실버",
    "conviction.bronze":   "브론즈",
    "conviction.unranked": "미랭크",
    // Alerts
    "alerts.kicker":   "푸시 알림",
    "alerts.headline": "신뢰 등급 알림",
    "alerts.sub":      "종목이 신뢰 등급을 넘을 때 알림을 받으세요.",
    // Regime
    "regime.kicker":   "시장 포지션",
    "regime.headline": "시장 국면",
    "regime.sub":      "미국·한국 시장 국면 보드는 매일 밤 업데이트됩니다.",
  },
};
