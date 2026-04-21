import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import {
  ChartPriceBar,
  InstrumentDetail,
  fetchInstrument,
  fetchInstrumentChart,
} from "@consensus/api-client";
import { CandlestickChart } from "react-native-wagmi-charts";
import { ConvictionBadge } from "@/components/ui/conviction-badge";
import { Panel } from "@/components/ui/panel";
import { Pip } from "@/components/ui/pip";
import { Display, Kicker } from "@/components/ui/typography";
import { FONTS, getTheme } from "@/lib/theme";
import { isPinnedInstrument, togglePinnedInstrument } from "@/lib/pinned";

type ChartRange = "1M" | "3M" | "6M" | "1Y";
type Params = { market?: string | string[]; ticker?: string | string[] };

const CHART_RANGES: Record<ChartRange, number> = {
  "1M": 30,
  "3M": 90,
  "6M": 180,
  "1Y": 365,
};

function getParamValue(value?: string | string[]) {
  return Array.isArray(value) ? value[0] : value;
}

function formatCurrency(value: number | null, market: "US" | "KR") {
  if (value == null || !Number.isFinite(value)) {
    return "--";
  }

  return new Intl.NumberFormat(market === "KR" ? "ko-KR" : "en-US", {
    style: "currency",
    currency: market === "KR" ? "KRW" : "USD",
    maximumFractionDigits: market === "KR" ? 0 : 2,
  }).format(value);
}

