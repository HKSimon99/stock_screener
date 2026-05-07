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
  | "ui.strategiesCount"
  | "ui.regimeWarning"
  | "ui.openApp"
  | "ui.loading"
  // ── Strategies page ───────────────────────────────────────────────────────
  | "strategies.headline"
  | "strategies.sub"
  | "strategies.canslimNote"
  | "strategies.unavailable"
  | "strategies.empty"
  // ── CANSLIM filter builder ────────────────────────────────────────────────
  | "canslim.advancedFilters"
  | "canslim.presets"
  | "canslim.scoreLabel"
  | "canslim.piotroskiLabel"
  | "canslim.minerviniLabel"
  | "canslim.weinsteinLabel"
  | "canslim.weinsteinDesc"
  | "canslim.rsLineLabel"
  | "canslim.rsLineDesc"
  | "canslim.reset"
  | "canslim.apply"
  | "canslim.clear"
  | "canslim.filterError"
  | "canslim.noResults"
  | "canslim.noBase"
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
  | "alerts.center"
  | "alerts.active"
  | "alerts.empty"
  | "alerts.refreshing"
  | "alerts.count.critical"
  | "alerts.count.warnings"
  | "alerts.count.total"
  | "alerts.group.critical"
  | "alerts.group.warnings"
  | "alerts.group.info"
  | "alerts.threshold"
  | "alerts.actual"
  | "alerts.relative.minutes"
  | "alerts.relative.hours"
  | "alerts.relative.days"
  // ── Methodology page ──────────────────────────────────────────────────────
  | "methodology.kicker"
  | "methodology.headline"
  | "methodology.intro"
  | "methodology.section.coverage.title"
  | "methodology.section.coverage.body"
  | "methodology.section.strategies.title"
  | "methodology.section.strategies.body"
  | "methodology.section.pit.title"
  | "methodology.section.pit.body"
  // ── Data Sources page ─────────────────────────────────────────────────────
  | "dataSources.kicker"
  | "dataSources.headline"
  | "dataSources.intro"
  | "dataSources.row.usListings.title"
  | "dataSources.row.usListings.body"
  | "dataSources.row.krListings.title"
  | "dataSources.row.krListings.body"
  | "dataSources.row.usFundamentals.title"
  | "dataSources.row.usFundamentals.body"
  | "dataSources.row.krFundamentals.title"
  | "dataSources.row.krFundamentals.body"
  | "dataSources.row.usPrices.title"
  | "dataSources.row.usPrices.body"
  | "dataSources.row.krPrices.title"
  | "dataSources.row.krPrices.body"
  // ── Freshness Policy page ─────────────────────────────────────────────────
  | "freshness.kicker"
  | "freshness.headline"
  | "freshness.intro"
  | "freshness.col.state"
  | "freshness.col.meaning"
  | "freshness.row.needsPrice.label"
  | "freshness.row.needsPrice.body"
  | "freshness.row.needsFundamentals.label"
  | "freshness.row.needsFundamentals.body"
  | "freshness.row.needsScoring.label"
  | "freshness.row.needsScoring.body"
  | "freshness.row.stale.label"
  | "freshness.row.stale.body"
  | "freshness.row.ranked.label"
  | "freshness.row.ranked.body"
  // ── Disclosures page ──────────────────────────────────────────────────────
  | "disclosures.kicker"
  | "disclosures.headline"
  | "disclosures.item.notAdvice"
  | "disclosures.item.dataDelay"
  | "disclosures.item.coverageMeaning"
  | "disclosures.item.krLicensing"
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
    "home.kicker":                     "US + Korea multi-strategy stock screener",
    "home.headline1":                  "Find what's working.",
    "home.headline2":                  "Back it with data.",
    "home.sub":                        "Search any US or Korean stock. Five proven strategies grade each name. We only rank the ones we have solid data for — everything else shows up clearly labeled.",
    "home.cta.app":                    "Open the app",
    "home.cta.methodology":            "How we rank",
    "home.stats.universe.label":       "Stocks covered",
    "home.stats.universe.value":       "6,500+",
    "home.stats.universe.sub":         "US + Korea",
    "home.stats.strategies.label":     "Strategies",
    "home.stats.strategies.value":     "5",
    "home.stats.strategies.sub":       "CANSLIM · Piotroski · Minervini · Weinstein · Dual Momentum",
    "home.stats.data.label":           "Updates",
    "home.stats.data.value":           "Nightly",
    "home.stats.data.sub":             "Korea live, US end-of-day",
    "home.features.kicker":            "What you get",
    "home.features.headline":          "Built around how you actually research stocks.",
    "home.features.search.title":      "Search every stock",
    "home.features.search.body":       "Find any covered US or Korean stock by ticker, name, or exchange. Open a chart even if it's not fully ranked yet.",
    "home.features.coverage.title":    "We tell you what we don't know",
    "home.features.coverage.body":     "Stocks missing data, a fresh score, or full coverage show up separately — clearly labeled. The ranked board only shows what we can actually back up.",
    "home.features.chart.title":       "Single-stock research desk",
    "home.features.chart.body":        "Jump from rankings to a full chart view: price structure, relative strength, patterns, and data freshness all in one place.",
    "home.features.regime.title":      "Market context, always visible",
    "home.features.regime.body":       "US and KR market status stays on screen so you're reading rankings against real market conditions, not just chasing scores.",
    "home.direction.kicker":           "How it's structured",
    "home.direction.headline1":        "Public site outside,",
    "home.direction.headline2":        "research desk inside.",
    "home.direction.body":             "This site covers methodology, data sources, freshness, and disclosures. The app is where rankings, search, and stock workspaces live.",
    "home.next.kicker":                "Ready to start",
    "home.next.headline":              "See what's ranking right now",
    "home.next.body":                  "Browse ranked stocks, filter by strategy or conviction, or search for any ticker. Data updates every night.",
    "home.next.cta":                   "Open search",
    "home.footer.disclaimer":          "Not investment advice.",
    "home.leaderboard.kicker":         "Live rankings",
    "home.leaderboard.ranked":         "ranked",
    "home.leaderboard.viewAll":        "See all rankings",
    "home.how.title":                  "How it works",
    "home.how.step1.title":            "Collect",
    "home.how.step1.body":             "Every trading day we pull price, volume, fundamentals, and filings for 6,500+ US and Korean stocks.",
    "home.how.step2.title":            "Score",
    "home.how.step2.body":             "Five independent strategies — CANSLIM, Piotroski, Minervini, Weinstein, and Dual Momentum — grade each stock 0–100.",
    "home.how.step3.title":            "Rank",
    "home.how.step3.body":             "Stocks where multiple strategies agree rise to the top. One strategy liking a name isn't enough to rank it.",
    // Search
    "search.kicker":           "Stock search",
    "search.headline":         "Find any stock, then decide what to do with it.",
    "search.sub":              "Search by ticker, company name, or exchange. Each result shows exactly where the stock stands — missing data, waiting on a score, stale, or fully ranked.",
    "search.placeholder":      "AAPL, Samsung, semiconductors, NYSE…",
    "search.filter.allMarkets":"All markets",
    "search.filter.allTypes":  "All types",
    "search.pinned":           "Pinned",
    "search.recent":           "Recent",
    "search.pinEmpty":         "Pin a stock from any result to keep it here.",
    "search.recentEmpty":      "Stocks you've looked up will appear here.",
    "search.results":          "Results",
    "search.fetching":         "Searching…",
    "search.matches":          "results",
    "search.empty":            "No stocks matched your search.",
    "search.noResults":        "No stocks matched your search.",
    "search.startPrompt":      "Search by ticker, name, or exchange.",
    // Rankings
    "rankings.kicker":                  "Rankings",
    "rankings.headline":                "Signal Board",
    "rankings.sub":                     "Ranked stocks are backed by real scores. Stocks waiting on data or a score show up below the board — labeled honestly, never inflated.",
    "rankings.stat.loaded":             "Loaded",
    "rankings.stat.requested":          "requested",
    "rankings.stat.topScore":           "Top score",
    "rankings.stat.average":            "Average",
    "rankings.stat.freshness":          "Data age",
    "rankings.stat.refreshing":         "Updating…",
    "rankings.stat.activeFilters":      "filters on",
    "rankings.controls.kicker":         "Market",
    "rankings.controls.usMarket":       "US",
    "rankings.controls.krMarket":       "Korea",
    "rankings.controls.resultCount":    "Show",
    "rankings.controls.top":            "Top",
    "rankings.lens.kicker":             "Active filters",
    "rankings.presets.kicker":          "Strategy presets",
    "rankings.presets.headline":        "Pick a strategy lens, or set your own filters.",
    "rankings.presets.reset":           "Clear filters",
    "rankings.presets.advanced":        "More filters",
    "rankings.filters.conviction":      "Conviction",
    "rankings.filters.coverage":        "Coverage",
    "rankings.filters.finalScore":      "Score",
    "rankings.filters.strategyCount":   "Strategies passing",
    "rankings.filters.technical":       "Technical",
    "rankings.filters.rsNewHigh":       "RS New High",
    "rankings.filters.anyConviction":   "Any",
    "rankings.filters.anyCoverage":     "Any",
    "rankings.filters.noMinimum":       "No minimum",
    "rankings.filters.noPassing":       "No minimum",
    "rankings.filters.any":             "Any",
    "rankings.filters.required":        "Required",
    "rankings.filters.exclude":         "Exclude",
    "rankings.regime.warning":          "ranked stocks have a market warning.",
    "rankings.leaderboard.eyebrow":     "Ranked",
    "rankings.leaderboard.subtitle":    "Every stock here has a stored score. Use filters to narrow down the list without changing the underlying order.",
    "rankings.leaderboard.showing":     "Showing",
    "rankings.leaderboard.loadMore":    "Load more",
    "rankings.leaderboard.refreshing":  "Updating…",
    "rankings.leaderboard.error":       "Rankings are temporarily unavailable.",
    "rankings.leaderboard.empty":       "Nothing ranked matches your filters. Try clearing some and looking again.",
    "rankings.partial.eyebrow":         "Waiting on a score",
    "rankings.partial.title":           "Almost there",
    "rankings.partial.subtitle":        "These stocks have enough data to be worth watching, but haven't been scored yet. They'll appear in the ranked board once scoring runs.",
    "rankings.partial.loadMore":        "Load more",
    "rankings.partial.error":           "This section is unavailable right now. Ranked results are not affected.",
    "rankings.partial.empty":           "No stocks waiting on a score for this market.",
    "rankings.explore.eyebrow":         "On the radar",
    "rankings.explore.title":           "Not ranked yet",
    "rankings.explore.subtitle":        "Known stocks from our universe that don't have enough data to rank. They won't claim a score they don't have.",
    "rankings.explore.loadMore":        "Load more",
    "rankings.explore.error":           "This section is unavailable right now. Ranked results are not affected.",
    "rankings.explore.empty":           "Nothing else to show for this market.",
    "rankings.watchlist.eyebrow":       "Watchlist",
    "rankings.watchlist.title":         "Pinned stocks",
    "rankings.watchlist.empty":         "No pinned stocks for this market yet. Pin any row from the board below.",
    "rankings.watchlist.signIn":        "Sign in to keep your watchlist across devices.",
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
    "alerts.kicker":            "Push alerts",
    "alerts.headline":          "Conviction alerts",
    "alerts.sub":               "Get notified when an instrument crosses a conviction level.",
    "alerts.center":            "Alert Centre",
    "alerts.active":            "Active Alerts",
    "alerts.empty":             "No alerts in the past 30 days.",
    "alerts.refreshing":        "refreshing…",
    "alerts.count.critical":    "critical",
    "alerts.count.warnings":    "warnings",
    "alerts.count.total":       "total",
    "alerts.group.critical":    "Critical",
    "alerts.group.warnings":    "Warnings",
    "alerts.group.info":        "Info",
    "alerts.threshold":         "Threshold",
    "alerts.actual":            "Actual",
    "alerts.relative.minutes":  "m ago",
    "alerts.relative.hours":    "h ago",
    "alerts.relative.days":     "d ago",
    // Methodology
    "methodology.kicker":                    "How we rank",
    "methodology.headline":                  "Rankings should be explainable before they're persuasive.",
    "methodology.intro":                     "We rebuilt the product around broader universe coverage, clearer freshness labels, and honest ranking eligibility — so you always know what the board can and can't claim.",
    "methodology.section.coverage.title":    "Coverage before confidence",
    "methodology.section.coverage.body":     "We separate stocks that still need price data, fundamentals, scoring, or freshness repair from names that are genuinely ranked. If it's not ready, it doesn't pretend to be.",
    "methodology.section.strategies.title":  "Named strategies are overlays",
    "methodology.section.strategies.body":   "CANSLIM, Piotroski, Minervini, Weinstein, and Dual Momentum explain each stock's profile and posture well — but none of them covers the full universe on their own.",
    "methodology.section.pit.title":         "Point-in-time data matters",
    "methodology.section.pit.body":          "US fundamentals come from SEC EDGAR/XBRL, Korea from OpenDART. Rankings are only as trustworthy as their filing availability, price history, and freshness labels.",
    // Data Sources
    "dataSources.kicker":                        "Where the data comes from",
    "dataSources.headline":                      "Every number is traceable to a source.",
    "dataSources.intro":                         "Every coverage state in the app should eventually trace to one or more upstream market, price, or filing sources. Here's what we're running at launch.",
    "dataSources.row.usListings.title":          "US listings",
    "dataSources.row.usListings.body":           "Nasdaq Trader symbol directories for major listed US securities.",
    "dataSources.row.krListings.title":          "KR listings",
    "dataSources.row.krListings.body":           "KRX universe via FinanceDataReader-backed KRX listings.",
    "dataSources.row.usFundamentals.title":      "US fundamentals",
    "dataSources.row.usFundamentals.body":       "SEC EDGAR / XBRL ingestion through edgartools.",
    "dataSources.row.krFundamentals.title":      "KR fundamentals",
    "dataSources.row.krFundamentals.body":       "OpenDART filings and corp-code mapping.",
    "dataSources.row.usPrices.title":            "US prices",
    "dataSources.row.usPrices.body":             "Yahoo Finance historical prices for delayed/snapshot research views.",
    "dataSources.row.krPrices.title":            "KR prices",
    "dataSources.row.krPrices.body":             "KIS-backed historical pricing pipeline. Live-stream delivery is gated by licensing.",
    // Freshness Policy
    "freshness.kicker":                          "Data freshness",
    "freshness.headline":                        "Labels remove ambiguity. They don't decorate it.",
    "freshness.intro":                           "The app shows when each price, fundamental, and ranked layer was last updated. Coverage states explain what we can safely claim for each stock.",
    "freshness.col.state":                       "State",
    "freshness.col.meaning":                     "Meaning",
    "freshness.row.needsPrice.label":            "Needs Price",
    "freshness.row.needsPrice.body":             "The stock exists in our universe but doesn't have usable price history yet.",
    "freshness.row.needsFundamentals.label":     "Needs Fundamentals",
    "freshness.row.needsFundamentals.body":      "We have price history, but filing coverage isn't available for this stock yet.",
    "freshness.row.needsScoring.label":          "Needs Scoring",
    "freshness.row.needsScoring.body":           "All the raw data exists, but we haven't generated a stored score yet.",
    "freshness.row.stale.label":                 "Stale",
    "freshness.row.stale.body":                  "A price or fundamentals layer is older than our freshness policy expects.",
    "freshness.row.ranked.label":                "Ranked",
    "freshness.row.ranked.body":                 "A stored score snapshot exists and this stock can appear on the leaderboard.",
    // Disclosures
    "disclosures.kicker":                  "Legal",
    "disclosures.headline":                "Trust is built by stating limits clearly.",
    "disclosures.item.notAdvice":          "This is a research and charting tool, not individualised investment advice.",
    "disclosures.item.dataDelay":          "Displayed market data may be live, delayed, or end-of-day depending on market, entitlement, and source availability.",
    "disclosures.item.coverageMeaning":    "Coverage states explain what data is available. They are not endorsements of quality, safety, or expected return.",
    "disclosures.item.krLicensing":        "Korea live redistribution for public web and mobile remains subject to market-data licensing and exchange policy.",
    // Shared UI additions
    "ui.strategiesCount":  "strategies",
    "ui.regimeWarning":    "regime",
    "ui.openApp":          "Open App",
    "ui.loading":          "Loading…",
    // Strategies page
    "strategies.headline":    "Strategy Rankings",
    "strategies.sub":         "Each strategy scored and ranked on its own — click through to see how.",
    "strategies.canslimNote": "CANSLIM covers US growth stocks only.",
    "strategies.unavailable": "Rankings temporarily unavailable.",
    "strategies.empty":       "No rankings available yet.",
    // CANSLIM filter builder
    "canslim.advancedFilters": "Advanced Filters",
    "canslim.presets":         "Presets",
    "canslim.scoreLabel":      "CANSLIM Score",
    "canslim.piotroskiLabel":  "Piotroski F-Score",
    "canslim.minerviniLabel":  "Minervini Criteria",
    "canslim.weinsteinLabel":  "Weinstein Stage 2",
    "canslim.weinsteinDesc":   "Only show stocks currently in Stage 2 (advancing)",
    "canslim.rsLineLabel":     "RS Line New High",
    "canslim.rsLineDesc":      "Relative strength line at a 52-week high",
    "canslim.reset":           "Reset",
    "canslim.apply":           "Apply Filters",
    "canslim.clear":           "Clear",
    "canslim.filterError":     "Filter query failed — check your session or try again.",
    "canslim.noResults":       "No results match these filters. Try loosening the criteria.",
    "canslim.noBase":          "No CANSLIM rankings available for US yet.",
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
    "home.kicker":                     "미국·한국 멀티 전략 주식 스크리너",
    "home.headline1":                  "잘 가는 종목을 찾고,",
    "home.headline2":                  "데이터로 확인하세요.",
    "home.sub":                        "미국·한국 주식 어느 것이든 검색하세요. 다섯 가지 검증된 전략이 각 종목을 평가하고, 데이터가 충분한 종목만 순위에 올립니다. 나머지는 이유를 명확히 표시해 따로 보여줍니다.",
    "home.cta.app":                    "앱 열기",
    "home.cta.methodology":            "순위 산출 방식 보기",
    "home.stats.universe.label":       "커버 종목",
    "home.stats.universe.value":       "6,500+",
    "home.stats.universe.sub":         "미국·한국",
    "home.stats.strategies.label":     "전략",
    "home.stats.strategies.value":     "5",
    "home.stats.strategies.sub":       "CANSLIM · 피오트로스키 · 미너비니 · 와인스타인 · 듀얼 모멘텀",
    "home.stats.data.label":           "업데이트",
    "home.stats.data.value":           "매일 밤",
    "home.stats.data.sub":             "한국 실시간·미국 장 마감 기준",
    "home.features.kicker":            "주요 기능",
    "home.features.headline":          "실제로 종목을 분석하는 방식으로 만들었어요.",
    "home.features.search.title":      "전 종목 검색",
    "home.features.search.body":       "미국·한국 커버리지 내 모든 종목을 검색할 수 있어요. 순위에 없는 종목도 차트에서 바로 열어볼 수 있습니다.",
    "home.features.coverage.title":    "모르는 건 솔직하게 표시해요",
    "home.features.coverage.body":     "데이터·점수·최신성이 부족한 종목은 순위 보드와 따로 표시됩니다. 순위에 오른 종목은 실제 데이터로 뒷받침된 것들만이에요.",
    "home.features.chart.title":       "개별 종목 리서치",
    "home.features.chart.body":        "순위에서 클릭하면 가격 구조, 상대 강도, 패턴, 데이터 현황을 한 화면에서 볼 수 있습니다.",
    "home.features.regime.title":      "시장 흐름 항상 확인",
    "home.features.regime.body":       "미국·한국 시장 상태를 화면에 유지해서, 점수만 따라가는 게 아니라 실제 시장 흐름 위에서 순위를 읽을 수 있게 해드려요.",
    "home.direction.kicker":           "구조 안내",
    "home.direction.headline1":        "공개 사이트는 외부에,",
    "home.direction.headline2":        "리서치 앱은 내부에.",
    "home.direction.body":             "이 사이트에서는 방법론·데이터 출처·최신성·고지사항을 설명합니다. 순위, 검색, 종목 분석은 앱 안에 있어요.",
    "home.next.kicker":                "지금 바로",
    "home.next.headline":              "지금 순위를 확인해보세요",
    "home.next.body":                  "순위 보드를 둘러보거나, 전략·신뢰 등급으로 필터링하거나, 아무 종목이나 검색해보세요. 매일 밤 업데이트됩니다.",
    "home.next.cta":                   "검색하기",
    "home.footer.disclaimer":          "투자 조언이 아닙니다.",
    "home.leaderboard.kicker":         "실시간 순위",
    "home.leaderboard.ranked":         "분석 완료",
    "home.leaderboard.viewAll":        "전체 순위 보기",
    "home.how.title":                  "어떻게 작동하나요",
    "home.how.step1.title":            "데이터 수집",
    "home.how.step1.body":             "매 거래일마다 미국·한국 6,500개 이상 종목의 주가, 거래량, 재무 지표, 공시를 가져옵니다.",
    "home.how.step2.title":            "점수 산출",
    "home.how.step2.body":             "CANSLIM, 피오트로스키, 미너비니, 와인스타인, 듀얼 모멘텀 — 다섯 가지 전략이 각 종목을 0~100점으로 평가합니다.",
    "home.how.step3.title":            "순위 결정",
    "home.how.step3.body":             "여러 전략이 동시에 동의하는 종목이 위로 올라옵니다. 전략 하나만 좋아하는 종목은 순위에 오르지 않아요.",
    // Search
    "search.kicker":           "종목 검색",
    "search.headline":         "종목을 찾고, 상태를 바로 확인하세요.",
    "search.sub":              "티커, 회사명, 거래소로 검색할 수 있어요. 결과에서 각 종목이 어떤 상태인지 — 데이터 부족, 점수 대기, 오래된 데이터, 순위 포함 — 바로 확인됩니다.",
    "search.placeholder":      "AAPL, 삼성전자, 반도체, NYSE…",
    "search.filter.allMarkets":"전체 시장",
    "search.filter.allTypes":  "전체 유형",
    "search.pinned":           "고정",
    "search.recent":           "최근",
    "search.pinEmpty":         "결과에서 종목을 고정하면 여기에 표시돼요.",
    "search.recentEmpty":      "검색한 종목이 여기에 기록됩니다.",
    "search.results":          "결과",
    "search.fetching":         "검색 중…",
    "search.matches":          "개",
    "search.empty":            "검색 결과가 없어요.",
    "search.noResults":        "검색 결과가 없어요.",
    "search.startPrompt":      "티커, 회사명, 또는 거래소로 검색해보세요.",
    // Rankings
    "rankings.kicker":                  "순위",
    "rankings.headline":                "시그널 보드",
    "rankings.sub":                     "순위에 오른 종목은 모두 실제 점수로 뒷받침돼요. 데이터가 부족한 종목은 보드 아래에 따로 표시됩니다 — 부풀리지 않고 솔직하게.",
    "rankings.stat.loaded":             "불러옴",
    "rankings.stat.requested":          "요청",
    "rankings.stat.topScore":           "최고 점수",
    "rankings.stat.average":            "평균",
    "rankings.stat.freshness":          "데이터 나이",
    "rankings.stat.refreshing":         "업데이트 중…",
    "rankings.stat.activeFilters":      "개 필터 적용 중",
    "rankings.controls.kicker":         "시장",
    "rankings.controls.usMarket":       "미국",
    "rankings.controls.krMarket":       "한국",
    "rankings.controls.resultCount":    "표시",
    "rankings.controls.top":            "상위",
    "rankings.lens.kicker":             "적용된 필터",
    "rankings.presets.kicker":          "전략 프리셋",
    "rankings.presets.headline":        "전략 렌즈를 고르거나 직접 필터를 설정하세요.",
    "rankings.presets.reset":           "필터 초기화",
    "rankings.presets.advanced":        "필터 더 보기",
    "rankings.filters.conviction":      "신뢰 등급",
    "rankings.filters.coverage":        "데이터 커버",
    "rankings.filters.finalScore":      "점수",
    "rankings.filters.strategyCount":   "통과 전략 수",
    "rankings.filters.technical":       "기술적",
    "rankings.filters.rsNewHigh":       "RS 신고가",
    "rankings.filters.anyConviction":   "전체",
    "rankings.filters.anyCoverage":     "전체",
    "rankings.filters.noMinimum":       "최소 없음",
    "rankings.filters.noPassing":       "최소 없음",
    "rankings.filters.any":             "전체",
    "rankings.filters.required":        "필수",
    "rankings.filters.exclude":         "제외",
    "rankings.regime.warning":          "개 종목에 시장 경고가 있어요.",
    "rankings.leaderboard.eyebrow":     "순위",
    "rankings.leaderboard.subtitle":    "여기 나오는 종목은 모두 실제 점수가 있어요. 필터로 좁혀도 기본 순서는 바뀌지 않습니다.",
    "rankings.leaderboard.showing":     "표시 중",
    "rankings.leaderboard.loadMore":    "더 보기",
    "rankings.leaderboard.refreshing":  "업데이트 중…",
    "rankings.leaderboard.error":       "순위를 잠시 불러올 수 없습니다.",
    "rankings.leaderboard.empty":       "설정한 필터에 맞는 종목이 없어요. 필터를 조금 풀어보세요.",
    "rankings.partial.eyebrow":         "점수 대기 중",
    "rankings.partial.title":           "거의 다 왔어요",
    "rankings.partial.subtitle":        "데이터는 충분하지만 아직 점수가 산출되지 않은 종목들이에요. 다음 업데이트 때 순위에 포함될 예정입니다.",
    "rankings.partial.loadMore":        "더 보기",
    "rankings.partial.error":           "이 섹션을 잠시 불러올 수 없습니다. 순위 결과에는 영향이 없어요.",
    "rankings.partial.empty":           "이 시장에서 점수 대기 중인 종목이 없어요.",
    "rankings.explore.eyebrow":         "관심 목록",
    "rankings.explore.title":           "아직 순위에 없는 종목",
    "rankings.explore.subtitle":        "커버리지에는 있지만 데이터가 충분하지 않아 순위에 오르지 못한 종목들이에요. 없는 점수를 주장하지 않습니다.",
    "rankings.explore.loadMore":        "더 보기",
    "rankings.explore.error":           "이 섹션을 잠시 불러올 수 없습니다. 순위 결과에는 영향이 없어요.",
    "rankings.explore.empty":           "이 시장에 추가로 표시할 종목이 없어요.",
    "rankings.watchlist.eyebrow":       "관심 종목",
    "rankings.watchlist.title":         "고정한 종목",
    "rankings.watchlist.empty":         "이 시장에 고정한 종목이 없어요. 아래 보드에서 종목을 고정해보세요.",
    "rankings.watchlist.signIn":        "기기 간 동기화를 원하시면 로그인하세요.",
    // Shared
    "ui.pin":          "고정",
    "ui.pinned":       "고정됨",
    "ui.open":         "열기",
    "ui.strategies":   "개 전략",
    "ui.regime":       "시장 상태",
    "ui.conviction":   "신뢰 등급",
    "ui.needsScoring": "점수 필요",
    "ui.explore":      "탐색",
    "ui.allCoverage":  "전체 커버",
    "ui.stock":        "주식",
    // Conviction
    "conviction.diamond":  "다이아몬드",
    "conviction.platinum": "플래티넘",
    "conviction.gold":     "골드",
    "conviction.silver":   "실버",
    "conviction.bronze":   "브론즈",
    "conviction.unranked": "미분류",
    // Alerts
    "alerts.kicker":            "푸시 알림",
    "alerts.headline":          "신뢰 등급 알림",
    "alerts.sub":               "종목이 신뢰 등급을 넘을 때 알림을 받으세요.",
    "alerts.center":            "알림 센터",
    "alerts.active":            "활성 알림",
    "alerts.empty":             "최근 30일 동안 알림이 없습니다.",
    "alerts.refreshing":        "새로고침 중…",
    "alerts.count.critical":    "긴급",
    "alerts.count.warnings":    "경고",
    "alerts.count.total":       "전체",
    "alerts.group.critical":    "긴급",
    "alerts.group.warnings":    "경고",
    "alerts.group.info":        "정보",
    "alerts.threshold":         "기준값",
    "alerts.actual":            "실제값",
    "alerts.relative.minutes":  "분 전",
    "alerts.relative.hours":    "시간 전",
    "alerts.relative.days":     "일 전",
    // Methodology
    "methodology.kicker":                    "순위 산출 방식",
    "methodology.headline":                  "설득하기 전에 먼저 설명할 수 있어야 합니다.",
    "methodology.intro":                     "더 넓은 종목 커버리지, 명확한 데이터 현황 표시, 정직한 순위 기준을 중심으로 제품을 다시 만들었습니다. 보드가 무엇을 알고 무엇을 모르는지 항상 확인할 수 있습니다.",
    "methodology.section.coverage.title":    "신뢰보다 커버리지가 먼저",
    "methodology.section.coverage.body":     "가격 데이터, 재무 정보, 점수 산출, 데이터 최신성이 부족한 종목은 완전히 순위에 오른 종목과 구분합니다. 준비되지 않은 종목은 준비된 척하지 않습니다.",
    "methodology.section.strategies.title":  "전략은 보조 도구입니다",
    "methodology.section.strategies.body":   "CANSLIM, 피오트로스키, 미너비니, 와인스타인, 듀얼 모멘텀은 각 종목의 특성과 포지션을 잘 설명해줍니다. 하지만 어떤 단일 전략도 전체 시장을 커버하지는 않습니다.",
    "methodology.section.pit.title":         "시점 데이터가 중요합니다",
    "methodology.section.pit.body":          "미국 재무 데이터는 SEC EDGAR/XBRL에서, 한국은 OpenDART에서 가져옵니다. 순위는 공시 가용성, 가격 이력, 데이터 현황만큼만 신뢰할 수 있습니다.",
    // Data Sources
    "dataSources.kicker":                        "데이터 출처",
    "dataSources.headline":                      "모든 수치는 출처를 추적할 수 있습니다.",
    "dataSources.intro":                         "앱의 모든 커버리지 상태는 하나 이상의 상위 시장·가격·공시 출처로 추적 가능해야 합니다. 현재 운영 중인 출처를 정리했습니다.",
    "dataSources.row.usListings.title":          "미국 상장 종목",
    "dataSources.row.usListings.body":           "Nasdaq Trader 심볼 디렉토리 기반 미국 주요 상장 종목.",
    "dataSources.row.krListings.title":          "한국 상장 종목",
    "dataSources.row.krListings.body":           "FinanceDataReader 기반 KRX 상장 종목.",
    "dataSources.row.usFundamentals.title":      "미국 재무 데이터",
    "dataSources.row.usFundamentals.body":       "edgartools를 통한 SEC EDGAR / XBRL 수집.",
    "dataSources.row.krFundamentals.title":      "한국 재무 데이터",
    "dataSources.row.krFundamentals.body":       "OpenDART 공시 및 기업 코드 매핑.",
    "dataSources.row.usPrices.title":            "미국 주가",
    "dataSources.row.usPrices.body":             "지연/스냅샷 리서치 뷰용 Yahoo Finance 과거 주가.",
    "dataSources.row.krPrices.title":            "한국 주가",
    "dataSources.row.krPrices.body":             "KIS 기반 과거 주가 파이프라인. 실시간 제공은 라이선스 조건에 따라 제한됩니다.",
    // Freshness Policy
    "freshness.kicker":                          "데이터 현황",
    "freshness.headline":                        "레이블은 모호함을 없애야 합니다. 꾸미는 용도가 아닙니다.",
    "freshness.intro":                           "앱은 가격·재무·순위 각 레이어가 마지막으로 업데이트된 날짜를 보여줍니다. 커버리지 상태는 각 종목에 대해 무엇을 안전하게 말할 수 있는지를 설명합니다.",
    "freshness.col.state":                       "상태",
    "freshness.col.meaning":                     "의미",
    "freshness.row.needsPrice.label":            "가격 없음",
    "freshness.row.needsPrice.body":             "커버리지에 포함된 종목이지만 아직 사용 가능한 가격 이력이 없습니다.",
    "freshness.row.needsFundamentals.label":     "재무 없음",
    "freshness.row.needsFundamentals.body":      "가격 이력은 있지만 이 종목의 공시 커버리지가 아직 없습니다.",
    "freshness.row.needsScoring.label":          "점수 필요",
    "freshness.row.needsScoring.body":           "원시 데이터는 모두 있지만 아직 점수가 산출되지 않았습니다.",
    "freshness.row.stale.label":                 "오래된 데이터",
    "freshness.row.stale.body":                  "가격 또는 재무 데이터 레이어가 데이터 현황 정책이 기대하는 것보다 오래되었습니다.",
    "freshness.row.ranked.label":                "순위 포함",
    "freshness.row.ranked.body":                 "저장된 점수 스냅샷이 있으며 리더보드에 표시될 수 있습니다.",
    // Disclosures
    "disclosures.kicker":                  "고지사항",
    "disclosures.headline":                "한계를 명확히 밝혀야 신뢰가 쌓입니다.",
    "disclosures.item.notAdvice":          "이 서비스는 리서치 및 차트 도구이며, 개별 투자 조언이 아닙니다.",
    "disclosures.item.dataDelay":          "표시되는 시장 데이터는 시장·권한·출처 가용성에 따라 실시간, 지연, 또는 장 마감 기준일 수 있습니다.",
    "disclosures.item.coverageMeaning":    "커버리지 상태는 어떤 데이터가 있는지를 설명합니다. 품질, 안전성, 기대 수익에 대한 보증이 아닙니다.",
    "disclosures.item.krLicensing":        "공개 웹 및 모바일에서의 한국 실시간 데이터 제공은 시장 데이터 라이선스 및 거래소 정책의 적용을 받습니다.",
    // Shared UI additions
    "ui.strategiesCount":  "개 전략",
    "ui.regimeWarning":    "시장 경고",
    "ui.openApp":          "앱 열기",
    "ui.loading":          "로딩 중…",
    // Strategies page
    "strategies.headline":    "전략 랭킹",
    "strategies.sub":         "각 전략을 독립적으로 채점하고 순위를 매겼습니다. 전략별 기준을 확인해보세요.",
    "strategies.canslimNote": "CANSLIM은 미국 성장주에만 적용됩니다.",
    "strategies.unavailable": "일시적으로 순위를 불러올 수 없습니다.",
    "strategies.empty":       "아직 표시할 순위가 없습니다.",
    // CANSLIM filter builder
    "canslim.advancedFilters": "고급 필터",
    "canslim.presets":         "프리셋",
    "canslim.scoreLabel":      "CANSLIM 점수",
    "canslim.piotroskiLabel":  "피오트로스키 F-점수",
    "canslim.minerviniLabel":  "미너비니 기준",
    "canslim.weinsteinLabel":  "와인스타인 2단계",
    "canslim.weinsteinDesc":   "현재 2단계(상승 추세)에 있는 종목만 표시",
    "canslim.rsLineLabel":     "RS 라인 신고가",
    "canslim.rsLineDesc":      "RS 라인이 52주 신고가를 기록한 종목",
    "canslim.reset":           "초기화",
    "canslim.apply":           "필터 적용",
    "canslim.clear":           "초기화",
    "canslim.filterError":     "필터 조회에 실패했습니다. 다시 시도해주세요.",
    "canslim.noResults":       "조건에 맞는 종목이 없습니다. 기준을 낮춰보세요.",
    "canslim.noBase":          "아직 CANSLIM 미국 순위가 없습니다.",
    // Regime
    "regime.kicker":   "시장 상태",
    "regime.headline": "시장 국면",
    "regime.sub":      "미국·한국 시장 국면은 매일 밤 업데이트됩니다.",
  },
};
