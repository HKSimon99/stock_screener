"use client";

/**
 * StrategiesClient — 3-tab strategy breakdown page
 *
 * Tabs:
 *  • CANSLIM      — US-only (growth-stock strategy designed for US markets)
 *  • Piotroski    — US + KR (fundamental health score, F-score 0–9)
 *  • Magic Formula — US + KR (ROIC + EY, high-quality value)
 *
 * Each tab fetches strategy-specific rankings via fetchStrategyRankings()
 * and renders items with the shared RankingRow component.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  APIError,
  fetchStrategyRankings,
  type StrategyRankingsResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { RankingRow } from "@/components/ranking-row";
import { CanslimTab } from "@/app/app/strategies/_components/canslim-filter-builder";
import { useT } from "@/hooks/use-t";
import type { Lang } from "@/lib/i18n";

// ── Types ─────────────────────────────────────────────────────────────────────

type StrategyTab = "canslim" | "piotroski" | "magic_formula";

// ── Strategy metadata ─────────────────────────────────────────────────────────

interface StrategyCriterion {
  label: string;
  desc: string;
}

interface StrategyInfo {
  guru: string;
  guruTitle: string;
  tagline: string;
  description: string;
  criteria: StrategyCriterion[];
}

const STRATEGY_INFO_EN: Record<StrategyTab, StrategyInfo> = {
  canslim: {
    guru: "William J. O'Neil",
    guruTitle: "Founder, Investor's Business Daily",
    tagline: "7 criteria for growth stocks",
    description:
      "Developed by IBD founder William O'Neil in 1988. Combines earnings growth, institutional buying, and market trend to find stocks poised for a big move. Each letter is an independent filter — the more criteria a stock passes, the stronger the case.",
    criteria: [
      { label: "C — Current EPS",    desc: "Quarterly EPS up 25% or more year-over-year" },
      { label: "A — Annual EPS",     desc: "Annual EPS growth of 25%+ over the past 3 years" },
      { label: "N — New",            desc: "New product, service, or 52-week high" },
      { label: "S — Supply & Demand", desc: "Volume spike with relatively low float" },
      { label: "L — Leader",         desc: "RS rating 80+ (top 20% of sector)" },
      { label: "I — Institutional",  desc: "Rising institutional ownership" },
      { label: "M — Market",         desc: "Only buy in a confirmed uptrend" },
    ],
  },
  piotroski: {
    guru: "Joseph Piotroski",
    guruTitle: "Professor, Stanford Graduate School of Business",
    tagline: "9-point financial health score",
    description:
      "Published in a 2000 paper by Stanford professor Joseph Piotroski. Scores nine binary tests across profitability, leverage, and efficiency — each passes (1) or fails (0). F-Score 8–9 signals a financially strong company; 0–2 signals a weak one. Particularly effective at avoiding value traps.",
    criteria: [
      { label: "ROA > 0",           desc: "Net income positive relative to assets" },
      { label: "Operating cash flow > 0", desc: "Generating real cash, not just book earnings" },
      { label: "ROA improving",     desc: "ROA higher than the prior year" },
      { label: "Accruals < 0",      desc: "Cash earnings exceed book earnings (earnings quality)" },
      { label: "Leverage falling",  desc: "Long-term debt ratio declining" },
      { label: "Liquidity improving", desc: "Better short-term coverage ratio" },
      { label: "No dilution",       desc: "No new shares issued" },
      { label: "Asset turnover up", desc: "More revenue per dollar of assets" },
      { label: "Gross margin up",   desc: "Improving profitability structure" },
    ],
  },
  magic_formula: {
    guru: "Joel Greenblatt",
    guruTitle: "Founder, Gotham Capital · Professor, Columbia",
    tagline: "ROIC + earnings yield combined rank",
    description:
      "Published in 'The Little Book That Beats the Market' (2005) by hedge fund manager Joel Greenblatt. Simplifies Buffett's 'buy good companies cheap' principle into two numbers. Rank stocks by ROIC (quality) and earnings yield (value) separately, then add the ranks. The lowest combined rank wins.",
    criteria: [
      {
        label: "ROIC",
        desc: "EBIT ÷ (net working capital + net fixed assets) — higher is better quality",
      },
      {
        label: "Earnings Yield",
        desc: "EBIT ÷ enterprise value (market cap + debt – cash) — higher means cheaper",
      },
      {
        label: "Combined rank",
        desc: "ROIC rank + EY rank — lower combined rank means more attractive",
      },
    ],
  },
};

const STRATEGY_INFO_KO: Record<StrategyTab, StrategyInfo> = {
  canslim: {
    guru: "William J. O'Neil",
    guruTitle: "Investor's Business Daily 창업자",
    tagline: "성장주 7대 기준",
    description:
      "IBD 창업자 윌리엄 오닐이 1988년 정리한 성장주 선별 기준. 주당순이익(EPS)과 매출 성장, 기관 매수, 시장 추세를 결합해 폭발적 성장이 임박한 종목을 찾습니다. CAN SLIM 각 글자는 독립적인 필터로, 더 많이 통과할수록 확신도가 높아집니다.",
    criteria: [
      { label: "C — Current EPS",  desc: "최근 분기 EPS 전년 대비 25% 이상 성장" },
      { label: "A — Annual EPS",   desc: "최근 3년 연간 EPS 25% 이상 성장" },
      { label: "N — 새로운 것",    desc: "신제품·신서비스·52주 신고가" },
      { label: "S — 수급",         desc: "거래량 급증 + 유통주식 수 적음" },
      { label: "L — 주도주",       desc: "RS 등급 80 이상 (섹터 내 상위 20%)" },
      { label: "I — 기관",         desc: "기관 순매수 증가" },
      { label: "M — 시장 방향",    desc: "상승 장세에서만 매수" },
    ],
  },
  piotroski: {
    guru: "Joseph Piotroski",
    guruTitle: "스탠퍼드 경영대학원 교수",
    tagline: "재무 건전성 9점 F-Score",
    description:
      "스탠퍼드 교수 조셉 피오트로스키가 2000년 발표한 논문의 재무 건전성 점수. 수익성·레버리지·효율성 9개 항목을 0/1로 채점해 합산합니다. F-Score 8~9는 재무적으로 강한 기업, 0~2는 위험 기업입니다. 가치 함정(value trap)을 피하는 데 특히 효과적입니다.",
    criteria: [
      { label: "ROA > 0",          desc: "총자산 대비 순이익 양수" },
      { label: "영업 현금흐름 > 0", desc: "장부 이익이 아닌 실제 현금 창출" },
      { label: "ROA 개선",         desc: "전년 대비 ROA 증가" },
      { label: "발생액 < 0",       desc: "현금이익 > 장부이익 (이익 품질 확인)" },
      { label: "부채비율 감소",    desc: "장기부채 비중 하락" },
      { label: "유동비율 개선",    desc: "단기 지급 능력 향상" },
      { label: "희석 없음",        desc: "신주 발행 없음" },
      { label: "총자산회전율 개선", desc: "자산 효율 상승" },
      { label: "매출총이익률 개선", desc: "수익성 구조 개선" },
    ],
  },
  magic_formula: {
    guru: "Joel Greenblatt",
    guruTitle: "고담 캐피탈 창업자 · 컬럼비아 교수",
    tagline: "ROIC + 이익수익률 복합 순위",
    description:
      "헤지펀드 매니저 조엘 그린블라트가 《주식시장을 이기는 작은 책》(2005)에서 공개한 전략. '좋은 기업을 저렴하게 사라'는 원칙을 두 개의 숫자로 단순화했습니다. ROIC(우량성)와 이익수익률(저평가) 순위를 각각 매긴 뒤 합산해, 복합 순위가 낮은 종목을 선택합니다.",
    criteria: [
      {
        label: "ROIC (자본이익률)",
        desc: "EBIT ÷ (순운전자본 + 순고정자산) — 높을수록 우량",
      },
      {
        label: "EY (이익수익률)",
        desc: "EBIT ÷ 기업가치(시총+부채-현금) — 높을수록 저평가",
      },
      {
        label: "복합 순위",
        desc: "ROIC 순위 + EY 순위 합산 — 낮을수록 매력적",
      },
    ],
  },
};

const TAB_LABELS: Record<StrategyTab, string> = {
  canslim:       "CANSLIM",
  piotroski:     "Piotroski",
  magic_formula: "Magic Formula",
};

/** Markets available per strategy (CANSLIM is US-only) */
const STRATEGY_MARKETS: Record<StrategyTab, Array<"US" | "KR">> = {
  canslim:       ["US"],
  piotroski:     ["US", "KR"],
  magic_formula: ["US", "KR"],
};