function formatSigned(value: number | null, digits = 2) {
  if (value == null || !Number.isFinite(value)) {
    return "--";
  }

  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function countActive(values: { active: boolean }[]) {
  return values.filter((value) => value.active).length;
}

function buildPriceSummary(bars: ChartPriceBar[]) {
  const latest = bars[bars.length - 1];
  const previous = bars[bars.length - 2];

  if (!latest) {
    return {
      latest: null as ChartPriceBar | null,
      changeValue: null as number | null,
      changePercent: null as number | null,
    };
  }

  if (!previous || previous.close === 0) {
    return {
      latest,
      changeValue: 0,
      changePercent: 0,
    };
  }

  const changeValue = latest.close - previous.close;
  const changePercent = (changeValue / previous.close) * 100;

  return {
    latest,
    changeValue,
    changePercent,
  };
}

function buildCandles(bars: ChartPriceBar[]) {
  return [...bars]
    .filter(
      (bar) =>
        Number.isFinite(bar.open) &&
        Number.isFinite(bar.high) &&
        Number.isFinite(bar.low) &&
        Number.isFinite(bar.close)
    )
    .sort((left, right) => new Date(left.time).getTime() - new Date(right.time).getTime())
    .map((bar) => ({
      timestamp: new Date(`${bar.time}T00:00:00Z`).getTime(),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }));
}

function buildCanslimPips(detail: InstrumentDetail) {
  const scoreMap = new Map(
    (detail.canslim_breakdown ?? []).map((item) => [item.key, item.score])
  );

  return [
    { label: "C", active: (scoreMap.get("C") ?? 0) > 0 },
    { label: "A", active: (scoreMap.get("A") ?? 0) > 0 },
    { label: "N", active: (scoreMap.get("N") ?? 0) > 0 },
    { label: "S", active: (scoreMap.get("S") ?? 0) > 0 },
    { label: "L", active: (scoreMap.get("L") ?? 0) > 0 },
    { label: "I", active: (scoreMap.get("I") ?? 0) > 0 },
    { label: "M", active: !detail.regime_warning },
  ];
}

function buildPiotroskiPips(detail: InstrumentDetail) {
  const data = detail.piotroski_detail;
  return [
    { label: "F1", active: Boolean(data?.f1) },
    { label: "F2", active: Boolean(data?.f2) },
    { label: "F3", active: Boolean(data?.f3) },
    { label: "F4", active: Boolean(data?.f4) },
    { label: "F5", active: Boolean(data?.f5) },
    { label: "F6", active: Boolean(data?.f6) },
    { label: "F7", active: Boolean(data?.f7) },
    { label: "F8", active: Boolean(data?.f8) },
    { label: "F9", active: Boolean(data?.f9) },
  ];
}

function buildMinerviniPips(detail: InstrumentDetail) {
  const data = detail.minervini_detail;
  return [
    { label: "T1", active: Boolean(data?.t1) },
    { label: "T2", active: Boolean(data?.t2) },
    { label: "T3", active: Boolean(data?.t3) },
    { label: "T4", active: Boolean(data?.t4) },
    { label: "T5", active: Boolean(data?.t5) },
    { label: "T6", active: Boolean(data?.t6) },
    { label: "T7", active: Boolean(data?.t7) },
    { label: "T8", active: Boolean(data?.t8) },
  ];
}

function formatStageLabel(stage?: string, subStage?: string) {
  const parts = [stage, subStage]
    .filter(Boolean)
    .join(" ")
    .replace(/_/g, " ")
    .trim()
    .toUpperCase();

  return parts ? `STAGE ${parts}` : "STAGE --";
}

function getStageTone(stage: string | undefined, theme: ReturnType<typeof getTheme>) {
  if (stage?.startsWith("2")) {
    return {
      backgroundColor: "rgba(116,211,155,0.14)",
      borderColor: "rgba(116,211,155,0.4)",
      color: theme.green,
    };
  }

  if (stage?.startsWith("4")) {
    return {
      backgroundColor: "rgba(231,133,118,0.14)",
      borderColor: "rgba(231,133,118,0.4)",
      color: theme.red,
    };
  }

  return {
    backgroundColor: theme.primaryDim,
    borderColor: theme.primaryLine,
    color: theme.primary,
  };
}

function StrategyPipRow({
  label,
  value,
  pips,
  theme,
}: {
  label: string;
  value: string;
  pips: { label: string; active: boolean }[];
  theme: ReturnType<typeof getTheme>;
}) {
  return (
    <View style={styles.strategySection}>
      <View style={styles.strategyHeader}>
        <Text style={[styles.strategyLabel, { color: theme.text, fontFamily: FONTS.headingSemiBold }]}>
          {label}
        </Text>
        <Text style={[styles.strategyValue, { color: theme.faint, fontFamily: FONTS.monoMedium }]}>
          {value}
        </Text>
      </View>
      <View style={styles.pipWrap}>
        {pips.map((pip) => (
          <Pip key={pip.label} label={pip.label} active={pip.active} theme={theme} />
        ))}
      </View>
    </View>
  );
}

export default function InstrumentDetailScreen() {
  const params = useLocalSearchParams<Params>();
  const market = getParamValue(params.market) === "KR" ? "KR" : "US";
  const ticker = getParamValue(params.ticker) ?? "";
  const theme = getTheme("dark");
  const router = useRouter();
  const [range, setRange] = useState<ChartRange>("6M");
  const [pinned, setPinned] = useState(false);
  const { width } = useWindowDimensions();
  const rangeDays = CHART_RANGES[range];

  const detailQuery = useQuery({
    queryKey: ["instrument", market, ticker],
    queryFn: () => fetchInstrument(ticker, market),
    enabled: Boolean(ticker),
    staleTime: 0,
    refetchOnMount: "always",
  });

  const chartQuery = useQuery({
    queryKey: ["chart", market, ticker, range],
    queryFn: () =>
      fetchInstrumentChart(ticker, market, {
        interval: "1d",
        range_days: rangeDays,
        include_indicators: true,
      }),
    enabled: Boolean(ticker),
    staleTime: 0,
    refetchOnMount: "always",
  });

  const detail = detailQuery.data;
  const chart = chartQuery.data;
  const candles = useMemo(() => buildCandles(chart?.bars ?? []), [chart?.bars]);
  const priceSummary = useMemo(
    () => buildPriceSummary(chart?.bars ?? []),
    [chart?.bars]
  );

  const priceColor =
    (priceSummary.changePercent ?? 0) >= 0 ? theme.green : theme.red;

  const chartWidth = Math.max(width - 64, 240);

  useEffect(() => {
    if (!ticker) {
      return;
    }
    setPinned(isPinnedInstrument(ticker, market));
  }, [market, ticker]);

  if (detailQuery.isLoading || chartQuery.isLoading) {
    return (
      <SafeAreaView style={[styles.loadingState, { backgroundColor: theme.bg0 }]} edges={["top"]}>
        <ActivityIndicator size="large" color={theme.primary} />
      </SafeAreaView>
    );
  }

  if (!ticker || detailQuery.isError || chartQuery.isError || !detail || !chart) {
    return (
      <SafeAreaView style={[styles.loadingState, { backgroundColor: theme.bg0 }]} edges={["top"]}>
        <Text style={[styles.errorTitle, { color: theme.text, fontFamily: FONTS.headingBold }]}>
          Instrument unavailable
        </Text>
        <Text style={[styles.errorCopy, { color: theme.quiet }]}>
          We couldn’t load this instrument view right now. Check the ticker and backend data, then try again.
        </Text>
      </SafeAreaView>
    );
  }

  const convictionTone =
    theme.conviction[detail.conviction_level] ?? theme.conviction.UNRANKED;
  const canslimPips = buildCanslimPips(detail);
  const piotroskiPips = buildPiotroskiPips(detail);
  const minerviniPips = buildMinerviniPips(detail);
  const stageTone = getStageTone(detail.weinstein_detail?.stage, theme);
  const strategyTiles = [
    { label: "CANSLIM", value: detail.canslim_score },
    { label: "PIOTROSKI", value: detail.piotroski_score },
    { label: "MINERVINI", value: detail.minervini_score },
    { label: "WEINSTEIN", value: detail.weinstein_score },
  ];

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.bg0 }]} edges={["top"]}>
      <View style={[styles.topBar, { borderBottomColor: theme.lineSoft }]}>
        <Pressable
          onPress={() => router.back()}
          style={({ pressed }) => [
            styles.backButton,
            {
              backgroundColor: theme.bg3,
              borderColor: theme.line,
              opacity: pressed ? 0.9 : 1,
            },
          ]}
        >
          <Ionicons name="chevron-back" size={16} color={theme.text} />
        </Pressable>
        <Text style={[styles.marketMeta, { color: theme.faint, fontFamily: FONTS.monoRegular }]}>
          {detail.market} / {detail.exchange ?? "--"}
        </Text>
        <Pressable
          onPress={() =>
            setPinned(
              togglePinnedInstrument({
                ticker: detail.ticker,
                market: detail.market,
                name: detail.name ?? detail.ticker,
                name_kr: detail.name_kr,
              })
            )
          }
          style={({ pressed }) => [
            styles.pinButton,
            {
              borderColor: pinned ? theme.primaryLine : theme.line,
              backgroundColor: pinned ? theme.primaryDim : "transparent",
              opacity: pressed ? 0.9 : 1,
            },
          ]}
        >
          <Ionicons
            name={pinned ? "bookmark" : "bookmark-outline"}
            size={13}
            color={pinned ? theme.primary : theme.text}
          />
          <Text
            style={[
              styles.pinButtonText,
              {
                color: pinned ? theme.primary : theme.text,
                fontFamily: FONTS.headingSemiBold,
              },
            ]}
          >
            Pin
          </Text>
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.heroHeader}>
          <View style={styles.heroText}>
            <Display
              theme={theme}
              style={[
                styles.tickerDisplay,
                { fontSize: 48, lineHeight: 48, letterSpacing: -1.8 },
              ]}
            >
              {detail.ticker}
            </Display>
            <Text style={[styles.instrumentName, { color: theme.quiet }]}>
              {detail.name}
              {detail.name_kr ? ` · ${detail.name_kr}` : ""}
            </Text>
            <View style={styles.badgeRow}>
              <ConvictionBadge level={detail.conviction_level} theme={theme} size="md" />
              {detail.sector ? (
                <View style={[styles.sectorBadge, { borderColor: theme.line }]}>
                  <Text style={[styles.sectorText, { color: theme.faint, fontFamily: FONTS.headingSemiBold }]}>
                    {detail.sector}
                  </Text>
                </View>
              ) : null}
            </View>
          </View>

          <View style={styles.priceWrap}>
            <Text style={[styles.priceText, { color: theme.text, fontFamily: FONTS.monoSemiBold }]}>
              {formatCurrency(priceSummary.latest?.close ?? null, detail.market)}
            </Text>
            <Text style={[styles.changeText, { color: priceColor, fontFamily: FONTS.monoMedium }]}>
              {formatSigned(priceSummary.changePercent, 2)}%
            </Text>
            <Text style={[styles.changeValue, { color: theme.faint, fontFamily: FONTS.monoRegular }]}>
              {formatSigned(priceSummary.changeValue, detail.market === "KR" ? 0 : 2)}
            </Text>
          </View>
        </View>

        <Panel theme={theme} style={styles.panelTight}>
          <View style={styles.panelHeaderRow}>
            <Kicker theme={theme}>Consensus score</Kicker>
            <Text style={[styles.passCount, { color: theme.faint, fontFamily: FONTS.monoRegular }]}>
              {detail.strategy_pass_count}/5 strategies pass
            </Text>
          </View>

          <View style={styles.scoreHero}>
            <Text style={[styles.scoreValue, { color: theme.text, fontFamily: FONTS.headingBold }]}>
              {detail.final_score.toFixed(1)}
            </Text>
            <Text style={[styles.scoreSuffix, { color: theme.faint, fontFamily: FONTS.monoRegular }]}>
              /100
            </Text>
          </View>

          <View style={[styles.scoreTrack, { backgroundColor: theme.bg3 }]}>
            <View
              style={[
                styles.scoreFill,
                {
                  width: `${Math.max(0, Math.min(100, detail.final_score))}%`,
                  backgroundColor: convictionTone.text,
                },
              ]}
            />
          </View>

          <View style={styles.tileGrid}>
            {strategyTiles.map((tile) => (
              <View
                key={tile.label}
                style={[
                  styles.strategyTile,
                  {
                    backgroundColor: theme.bg3,
                    borderColor: theme.lineSoft,
                  },
                ]}
              >
                <Text style={[styles.tileValue, { color: theme.text, fontFamily: FONTS.monoSemiBold }]}>
                  {tile.value.toFixed(0)}
                </Text>
                <Text style={[styles.tileLabel, { color: theme.faint, fontFamily: FONTS.headingSemiBold }]}>
                  {tile.label}
                </Text>
              </View>
            ))}
          </View>
        </Panel>

        <Panel theme={theme} style={styles.panelTight}>
          <View style={styles.chartHeader}>
            <Kicker theme={theme}>Price · {rangeDays} days</Kicker>
            <View style={styles.rangeButtons}>
              {(Object.keys(CHART_RANGES) as ChartRange[]).map((label) => {
                const active = range === label;
                return (
                  <Pressable
                    key={label}
                    onPress={() => setRange(label)}
                    style={[
                      styles.rangeButton,
                      {
                        backgroundColor: active ? theme.primaryDim : "transparent",
                        borderColor: active ? theme.primaryLine : theme.lineSoft,
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.rangeButtonText,
                        {
                          color: active ? theme.text : theme.faint,
                          fontFamily: FONTS.headingSemiBold,
                        },
                      ]}
                    >
                      {label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </View>

          {candles.length > 0 ? (
            <CandlestickChart.Provider data={candles}>
              <CandlestickChart width={chartWidth} height={240} style={styles.chartCanvas}>
                <CandlestickChart.Candles
                  positiveColor={theme.green}
                  negativeColor={theme.red}
                  useAnimations={false}
                />
                <CandlestickChart.Crosshair color={theme.primary} />
              </CandlestickChart>
            </CandlestickChart.Provider>
          ) : (
            <View style={styles.noChartState}>
              <Text style={[styles.noChartText, { color: theme.quiet }]}>
                No chart data available for this range.
              </Text>
            </View>
          )}

          {priceSummary.latest ? (
            <View style={styles.ohlcRow}>
              {[
                { label: "O", value: priceSummary.latest.open },
                { label: "H", value: priceSummary.latest.high },
                { label: "L", value: priceSummary.latest.low },
                { label: "C", value: priceSummary.latest.close },
              ].map((entry) => (
                <View key={entry.label} style={styles.ohlcItem}>
                  <Text style={[styles.ohlcLabel, { color: theme.faint, fontFamily: FONTS.headingSemiBold }]}>
                    {entry.label}
                  </Text>
                  <Text style={[styles.ohlcValue, { color: theme.text, fontFamily: FONTS.monoMedium }]}>
                    {formatCurrency(entry.value, detail.market)}
                  </Text>
                </View>
              ))}
            </View>
          ) : null}
        </Panel>

        <Panel theme={theme}>
          <Kicker theme={theme}>Strategy breakdown</Kicker>

          <StrategyPipRow
            label="CANSLIM"
            value={`${countActive(canslimPips)}/${canslimPips.length}`}
            pips={canslimPips}
            theme={theme}
          />

          <StrategyPipRow
            label="Piotroski F-Score"
            value={`${detail.piotroski_detail?.f_score ?? 0}/9`}
            pips={piotroskiPips}
            theme={theme}
          />

          <StrategyPipRow
            label="Minervini Trend"
            value={`${detail.minervini_detail?.count_passing ?? 0}/8`}
            pips={minerviniPips}
            theme={theme}
          />

          <View
            style={[
              styles.stageCard,
              {
                backgroundColor: theme.bg3,
                borderColor: theme.lineSoft,
              },
            ]}
          >
            <View style={styles.stageHeader}>
              <Text style={[styles.strategyLabel, { color: theme.text, fontFamily: FONTS.headingSemiBold }]}>
                Weinstein Stage
              </Text>
              <View
                style={[
                  styles.stageBadge,
                  {
                    backgroundColor: stageTone.backgroundColor,
                    borderColor: stageTone.borderColor,
                  },
                ]}
              >
                <Text style={[styles.stageBadgeText, { color: stageTone.color, fontFamily: FONTS.headingSemiBold }]}>
                  {formatStageLabel(
                    detail.weinstein_detail?.stage,
                    detail.weinstein_detail?.sub_stage
                  )}
                </Text>
              </View>
            </View>
            <Text style={[styles.stageMeta, { color: theme.quiet }]}>
              MA slope {formatSigned(detail.weinstein_detail?.ma_slope ?? null, 2)} ·{" "}
              {formatSigned(detail.weinstein_detail?.price_vs_ma ?? null, 2)} vs MA
            </Text>
          </View>
        </Panel>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingState: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  errorTitle: {
    fontSize: 22,
    textAlign: "center",
  },
  errorCopy: {
    marginTop: 10,
    fontSize: 14,
    lineHeight: 21,
    textAlign: "center",
  },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  backButton: {
    width: 34,
    height: 34,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  marketMeta: {
    flex: 1,
    fontSize: 12,
  },
  pinButton: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 7,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  pinButtonText: {
    fontSize: 10,
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 32,
    gap: 12,
  },
  heroHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
  },
  heroText: {
    flex: 1,
    minWidth: 0,
  },
  tickerDisplay: {
    textTransform: "none",
  },
  instrumentName: {
    marginTop: 4,
    fontSize: 13,
    lineHeight: 19,
  },
  badgeRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 10,
  },
  sectorBadge: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  sectorText: {
    fontSize: 10,
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
  priceWrap: {
    alignItems: "flex-end",
    paddingTop: 6,
  },
  priceText: {
    fontSize: 22,
    lineHeight: 26,
  },
  changeText: {
    marginTop: 3,
    fontSize: 12,
  },
  changeValue: {
    marginTop: 2,
    fontSize: 11,
  },
  panelTight: {
    padding: 18,
  },
  panelHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 10,
  },
  passCount: {
    fontSize: 10,
  },
  scoreHero: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
    marginTop: 14,
  },
  scoreValue: {
    fontSize: 64,
    lineHeight: 64,
    letterSpacing: -2,
  },
  scoreSuffix: {
    fontSize: 14,
    marginBottom: 8,
  },
  scoreTrack: {
    height: 6,
    borderRadius: 999,
    overflow: "hidden",
    marginTop: 14,
  },
  scoreFill: {
    height: "100%",
    borderRadius: 999,
  },
  tileGrid: {
    marginTop: 14,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  strategyTile: {
    width: "48%",
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: 8,
    paddingHorizontal: 4,
    alignItems: "center",
  },
  tileValue: {
    fontSize: 14,
    lineHeight: 16,
  },
  tileLabel: {
    marginTop: 2,
    fontSize: 8,
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
  chartHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 8,
    marginBottom: 12,
  },
  rangeButtons: {
    flexDirection: "row",
    gap: 4,
  },
  rangeButton: {
    borderWidth: 1,
    borderRadius: 7,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  rangeButtonText: {
    fontSize: 10,
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  noChartState: {
    height: 220,
    alignItems: "center",
    justifyContent: "center",
  },
  chartCanvas: {
    height: 240,
    overflow: "hidden",
  },
  noChartText: {
    fontSize: 13,
  },
  ohlcRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
    marginTop: 16,
  },
  ohlcItem: {
    flex: 1,
    gap: 4,
  },
  ohlcLabel: {
    fontSize: 10,
    letterSpacing: 1.4,
  },
  ohlcValue: {
    fontSize: 11,
  },
  strategySection: {
    marginTop: 14,
  },
  strategyHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
  },
  strategyLabel: {
    fontSize: 13,
  },
  strategyValue: {
    fontSize: 10,
  },
  pipWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 4,
    marginTop: 8,
  },
  stageCard: {
    marginTop: 14,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
  },
  stageHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 10,
  },
  stageBadge: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  stageBadgeText: {
    fontSize: 10,
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
  stageMeta: {
    marginTop: 6,
    fontSize: 11,
    lineHeight: 17,
  },
});
