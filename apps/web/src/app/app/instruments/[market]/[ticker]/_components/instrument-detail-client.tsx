"use client";

import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { Pin, RefreshCw } from "lucide-react";
import {
  APIError,
  addToWatchlist,
  fetchInstrument,
  fetchInstrumentChart,
  removeFromWatchlist,
  type InstrumentChart,
  type InstrumentDetail,
} from "@/lib/api";
import { useUIStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { InstrumentChart as InstrumentChartComponent, type ChartInterval, type ChartRangeDays } from "@/components/instrument-chart";

interface InstrumentDetailClientProps {
  ticker: string;
  market: "US" | "KR";
  initialData: InstrumentDetail | null;
  initialChartData: InstrumentChart | null;
}

function scoreChip(label: string, score?: number, max = 100) {
  const hasScore = typeof score === "number" && Number.isFinite(score);
  const safeScore = hasScore ? score : 0;
  const pct = hasScore ? Math.min(100, Math.max(0, (safeScore / max) * 100)) : 0;
  return (
    <div className="surface-panel-soft rounded-[1.2rem] px-4 py-3">
      <div className="text-[0.65rem] uppercase tracking-widest text-faint">{label}</div>
      <div className="mt-1 font-mono text-lg text-white">{hasScore ? safeScore.toFixed(1) : "—"}</div>
      <div className="relative mt-2 h-1 w-full overflow-hidden rounded-full bg-white/8">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-[oklch(0.78_0.11_84_/_0.6)]"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function convictionBadge(level: string) {
  const colorMap: Record<string, string> = {
    DIAMOND: "border-cyan-400/40 bg-cyan-400/10 text-cyan-300",
    PLATINUM: "border-violet-400/40 bg-violet-400/10 text-violet-300",
    GOLD: "border-amber-400/40 bg-amber-400/10 text-amber-300",
    SILVER: "border-slate-400/40 bg-slate-400/10 text-slate-300",
    BRONZE: "border-orange-400/40 bg-orange-400/10 text-orange-300",
    UNRANKED: "border-slate-600/40 bg-slate-600/10 text-slate-400",
  };
  const color = colorMap[level] || "border-white/10 text-faint";
  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-3 py-1 text-[0.68rem] uppercase tracking-widest",
        color
      )}
    >
      {level}
    </span>
  );
}

function missingLabel(market: "US" | "KR") {
  return market === "KR" ? "데이터 없음" : "Not available";
}

