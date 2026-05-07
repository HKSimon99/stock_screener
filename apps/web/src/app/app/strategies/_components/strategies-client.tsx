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

const STRATEGY_INFO: Record<StrategyTab, StrategyInfo> = {
  canslim: {
    guru: "William J. O'Neil",
    guruTitle: "Investor's Business Daily 창업자",
    tagline: "성장주 7대 기준",
    description:
      "IBD 창업자 윌리엄 오닐이 1988년 정리한 성장주 선별 기준. 주당순이익(EPS)과 매출 성장, 기관 매수, 시장 추세를 결합해 '폭발적 성장이 임박한 종목'을 찾는다. CAN SLIM 각 글자는 독립적인 필터로, 모두 통과할수록 확신도가 높다.",
    criteria: [
      { label: "C — Current EPS", desc: "최근 분기 EPS 25% 이상 성장" },
      { label: "A — Annual EPS", desc: "최근 3년 연간 EPS 25% 이상 성장" },
      { label: "N — New Product", desc: "신제품·신서비스·52주 신고가" },
      { label: "S — Supply & Demand", desc: "거래량 급증 + 낮은 유통주식 수" },
      { label: "L — Leader", desc: "RS 등급 80 이상 (섹터 내 상위 20%)" },
      { label: "I — Institutional", desc: "기관 순매수 증가" },
      { label: "M — Market Direction", desc: "상승 장세(Confirmed Uptrend)에서만 매수" },
    ],
  },
  piotroski: {
    guru: "Joseph Piotroski",
    guruTitle: "스탠퍼드 경영대학원 교수",
    tagline: "재무 건전성 9점 F-Score",
    description:
      "스탠퍼드 교수 조셉 피오트로스키가 2000년 발표한 논문에서 제시한 재무 건전성 점수. 수익성·레버리지·효율성 9개 항목을 0/1로 채점해 합산. F-Score 8–9는 '재무적으로 강한 기업', 0–2는 '위험 기업'으로 분류한다. 가치주 함정(value trap)을 피하는 데 특히 효과적이다.",
    criteria: [
      { label: "ROA > 0", desc: "총자산 대비 순이익 양수" },
      { label: "영업 현금흐름 > 0", desc: "실제 현금 창출" },
      { label: "ROA 개선", desc: "전년 대비 ROA 증가" },
      { label: "발생액 < 0", desc: "현금이익 > 장부이익 (분식 방어)" },
      { label: "부채비율 감소", desc: "장기부채 비중 하락" },
      { label: "유동비율 개선", desc: "단기 지급 능력 향상" },
      { label: "희석 없음", desc: "신주 발행 없음" },
      { label: "총자산회전율 개선", desc: "자산 효율 상승" },
      { label: "매출총이익률 개선", desc: "수익성 구조 개선" },
    ],
  },
  magic_formula: {
    guru: "Joel Greenblatt",
    guruTitle: "고담 캐피탈 창업자 · 컬럼비아 교수",
    tagline: "ROIC + 이익수익률 복합 랭킹",
    description:
      "헤지펀드 매니저 조엘 그린블라트가 《주식시장을 이기는 작은 책》(2005)에서 공개한 전략. '좋은 기업을 저렴한 가격에 사라'는 워런 버핏의 원칙을 두 개의 숫자로 단순화했다. ROIC가 높은 기업(우량 기업)과 이익수익률(EY)이 높은 기업(저평가 기업)의 순위를 합산해, 복합 순위가 낮은 종목을 선택한다.",
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
        desc: "ROIC 순위 + EY 순위 합산 → 낮을수록 매력적",
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

// ── Sub-component: strategy info card ────────────────────────────────────────

function StrategyInfoCard({ tab }: { tab: StrategyTab }) {
  const info = STRATEGY_INFO[tab];
  return (
    <div className="surface-panel rounded-2xl px-5 py-5 space-y-4">
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
            className="rounded-xl border border-white/8 bg-white/[0.06] px-3.5 py-2.5"
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
        Loading…
      </div>
    );
  }

  if (error) {
    return (
      <div className="surface-panel rounded-2xl border border-[oklch(0.68_0.18_28_/_0.3)] bg-[oklch(0.31_0.06_28_/_0.14)] px-5 py-5 text-sm text-[oklch(0.89_0.04_24)]">
        {error instanceof APIError
          ? error.detail ?? `${TAB_LABELS[strategy]} rankings are temporarily unavailable.`
          : `${TAB_LABELS[strategy]} rankings are temporarily unavailable.`}
      </div>
    );
  }

  if (!data?.items?.length) {
    return (
      <div className="surface-panel rounded-2xl px-5 py-8 text-center text-sm text-quiet">
        No {TAB_LABELS[strategy]} rankings available for {market}.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {isFetching && (
        <div className="text-right text-[0.65rem] text-faint">refreshing…</div>
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
        <div className="tiny-label">Strategies</div>
        <h1 className="mt-2 font-heading text-4xl font-bold uppercase text-white">
          Strategy Rankings
        </h1>
        <p className="mt-1 text-xs text-faint">
          Per-strategy scores ranked independently — drill into each methodology.
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
                  "rounded-full px-4 py-1.5 text-[0.72rem] uppercase tracking-[0.14em] transition-colors",
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
                    "rounded-full px-4 py-1.5 text-[0.72rem] uppercase tracking-[0.14em] transition-colors",
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
            CANSLIM is designed for US growth stocks — KR market not included.
          </div>
        )}
      </div>

      {/* ── Strategy info card ─────────────────────────────────────────── */}
      <StrategyInfoCard tab={activeTab} />

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