function getStrategyInfo(lang: Lang): Record<StrategyTab, StrategyInfo> {
  return lang === "ko" ? STRATEGY_INFO_KO : STRATEGY_INFO_EN;
}

// ── Sub-component: strategy info card ────────────────────────────────────────

function StrategyInfoCard({ tab, lang }: { tab: StrategyTab; lang: Lang }) {
  const info = getStrategyInfo(lang)[tab];
  return (
    <div className="motion-panel-in surface-panel rounded-2xl px-5 py-5 space-y-4">
      {/* Guru */}
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <div className="tiny-label">{info.tagline}</div>
          <h2 className="mt-1 font-heading text-xl font-bold uppercase text-white">
            {info.guru}
          </h2>
          <div className="mt-0.5 text-[0.68rem] text-faint">{info.guruTitle}</div>
          <p className="mt-3 text-xs leading-5 text-quiet">{info.description}</p>
        </div>
      </div>

      {/* Criteria grid */}
      <div className="grid gap-1.5 sm:grid-cols-2">
        {info.criteria.map((c) => (
          <div
            key={c.label}
            className="motion-card rounded-xl border border-white/8 bg-white/[0.06] px-3.5 py-2.5"
          >
            <div className="text-[0.65rem] font-medium uppercase tracking-[0.12em] text-white/70">
              {c.label}
            </div>
            <div className="mt-0.5 text-[0.7rem] leading-4 text-faint">{c.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Sub-component: strategy list ──────────────────────────────────────────────

interface StrategyListProps {
  strategy: StrategyTab;
  market: "US" | "KR";
  initialData?: StrategyRankingsResponse;
}

function StrategyList({ strategy, market, initialData }: StrategyListProps) {
  const { t } = useT();
  const { data, error, isFetching } = useQuery({
    queryKey: ["strategy-rankings", strategy, market],
    queryFn:  () => fetchStrategyRankings(strategy, market),
    initialData,
    staleTime: 60_000,
    retry: (failureCount, queryError) =>
      queryError instanceof APIError && queryError.status >= 500 && failureCount < 2,
  });

  if (isFetching && !data) {
    return (
      <div className="surface-panel rounded-2xl px-5 py-8 text-center text-sm text-quiet">
        {t("ui.loading")}
      </div>
    );
  }

  if (error) {
    return (
      <div className="surface-panel rounded-2xl border border-[oklch(0.68_0.18_28_/_0.3)] bg-[oklch(0.31_0.06_28_/_0.14)] px-5 py-5 text-sm text-[oklch(0.89_0.04_24)]">
        {error instanceof APIError
          ? error.detail ?? t("strategies.unavailable")
          : t("strategies.unavailable")}
      </div>
    );
  }

  if (!data?.items?.length) {
    return (
      <div className="surface-panel rounded-2xl px-5 py-8 text-center text-sm text-quiet">
        {t("strategies.empty")}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {isFetching && (
        <div className="text-right text-[0.65rem] text-faint">{t("alerts.refreshing")}</div>
      )}
      {data.items.map((item) => (
        <RankingRow
          key={`${item.market}-${item.ticker}`}
          item={{
            rank:        item.rank,
            ticker:      item.ticker,
            name:        item.name,
            market:      item.market,
            // StrategyRankingItem has no exchange field — omit
            final_score: item.score ?? 0,
          }}
        />
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface StrategiesClientProps {
  initialData?: Partial<Record<string, StrategyRankingsResponse>>;
}

export function StrategiesClient({ initialData = {} }: StrategiesClientProps) {
  const [activeTab, setActiveTab] = useState<StrategyTab>("canslim");
  const [market, setMarket]       = useState<"US" | "KR">("US");
  const { t, lang }               = useT();

  const availableMarkets = STRATEGY_MARKETS[activeTab];

  // When switching to CANSLIM, force US (it's US-only)
  function handleTabChange(tab: StrategyTab) {
    setActiveTab(tab);
    if (STRATEGY_MARKETS[tab].length === 1) {
      setMarket(STRATEGY_MARKETS[tab][0]);
    }
  }

  const cacheKey = `${activeTab}-${market}`;

  return (
    <div className="app-shell mobile-safe-bottom space-y-4 py-4 sm:py-6">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="surface-panel rounded-2xl px-5 py-5">
        <div className="tiny-label">{t("nav.strategies")}</div>
        <h1 className="mt-2 font-heading text-4xl font-bold uppercase text-white">
          {t("strategies.headline")}
        </h1>
        <p className="mt-1 text-xs text-faint">
          {t("strategies.sub")}
        </p>

        {/* ── Tab bar ────────────────────────────────────────────────── */}
        <div className="mt-5 flex flex-wrap gap-2">
          <div className="flex gap-0.5 rounded-full border border-white/8 p-0.5">
            {(Object.keys(TAB_LABELS) as StrategyTab[]).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => handleTabChange(tab)}
                className={cn(
                  "motion-press rounded-full px-4 py-1.5 text-[0.72rem] uppercase tracking-[0.14em] transition-colors",
                  activeTab === tab
                    ? "bg-white/10 text-white"
                    : "text-faint hover:text-quiet"
                )}
              >
                {TAB_LABELS[tab]}
              </button>
            ))}
          </div>

          {/* Market selector — hidden for CANSLIM (US-only) */}
          {availableMarkets.length > 1 && (
            <div className="flex gap-0.5 rounded-full border border-white/8 p-0.5">
              {availableMarkets.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMarket(m)}
                  className={cn(
                    "motion-press rounded-full px-4 py-1.5 text-[0.72rem] uppercase tracking-[0.14em] transition-colors",
                    market === m
                      ? "bg-white/10 text-white"
                      : "text-faint hover:text-quiet"
                  )}
                >
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Context note */}
        {activeTab === "canslim" && (
          <div className="mt-3 text-[0.65rem] text-faint">
            {t("strategies.canslimNote")}
          </div>
        )}
      </div>

      {/* ── Strategy info card ─────────────────────────────────────────── */}
      <StrategyInfoCard tab={activeTab} lang={lang} />

      {/* ── Strategy list ──────────────────────────────────────────────── */}
      {activeTab === "canslim" ? (
        <CanslimTab initialData={initialData["canslim-US"]} />
      ) : (
        <StrategyList
          key={cacheKey}
          strategy={activeTab}
          market={market}
          initialData={initialData[cacheKey]}
        />
      )}
    </div>
  );
}
