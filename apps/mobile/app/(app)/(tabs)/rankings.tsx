import React, { useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { RankingItem, fetchMarketRegime, fetchRankings } from "@consensus/api-client";
import { SafeAreaView } from "react-native-safe-area-context";
import { getTheme, SPACING, FONTS } from "@/lib/theme";
import { Display, Kicker } from "@/components/ui/typography";
import { MarketToggle } from "@/components/ui/market-toggle";
import { RankingRow } from "@/components/ui/ranking-row";

type Market = "US" | "KR";

const FILTER_CHIPS = ["All", "Stocks", "ETFs", "Diamond+", "Pass 4+"];

function formatRegime(state?: string | null) {
  switch (state) {
    case "CONFIRMED_UPTREND":
      return "Confirmed uptrend";
    case "MARKET_IN_CORRECTION":
      return "In correction";
    case "UPTREND_UNDER_PRESSURE":
      return "Under pressure";
    default:
      return "Refreshing";
  }
}

function regimeColors(theme: ReturnType<typeof getTheme>, state?: string | null) {
  if (state === "CONFIRMED_UPTREND") {
    return {
      bg: "rgba(116,211,155,0.08)",
      border: "rgba(116,211,155,0.3)",
      dot: theme.green,
    };
  }

  if (state === "MARKET_IN_CORRECTION") {
    return {
      bg: "rgba(231,133,118,0.08)",
      border: "rgba(231,133,118,0.3)",
      dot: theme.red,
    };
  }

  return {
    bg: theme.bg3,
    border: theme.line,
    dot: theme.amber,
  };
}

export default function RankingsScreen() {
  const theme = getTheme("dark");
  const [market, setMarket] = useState<Market>("US");
  const router = useRouter();

  const rankingsQuery = useQuery({
    queryKey: ["rankings", market, "stock", 50],
    queryFn: () => fetchRankings({ market, asset_type: "stock", limit: 50 }),
    staleTime: 0,
    refetchOnMount: "always",
  });

  const regimeQuery = useQuery({
    queryKey: ["market-regime", market],
    queryFn: () => fetchMarketRegime(market),
    staleTime: 0,
    refetchOnMount: "always",
  });

  const regime = regimeQuery.data ?? null;
  const rankingData = rankingsQuery.data;
  const regimeTone = useMemo(
    () => regimeColors(theme, regime?.state ?? rankingData?.regime_state),
    [rankingData?.regime_state, regime?.state, theme]
  );

  const renderItem = ({ item }: { item: RankingItem }) => (
    <RankingRow
      item={item}
      theme={theme}
      density="rich"
      onPress={() => router.push(`/instrument/${item.market}/${item.ticker}`)}
    />
  );

  if (rankingsQuery.isLoading && !rankingData) {
    return (
      <SafeAreaView style={[styles.loadingWrap, { backgroundColor: theme.bg0 }]} edges={["top"]}>
        <ActivityIndicator color={theme.primary} size="large" />
      </SafeAreaView>
    );
  }

  if (rankingsQuery.isError) {
    return (
      <SafeAreaView style={[styles.loadingWrap, { backgroundColor: theme.bg0 }]} edges={["top"]}>
        <Text style={[styles.errorTitle, { color: theme.text, fontFamily: FONTS.headingBold }]}>
          Rankings unavailable
        </Text>
        <Text style={[styles.errorCopy, { color: theme.quiet }]}>
          We couldn’t load the current consensus board. Pull to retry once the API is reachable.
        </Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.bg0 }]} edges={["top"]}>
      <FlatList
        data={rankingData?.items ?? []}
        keyExtractor={(item) => `${item.market}-${item.ticker}`}
        renderItem={renderItem}
        contentContainerStyle={styles.content}
        ItemSeparatorComponent={() => <View style={{ height: 10 }} />}
        refreshControl={
          <RefreshControl
            refreshing={rankingsQuery.isRefetching}
            onRefresh={() => {
              rankingsQuery.refetch();
              regimeQuery.refetch();
            }}
            tintColor={theme.primary}
          />
        }
        ListHeaderComponent={
          <View>
            <View style={styles.header}>
              <View style={styles.headerText}>
                <Kicker theme={theme}>Consensus Rankings</Kicker>
                <Display theme={theme} style={styles.display}>
                  {market}
                  {"\n"}
                  RANKINGS
                </Display>
              </View>
              <MarketToggle market={market} onChange={setMarket} theme={theme} />
            </View>

            <Text style={[styles.meta, { color: theme.faint, fontFamily: FONTS.monoRegular }]}>
              {rankingData?.items.length ?? 0} instruments · snapshot {rankingData?.score_date ?? "--"}
            </Text>

            <View
              style={[
                styles.regimeBanner,
                {
                  backgroundColor: regimeTone.bg,
                  borderColor: regimeTone.border,
                },
              ]}
            >
              <View style={[styles.regimeDot, { backgroundColor: regimeTone.dot }]} />
              <View style={styles.regimeContent}>
                <Text style={[styles.regimeLabel, { color: theme.faint, fontFamily: FONTS.headingSemiBold }]}>
                  Market regime
                </Text>
                <Text style={[styles.regimeText, { color: theme.text, fontFamily: FONTS.headingSemiBold }]}>
                  {market} · {formatRegime(regime?.state ?? rankingData?.regime_state)}
                  {(rankingData?.regime_warning_count ?? 0) > 0
                    ? ` · ${rankingData?.regime_warning_count} warnings`
                    : ""}
                </Text>
              </View>
            </View>

            <View style={styles.chips}>
              {FILTER_CHIPS.map((chip, index) => {
                const active = index === 0;
                return (
                  <View
                    key={chip}
                    style={[
                      styles.chip,
                      {
                        backgroundColor: active ? theme.primaryDim : "transparent",
                        borderColor: active ? theme.primaryLine : theme.line,
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.chipText,
                        {
                          color: active ? theme.text : theme.faint,
                          fontFamily: FONTS.headingSemiBold,
                        },
                      ]}
                    >
                      {chip}
                    </Text>
                  </View>
                );
              })}
            </View>
          </View>
        }
        ListEmptyComponent={
          <View style={[styles.emptyState, { borderColor: theme.line, backgroundColor: theme.panel }]}>
            <Text style={[styles.emptyTitle, { color: theme.text, fontFamily: FONTS.headingBold }]}>
              No consensus scores yet
            </Text>
            <Text style={[styles.emptyCopy, { color: theme.quiet }]}>
              Pull to refresh after the mobile app reconnects to the API. The latest US and KR snapshots will appear here once the client can reach the backend.
            </Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingWrap: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  content: {
    paddingHorizontal: 16,
    paddingTop: 20,
    paddingBottom: 28,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    gap: 12,
  },
  headerText: {
    flex: 1,
  },
  display: {
    marginTop: 8,
  },
  meta: {
    marginTop: 10,
    fontSize: 11,
  },
  regimeBanner: {
    marginTop: 16,
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  regimeDot: {
    width: 8,
    height: 8,
    borderRadius: 999,
  },
  regimeContent: {
    flex: 1,
  },
  regimeLabel: {
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 1.8,
  },
  regimeText: {
    marginTop: 2,
    fontSize: 13,
  },
  chips: {
    flexDirection: "row",
    gap: 6,
    marginTop: 14,
    marginBottom: 14,
    flexWrap: "wrap",
  },
  chip: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  chipText: {
    fontSize: 11,
    letterSpacing: 1.2,
    textTransform: "uppercase",
  },
  emptyState: {
    borderWidth: 1,
    borderRadius: SPACING.radius,
    padding: 18,
  },
  emptyTitle: {
    fontSize: 18,
  },
  emptyCopy: {
    marginTop: 8,
    fontSize: 14,
    lineHeight: 21,
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
});