function formatDate(value: string | undefined, market: "US" | "KR") {
  if (!value) return missingLabel(market);
  try {
    return new Intl.DateTimeFormat(market === "KR" ? "ko-KR" : "en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(new Date(`${value}T00:00:00`));
  } catch {
    return value;
  }
}

function formatPrice(value: number | undefined, market: "US" | "KR") {
  if (typeof value !== "number" || !Number.isFinite(value)) return missingLabel(market);
  return new Intl.NumberFormat(market === "KR" ? "ko-KR" : "en-US", {
    style: "currency",
    currency: market === "KR" ? "KRW" : "USD",
    maximumFractionDigits: market === "KR" ? 0 : 2,
  }).format(value);
}

function compactMoney(value: number | undefined, market: "US" | "KR") {
  if (typeof value !== "number" || !Number.isFinite(value)) return missingLabel(market);
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  if (market === "KR") {
    if (abs >= 1_000_000_000_000) return `${sign}₩${(abs / 1_000_000_000_000).toFixed(1)}조`;
    if (abs >= 100_000_000) return `${sign}₩${(abs / 100_000_000).toFixed(1)}억`;
    if (abs >= 10_000) return `${sign}₩${(abs / 10_000).toFixed(1)}만`;
    return `${sign}₩${abs.toLocaleString("ko-KR")}`;
  }
  if (abs >= 1_000_000_000_000) return `${sign}$${(abs / 1_000_000_000_000).toFixed(1)}T`;
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}K`;
  return `${sign}$${abs.toLocaleString("en-US")}`;
}

function compactShares(value: number | undefined, market: "US" | "KR") {
  if (typeof value !== "number" || !Number.isFinite(value)) return missingLabel(market);
  const abs = Math.abs(value);
  if (market === "KR") {
    if (abs >= 100_000_000) return `${(abs / 100_000_000).toFixed(1)}억주`;
    if (abs >= 10_000) return `${(abs / 10_000).toFixed(1)}만주`;
    return `${abs.toLocaleString("ko-KR")}주`;
  }
  if (abs >= 1_000_000_000) return `${(abs / 1_000_000_000).toFixed(1)}B sh`;
  if (abs >= 1_000_000) return `${(abs / 1_000_000).toFixed(1)}M sh`;
  if (abs >= 1_000) return `${(abs / 1_000).toFixed(1)}K sh`;
  return `${abs.toLocaleString("en-US")} sh`;
}

function compactCount(value: number | undefined, market: "US" | "KR") {
  if (typeof value !== "number" || !Number.isFinite(value)) return missingLabel(market);
  return new Intl.NumberFormat(market === "KR" ? "ko-KR" : "en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatPercent(value: number | undefined, market: "US" | "KR", mode: "ratio" | "points" = "ratio") {
  if (typeof value !== "number" || !Number.isFinite(value)) return missingLabel(market);
  const percent = mode === "ratio" ? value * 100 : value;
  return `${percent > 0 ? "+" : ""}${percent.toFixed(1)}%`;
}

function formatRatio(value: number | undefined, market: "US" | "KR") {
  if (typeof value !== "number" || !Number.isFinite(value)) return missingLabel(market);
  return value.toFixed(2);
}

function plainValue(value: string | number | undefined | null, market: "US" | "KR") {
  if (value === undefined || value === null || value === "") return missingLabel(market);
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString(market === "KR" ? "ko-KR" : "en-US") : missingLabel(market);
  return value;
}

function MetricCard({
  label,
  value,
  note,
  tone,
  market,
}: {
  label: string;
  value: string;
  note?: string;
  tone?: "up" | "down" | "neutral";
  market: "US" | "KR";
}) {
  return (
    <div className="surface-panel-soft rounded-[1.25rem] border border-white/8 px-4 py-4">
      <div className="text-[0.65rem] uppercase tracking-[0.18em] text-faint">{label}</div>
      <div
        className={cn(
          "mt-2 font-mono text-xl text-white",
          tone === "up" && market === "US" && "text-[oklch(0.82_0.12_145)]",
          tone === "up" && market === "KR" && "text-[oklch(0.7_0.15_25)]",
          tone === "down" && market === "US" && "text-[oklch(0.7_0.15_25)]",
          tone === "down" && market === "KR" && "text-[oklch(0.7_0.12_250)]"
        )}
      >
        {value}
      </div>
      {note && <div className="mt-1 text-xs text-faint">{note}</div>}
    </div>
  );
}

function MetricSection({
  title,
  subtitle,
  children,
  defaultOpen = true,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details className="group rounded-[1.25rem] border border-white/8 bg-white/[0.03] px-4 py-3" open={defaultOpen}>
      <summary className="cursor-pointer list-none">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-faint">{title}</div>
            {subtitle && <div className="mt-1 text-xs text-faint">{subtitle}</div>}
          </div>
          <span className="text-xs uppercase tracking-[0.16em] text-faint group-open:hidden">Open</span>
          <span className="hidden text-xs uppercase tracking-[0.16em] text-faint group-open:inline">Close</span>
        </div>
      </summary>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{children}</div>
    </details>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[0.95rem] border border-white/8 bg-black/10 px-3 py-3">
      <div className="text-[0.65rem] uppercase tracking-[0.15em] text-faint">{label}</div>
      <div className="mt-1 font-mono text-sm text-white">{value}</div>
    </div>
  );
}

export function InstrumentDetailClient({
  ticker,
  market,
  initialData,
  initialChartData,
}: InstrumentDetailClientProps) {
  const [chartInterval, setChartInterval] = useState<ChartInterval>("1d");
  const [chartRangeDays, setChartRangeDays] = useState<ChartRangeDays>(365);

  const { getToken } = useAuth();
  const togglePinned = useUIStore((state) => state.togglePinnedInstrument);
  const isPinned = useUIStore((state) => state.isPinned);
  const pinned = isPinned(ticker, market);

  async function handleTogglePin(name: string, exchange: string) {
    togglePinned({ ticker, market, name, exchange });
    try {
      const token = await getToken();
      if (token) {
        if (!pinned) {
          await addToWatchlist(ticker, market, token);
        } else {
          await removeFromWatchlist(ticker, market, token);
        }
      }
    } catch {
      // best-effort backend sync
    }
  }

  const {
    data,
    error,
    isPending,
    isFetching,
  } = useQuery({
    queryKey: ["instrument", ticker, market],
    queryFn: () => fetchInstrument(ticker, market),
    initialData: initialData ?? undefined,
    staleTime: initialData ? 30_000 : 0,
    refetchOnMount: false,
    retry: (failureCount, queryError) =>
      queryError instanceof APIError && queryError.status >= 500 && failureCount < 2,
  });

  const { data: chart, isFetching: chartFetching } = useQuery({
    queryKey: ["instrument-chart", ticker, market, chartInterval, chartRangeDays],
    queryFn: () =>
      fetchInstrumentChart(ticker, market, {
        interval: chartInterval,
        range_days: chartRangeDays,
        include_indicators: true,
      }),
    initialData:
      chartInterval === "1d" && chartRangeDays === 365
        ? (initialChartData ?? undefined)
        : undefined,
    staleTime: chartInterval === "1d" && chartRangeDays === 365 && initialChartData ? 30_000 : 0,
    refetchOnMount: false,
  });

  if (isPending && !data) {
    return (
      <div className="app-shell py-12 text-center">
        <div className="text-sm text-quiet">Loading instrument data…</div>
      </div>
    );
  }

  if (!data) {
    const detail =
      error instanceof APIError
        ? error.detail ?? "This instrument detail request failed."
        : "Instrument detail is temporarily unavailable.";

    return (
      <div className="app-shell py-12">
        <div className="surface-panel rounded-[1.65rem] px-5 py-5 text-sm text-[oklch(0.9_0.03_88)]">
          {detail}
        </div>
      </div>
    );
  }

  const isRanked = data.coverage_state === "ranked" && data.conviction_level !== "UNRANKED";
  const displayName = market === "KR" && data.name_kr ? data.name_kr : data.name || ticker;
  const secondaryName = market === "KR" && data.name_kr ? data.name : data.name_kr;
  const price = data.price_metrics ?? {};
  const quarterly = data.quarterly_metrics;
  const annual = data.annual_metrics;
  const marketMetrics = data.market_metrics;
  const ownership = data.ownership_metrics;
  const changeTone =
    typeof price.change === "number" && price.change > 0
      ? "up"
      : typeof price.change === "number" && price.change < 0
        ? "down"
        : "neutral";
  const labels = market === "KR"
    ? {
        investorMetrics: "투자 지표",
        valuation: "밸류에이션",
        ownershipFlow: "수급 및 보유",
        latestClose: "최근 종가",
        marketCap: "시가총액",
        trailingPe: "PER",
        institutionalOwnership: "기관 보유비중",
        foreignOwnership: "외국인 보유비중",
        thirteenFOwners: "기관 보유기관 수",
        institutionalFlow: "기관 30일 순매수",
        foreignFlow: "외국인 30일 순매수",
        buyback: "자사주 매입",
        dayChange: "전일 대비",
        volume: "거래량",
        avgVolume: "50일 평균 거래량",
        identity: "시장 정보",
        float: "유통 주식",
        priceLiquidity: "가격 및 유동성",
        quarterly: "최근 분기 실적",
        annualIncome: "연간 손익",
        balance: "재무 상태",
        technical: "기술적 신호",
        fundamentalsDate: "보고 기준",
        coverageStatus: "커버리지 상태",
        needsPrice: "가격 데이터가 아직 없습니다. 차트와 기술 지표는 가격 수집 후 표시됩니다.",
        needsFundamentals: "가격 데이터는 있지만 재무제표가 부족합니다. 실적 지표와 전체 점수는 아직 제한됩니다.",
        needsScoring: "기초 데이터는 준비되었지만 순위 모델 점수가 아직 생성되지 않았습니다.",
        stale: "데이터가 오래되었습니다. 최신 순위에 반영되기 전까지 주의해서 봐주세요.",
        unranked: "이 종목은 유니버스에 있지만 아직 전체 순위 모델 점수가 없습니다.",
        refreshPlaceholder: "새로고침 대기열은 Part 2에서 연결됩니다.",
        refreshCta: "새로고침 준비 중",
        close: "종가",
        previousClose: "전일 종가",
        change: "변동",
        changePercent: "변동률",
        revenue: "매출",
        revenueGrowth: "매출 성장률",
        netIncome: "순이익",
        eps: "EPS",
        dilutedEps: "희석 EPS",
        epsGrowth: "EPS 성장률",
        grossProfit: "매출총이익",
        operatingCashFlow: "영업현금흐름",
        totalAssets: "총자산",
        currentAssets: "유동자산",
        currentLiabilities: "유동부채",
        longTermDebt: "장기부채",
        roa: "ROA",
        currentRatio: "유동비율",
        grossMargin: "매출총이익률",
        assetTurnover: "자산회전율",
        leverageRatio: "레버리지 비율",
        technicalComposite: "기술 점수",
        rsRating: "RS 등급",
        adRating: "A/D 등급",
        bbSqueeze: "BB 스퀴즈",
        rsLineNewHigh: "RS 라인 신고가",
        stopLoss: "7% 손절가",
        previous: "이전",
        yes: "예",
        no: "아니오",
      }
    : {
        investorMetrics: "Investor Metrics",
        valuation: "Valuation",
        ownershipFlow: "Ownership & Flow",
        latestClose: "Latest Close",
        marketCap: "Market Cap",
        trailingPe: "Trailing P/E",
        institutionalOwnership: "Institutional Ownership",
        foreignOwnership: "Foreign Ownership",
        thirteenFOwners: "13F Owner Count",
        institutionalFlow: "Institutional 30D Net Buy",
        foreignFlow: "Foreign 30D Net Buy",
        buyback: "Buyback Active",
        dayChange: "Day Change",
        volume: "Volume",
        avgVolume: "50D Avg Volume",
        identity: "Market Info",
        float: "Float",
        priceLiquidity: "Price & Liquidity",
        quarterly: "Latest Quarter",
        annualIncome: "Annual Income",
        balance: "Balance Sheet",
        technical: "Technical Pulse",
        fundamentalsDate: "Reported",
        coverageStatus: "Coverage Status",
        needsPrice: "Price history is not available yet. Charts and technical indicators will appear after price ingestion.",
        needsFundamentals: "Price data exists, but fundamentals are still missing. Financial metrics and full scoring are limited.",
        needsScoring: "Baseline data is available, but the ranking model has not generated scores yet.",
        stale: "This dataset is stale. Treat the view as a snapshot until a fresh batch ranking runs.",
        unranked: "This symbol is in the universe, but the full ranking model has not scored it yet.",
        refreshPlaceholder: "Manual refresh queue connects in Part 2.",
        refreshCta: "Refresh queue pending",
        close: "Close",
        previousClose: "Previous Close",
        change: "Change",
        changePercent: "Change %",
        revenue: "Revenue",
        revenueGrowth: "Revenue Growth",
        netIncome: "Net Income",
        eps: "EPS",
        dilutedEps: "Diluted EPS",
        epsGrowth: "EPS Growth",
        grossProfit: "Gross Profit",
        operatingCashFlow: "Operating Cash Flow",
        totalAssets: "Total Assets",
        currentAssets: "Current Assets",
        currentLiabilities: "Current Liabilities",
        longTermDebt: "Long-Term Debt",
        roa: "ROA",
        currentRatio: "Current Ratio",
        grossMargin: "Gross Margin",
        assetTurnover: "Asset Turnover",
        leverageRatio: "Leverage Ratio",
        technicalComposite: "Technical Composite",
        rsRating: "RS Rating",
        adRating: "A/D Rating",
        bbSqueeze: "BB Squeeze",
        rsLineNewHigh: "RS Line New High",
        stopLoss: "Stop Loss 7%",
        previous: "Prev",
        yes: "Yes",
        no: "No",
      };

  return (
    <div className="app-shell space-y-4 py-4 sm:py-6">
      {/* Header */}
      <div className="surface-panel rounded-[1.65rem] px-5 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <div className="tiny-label">
                {market} / {data.exchange ?? ""}
              </div>
            </div>
            <h1 className="mt-2 font-heading text-4xl uppercase tracking-[0.03em] text-white sm:text-5xl">
              {displayName}
            </h1>
            <div className="mt-1 text-sm text-quiet">
              {ticker}
              {secondaryName ? ` · ${secondaryName}` : ""}
            </div>
            {isFetching && (
              <div className="mt-2 text-xs uppercase tracking-[0.16em] text-faint">
                Refreshing…
              </div>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {convictionBadge(data.conviction_level)}
              {data.sector && (
                <span className="rounded-full border border-white/10 px-3 py-1 text-[0.68rem] uppercase tracking-widest text-faint">
                  {data.sector}
                </span>
              )}
              {data.regime_warning && (
                <span className="rounded-full border border-[oklch(0.9_0.06_75_/_0.4)] bg-[oklch(0.9_0.06_75_/_0.08)] px-3 py-1 text-[0.68rem] uppercase tracking-widest text-[oklch(0.9_0.06_75)]">
                  ⚠ Regime warning
                </span>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={() => handleTogglePin(data.name ?? ticker, data.exchange ?? "")}
            className={cn(
              "inline-flex shrink-0 items-center gap-2 rounded-full border px-4 py-2 text-[0.72rem] uppercase tracking-[0.16em] transition-colors",
              pinned
                ? "border-[oklch(0.78_0.11_84_/_0.42)] bg-[oklch(0.8_0.11_84_/_0.14)] text-white"
                : "border-white/8 text-faint hover:text-white"
            )}
          >
            <Pin className="size-3.5" />
            {pinned ? "Pinned" : "Pin"}
          </button>
        </div>
      </div>

      {!isRanked && (
        <div className="surface-panel rounded-[1.65rem] border border-[oklch(0.9_0.03_88_/_0.18)] px-5 py-4">
          <div className="tiny-label">{labels.coverageStatus}</div>
          <div className="mt-2 text-sm leading-6 text-quiet">
            {data.coverage_state === "needs_price"
              ? labels.needsPrice
              : data.coverage_state === "needs_fundamentals"
                ? labels.needsFundamentals
                : data.coverage_state === "needs_scoring"
                  ? labels.needsScoring
                  : data.coverage_state === "stale"
                    ? labels.stale
                    : labels.unranked}
          </div>
          {data.ranking_eligibility?.reasons && data.ranking_eligibility.reasons.length > 0 && (
            <div className="mt-3 text-xs text-faint">
              {data.ranking_eligibility.reasons.join(" · ")}
            </div>
          )}
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
            <button
              type="button"
              disabled
              className="inline-flex items-center justify-center gap-2 rounded-full border border-white/20 bg-white/5 hover:bg-white/10 px-5 py-2.5 text-xs font-medium uppercase tracking-[0.08em] text-white transition-colors disabled:opacity-50"
            >
              <RefreshCw className="size-3.5" />
              {labels.refreshCta}
            </button>
            <div className="text-xs text-faint">
              {labels.refreshPlaceholder}
            </div>
          </div>
        </div>
      )}

      <div className="surface-panel rounded-[1.65rem] px-5 py-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="tiny-label">{labels.investorMetrics}</div>
            <div className="mt-2 text-sm text-quiet">
              Only sourced backend fields are shown. Missing metrics stay explicit until provider data is reliable.
            </div>
          </div>
          <div className="text-xs text-faint">
            {labels.fundamentalsDate}: {formatDate(quarterly?.report_date ?? annual?.report_date, market)}
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <MetricCard
            market={market}
            label={labels.latestClose}
            value={formatPrice(price.close, market)}
            note={formatDate(price.trade_date, market)}
          />
          <MetricCard
            market={market}
            label={labels.marketCap}
            value={compactMoney(marketMetrics?.market_cap, market)}
            note={marketMetrics?.share_count_source ?? missingLabel(market)}
          />
          <MetricCard
            market={market}
            label={labels.trailingPe}
            value={formatRatio(marketMetrics?.trailing_pe_ratio, market)}
            note={marketMetrics?.trailing_eps_source ?? missingLabel(market)}
          />
          <MetricCard
            market={market}
            label={market === "KR" ? labels.foreignOwnership : labels.institutionalOwnership}
            value={
              market === "KR"
                ? formatPercent(ownership?.foreign_ownership_pct, market)
                : formatPercent(ownership?.institutional_pct, market)
            }
            note={ownership?.data_source ?? missingLabel(market)}
          />
          <MetricCard
            market={market}
            label={market === "KR" ? labels.institutionalFlow : labels.thirteenFOwners}
            value={
              market === "KR"
                ? compactCount(ownership?.institutional_net_buy_30d, market)
                : compactCount(ownership?.num_institutional_owners, market)
            }
            note={
              market === "KR"
                ? `${labels.fundamentalsDate}: ${formatDate(ownership?.report_date, market)}`
                : ownership?.qoq_owner_change != null
                  ? `QoQ ${ownership.qoq_owner_change > 0 ? "+" : ""}${ownership.qoq_owner_change}`
                  : missingLabel(market)
            }
          />
        </div>

        <div className="mt-4 space-y-3">
          <MetricSection
            title={labels.priceLiquidity}
            subtitle={`${labels.latestClose}: ${formatDate(price.trade_date, market)}`}
          >
            <MetricRow label={labels.close} value={formatPrice(price.close, market)} />
            <MetricRow label={labels.previousClose} value={formatPrice(price.previous_close, market)} />
            <MetricRow label={labels.change} value={formatPrice(price.change, market)} />
            <MetricRow label={labels.changePercent} value={formatPercent(price.change_percent, market, "points")} />
            <MetricRow label={labels.volume} value={compactCount(price.volume, market)} />
            <MetricRow label={labels.avgVolume} value={compactCount(price.avg_volume_50d, market)} />
          </MetricSection>

          <MetricSection
            title={labels.valuation}
            subtitle={marketMetrics?.price_as_of ? formatDate(marketMetrics.price_as_of, market) : missingLabel(market)}
            defaultOpen={false}
          >
            <MetricRow label={labels.marketCap} value={compactMoney(marketMetrics?.market_cap, market)} />
            <MetricRow label="Float Market Cap" value={compactMoney(marketMetrics?.float_market_cap, market)} />
            <MetricRow label={labels.trailingPe} value={formatRatio(marketMetrics?.trailing_pe_ratio, market)} />
            <MetricRow label="Dividend Yield" value={formatPercent(marketMetrics?.dividend_yield, market)} />
            <MetricRow label="Share Source" value={plainValue(marketMetrics?.share_count_source, market)} />
            <MetricRow label="EPS Source" value={plainValue(marketMetrics?.trailing_eps_source, market)} />
          </MetricSection>

          <MetricSection
            title={labels.ownershipFlow}
            subtitle={ownership?.report_date ? formatDate(ownership.report_date, market) : missingLabel(market)}
            defaultOpen={false}
          >
            <MetricRow label={labels.institutionalOwnership} value={formatPercent(ownership?.institutional_pct, market)} />
            <MetricRow label={labels.foreignOwnership} value={formatPercent(ownership?.foreign_ownership_pct, market)} />
            <MetricRow label={labels.thirteenFOwners} value={compactCount(ownership?.num_institutional_owners, market)} />
            <MetricRow label={labels.institutionalFlow} value={compactCount(ownership?.institutional_net_buy_30d, market)} />
            <MetricRow label={labels.foreignFlow} value={compactCount(ownership?.foreign_net_buy_30d, market)} />
            <MetricRow label="Individual 30D Net Buy" value={compactCount(ownership?.individual_net_buy_30d, market)} />
            <MetricRow label="Top Fund Quality" value={formatRatio(ownership?.top_fund_quality_score, market)} />
            <MetricRow label="QoQ Owner Change" value={plainValue(ownership?.qoq_owner_change, market)} />
            <MetricRow label={labels.buyback} value={ownership?.is_buyback_active == null ? missingLabel(market) : ownership.is_buyback_active ? labels.yes : labels.no} />
            <MetricRow label="Source" value={plainValue(ownership?.data_source, market)} />
          </MetricSection>

          <MetricSection
            title={labels.quarterly}
            subtitle={
              quarterly?.fiscal_year && quarterly?.fiscal_quarter
                ? `FY${quarterly.fiscal_year} Q${quarterly.fiscal_quarter} · ${formatDate(quarterly.report_date, market)}`
                : missingLabel(market)
            }
            defaultOpen={false}
          >
            <MetricRow label={labels.revenue} value={compactMoney(quarterly?.revenue, market)} />
            <MetricRow label={labels.revenueGrowth} value={formatPercent(quarterly?.revenue_yoy_growth, market)} />
            <MetricRow label={labels.netIncome} value={compactMoney(quarterly?.net_income, market)} />
            <MetricRow label={labels.eps} value={plainValue(quarterly?.eps, market)} />
            <MetricRow label={labels.dilutedEps} value={plainValue(quarterly?.eps_diluted, market)} />
            <MetricRow label={labels.epsGrowth} value={formatPercent(quarterly?.eps_yoy_growth, market)} />
          </MetricSection>

          <MetricSection
            title={labels.annualIncome}
            subtitle={annual?.fiscal_year ? `FY${annual.fiscal_year} · ${formatDate(annual.report_date, market)}` : missingLabel(market)}
            defaultOpen={false}
          >
            <MetricRow label={labels.revenue} value={compactMoney(annual?.revenue, market)} />
            <MetricRow label={labels.grossProfit} value={compactMoney(annual?.gross_profit, market)} />
            <MetricRow label={labels.netIncome} value={compactMoney(annual?.net_income, market)} />
            <MetricRow label={labels.operatingCashFlow} value={compactMoney(annual?.operating_cash_flow, market)} />
            <MetricRow label={labels.eps} value={plainValue(annual?.eps, market)} />
            <MetricRow label={labels.epsGrowth} value={formatPercent(annual?.eps_yoy_growth, market)} />
          </MetricSection>

          <MetricSection title={labels.balance} defaultOpen={false}>
            <MetricRow label={labels.totalAssets} value={compactMoney(annual?.total_assets, market)} />
            <MetricRow label={labels.currentAssets} value={compactMoney(annual?.current_assets, market)} />
            <MetricRow label={labels.currentLiabilities} value={compactMoney(annual?.current_liabilities, market)} />
            <MetricRow label={labels.longTermDebt} value={compactMoney(annual?.long_term_debt, market)} />
            <MetricRow label={labels.roa} value={formatPercent(annual?.roa, market)} />
            <MetricRow label={labels.currentRatio} value={formatRatio(annual?.current_ratio, market)} />
            <MetricRow label={labels.grossMargin} value={formatPercent(annual?.gross_margin, market)} />
            <MetricRow label={labels.assetTurnover} value={formatRatio(annual?.asset_turnover, market)} />
            <MetricRow label={labels.leverageRatio} value={formatRatio(annual?.leverage_ratio, market)} />
          </MetricSection>

          <MetricSection title={labels.technical} defaultOpen={false}>
            <MetricRow label={labels.technicalComposite} value={plainValue(data.technical_composite, market)} />
            <MetricRow label={labels.rsRating} value={plainValue(data.rs_rating, market)} />
            <MetricRow label={labels.adRating} value={plainValue(data.ad_rating, market)} />
            <MetricRow label={labels.bbSqueeze} value={data.bb_squeeze == null ? missingLabel(market) : data.bb_squeeze ? labels.yes : labels.no} />
            <MetricRow label={labels.rsLineNewHigh} value={data.rs_line_new_high == null ? missingLabel(market) : data.rs_line_new_high ? labels.yes : labels.no} />
            <MetricRow label={labels.stopLoss} value={formatPrice(data.stop_loss_7pct, market)} />
          </MetricSection>
        </div>
      </div>

      {/* Scores grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {scoreChip("Consensus", isRanked ? data.final_score : undefined)}
        {scoreChip("CANSLIM", typeof data.canslim_score === "number" && data.canslim_score > 0 ? data.canslim_score : undefined)}
        {scoreChip(
          "Piotroski",
          typeof data.piotroski_score === "number" && data.piotroski_score > 0
            ? (data.piotroski_score / 9) * 100
            : undefined,
          100
        )}
        {scoreChip(
          "Minervini",
          typeof data.minervini_score === "number" && data.minervini_score > 0
            ? (data.minervini_score / 8) * 100
            : undefined,
          100
        )}
        {scoreChip("Weinstein", typeof data.weinstein_score === "number" && data.weinstein_score > 0 ? data.weinstein_score : undefined)}
      </div>

      {/* Strategy passes */}
      <div className="surface-panel rounded-[1.65rem] px-5 py-5">
        <div className="tiny-label mb-4">Strategy Breakdown</div>
        <div className="grid gap-3 sm:grid-cols-2">
          {/* CANSLIM */}
          {data.canslim_breakdown && (
            <div>
              <div className="mb-2 text-xs text-faint uppercase tracking-widest">CANSLIM</div>
              <div className="flex flex-wrap gap-1">
                {data.canslim_breakdown.map((c) => (
                  <span
                    key={c.key}
                    className={cn(
                      "rounded border px-2 py-0.5 text-[0.65rem] font-mono uppercase",
                      c.score > 0
                        ? "border-[oklch(0.92_0.04_150_/_0.4)] text-[oklch(0.92_0.04_150)]"
                        : "border-white/10 text-faint"
                    )}
                    title={c.label}
                  >
                    {c.key}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Piotroski */}
          {data.piotroski_detail && (
            <div>
              <div className="mb-2 text-xs text-faint uppercase tracking-widest">
                Piotroski F-Score: {data.piotroski_detail.f_score}/9
              </div>
              <div className="flex flex-wrap gap-1">
                {(Object.entries(data.piotroski_detail) as [string, boolean | number][])
                  .filter(([k]) => k.startsWith("f") && k !== "f_score")
                  .map(([k, v]) => (
                    <span
                      key={k}
                      className={cn(
                        "rounded border px-2 py-0.5 text-[0.65rem] font-mono uppercase",
                        v
                          ? "border-[oklch(0.92_0.04_150_/_0.4)] text-[oklch(0.92_0.04_150)]"
                          : "border-white/10 text-faint"
                      )}
                    >
                      {k.toUpperCase()}
                    </span>
                  ))}
              </div>
            </div>
          )}

          {/* Minervini */}
          {data.minervini_detail && (
            <div>
              <div className="mb-2 text-xs text-faint uppercase tracking-widest">
                Minervini: {data.minervini_detail.count_passing}/8
              </div>
              <div className="flex flex-wrap gap-1">
                {(Object.entries(data.minervini_detail) as [string, boolean | number][])
                  .filter(([k]) => k.startsWith("t"))
                  .map(([k, v]) => (
                    <span
                      key={k}
                      className={cn(
                        "rounded border px-2 py-0.5 text-[0.65rem] font-mono uppercase",
                        v
                          ? "border-[oklch(0.92_0.04_150_/_0.4)] text-[oklch(0.92_0.04_150)]"
                          : "border-white/10 text-faint"
                      )}
                    >
                      {k.toUpperCase()}
                    </span>
                  ))}
              </div>
            </div>
          )}

          {/* Weinstein */}
          {data.weinstein_detail && (
            <div>
              <div className="mb-2 text-xs text-faint uppercase tracking-widest">Weinstein</div>
              <div className="text-sm text-white">
                Stage {data.weinstein_detail.stage}
                {data.weinstein_detail.sub_stage ? ` · ${data.weinstein_detail.sub_stage}` : ""}
              </div>
              <div className="mt-1 text-xs text-faint">
                MA slope {data.weinstein_detail.ma_slope.toFixed(2)} ·{" "}
                {data.weinstein_detail.price_vs_ma > 0 ? "+" : ""}
                {(data.weinstein_detail.price_vs_ma * 100).toFixed(1)}% vs MA
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Price chart */}
      <InstrumentChartComponent
        data={chart ?? null}
        interval={chartInterval}
        rangeDays={chartRangeDays}
        onIntervalChange={setChartInterval}
        onRangeChange={setChartRangeDays}
        isFetching={chartFetching}
      />

      {/* Freshness */}
      {data.freshness && (
        <div className="surface-panel rounded-[1.65rem] px-5 py-4">
          <div className="tiny-label mb-2">Data Freshness</div>
          <div className="flex flex-wrap gap-4 text-xs text-faint">
            {Object.entries(data.freshness).map(([k, v]) => (
              <span key={k}>
                <span className="capitalize">{k.replace(/_/g, " ")}</span>:{" "}
                <span className={v ? "text-white" : "text-faint"}>{v ?? "—"}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
