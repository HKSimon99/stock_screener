import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { fetchInstrumentSearch, fetchRankings } from "@consensus/api-client";
import { getTheme } from "@/lib/theme";
import { ConvictionBadge } from "@/components/ui/conviction-badge";
import { Sparkline } from "@/components/ui/sparkline";
import { Display, Kicker } from "@/components/ui/typography";
import { getPinnedInstruments, type PinnedInstrument } from "@/lib/pinned";

type MarketFilter = "ALL" | "US" | "KR";
type AssetFilter = "ALL" | "stock" | "etf";

function getScopeLabel(market: MarketFilter, asset: AssetFilter) {
  return {
    marketAll: market === "ALL",
    marketUs: market === "US",
    marketKr: market === "KR",
    assetAll: asset === "ALL",
    assetStock: asset === "stock",
    assetEtf: asset === "etf",
  };
}

export default function SearchScreen() {
  const theme = getTheme("dark");
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [marketFilter, setMarketFilter] = useState<MarketFilter>("ALL");
  const [assetFilter, setAssetFilter] = useState<AssetFilter>("ALL");
  const [pinned, setPinned] = useState<PinnedInstrument[]>([]);

  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(timeout);
  }, [query]);

  useFocusEffect(
    React.useCallback(() => {
      setPinned(getPinnedInstruments());
    }, [])
  );

  const usTrendingQuery = useQuery({
    queryKey: ["search-trending", "US"],
    queryFn: () => fetchRankings({ market: "US", limit: 6 }),
  });

  const krTrendingQuery = useQuery({
    queryKey: ["search-trending", "KR"],
    queryFn: () => fetchRankings({ market: "KR", limit: 6 }),
  });

  const resultsQuery = useQuery({
    queryKey: ["instrument-search", debouncedQuery, marketFilter, assetFilter],
    enabled: debouncedQuery.length > 0,
    queryFn: () =>
      fetchInstrumentSearch({
        q: debouncedQuery,
        market: marketFilter === "ALL" ? undefined : marketFilter,
        asset_type: assetFilter === "ALL" ? undefined : assetFilter,
        limit: 24,
      }),
  });

  const convictionLookup = new Map(
    [...(usTrendingQuery.data?.items ?? []), ...(krTrendingQuery.data?.items ?? [])].map((item) => [
      `${item.market}-${item.ticker}`,
      item.conviction_level,
    ])
  );

  const trending = [...(usTrendingQuery.data?.items ?? []), ...(krTrendingQuery.data?.items ?? [])]
    .sort((left, right) => right.final_score - left.final_score)
    .slice(0, 6);

  const scope = getScopeLabel(marketFilter, assetFilter);
  const hasQuery = debouncedQuery.length > 0;

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.bg0 }]} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.inner} showsVerticalScrollIndicator={false}>
        <Kicker theme={theme}>Search</Kicker>
        <Display theme={theme} style={styles.title}>
          SEARCH
        </Display>
        <View
          style={[
            styles.searchBox,
            {
              backgroundColor: theme.bg2,
              borderColor: theme.line,
            },
          ]}
        >
          <Ionicons name="search-outline" size={16} color={theme.faint} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="AAPL, Samsung, semiconductors..."
            placeholderTextColor={theme.faint}
            style={[styles.input, { color: theme.text }]}
            autoCapitalize="none"
            autoCorrect={false}
          />
          {query.length > 0 ? (
            <Pressable onPress={() => setQuery("")}>
              <Ionicons name="close" size={16} color={theme.faint} />
            </Pressable>
          ) : null}
        </View>

        <View style={styles.chips}>
          {[
            { label: "All markets", active: scope.marketAll, onPress: () => setMarketFilter("ALL") },
            { label: "US", active: scope.marketUs, onPress: () => setMarketFilter("US") },
            { label: "KR", active: scope.marketKr, onPress: () => setMarketFilter("KR") },
            { label: "Stocks", active: scope.assetStock, onPress: () => setAssetFilter("stock") },
            { label: "ETFs", active: scope.assetEtf, onPress: () => setAssetFilter("etf") },
          ].map((chip) => (
            <Pressable
              key={chip.label}
              onPress={chip.onPress}
              style={[
                styles.chip,
                {
                  backgroundColor: chip.active ? theme.primaryDim : "transparent",
                  borderColor: chip.active ? theme.primaryLine : theme.line,
                },
              ]}
            >
              <Text
                style={[
                  styles.chipText,
                  { color: chip.active ? theme.text : theme.faint },
                ]}
              >
                {chip.label}
              </Text>
            </Pressable>
          ))}
        </View>

        {hasQuery ? (
          <View style={styles.section}>
            <Text style={[styles.sectionLabel, { color: theme.faint }]}>
              {resultsQuery.data?.total ?? 0} RESULTS
            </Text>
            {resultsQuery.isLoading ? (
              <View style={styles.loadingWrap}>
                <ActivityIndicator color={theme.primary} />
              </View>
            ) : null}
            {resultsQuery.data?.items.map((item) => {
              const conviction =
                convictionLookup.get(`${item.market}-${item.ticker}`) ?? "UNRANKED";
              return (
                <Pressable
                  key={`${item.market}-${item.ticker}`}
                  onPress={() => router.push(`/instrument/${item.market}/${item.ticker}`)}
                  style={[
                    styles.resultRow,
                    {
                      backgroundColor: theme.bg3,
                      borderColor: theme.lineSoft,
                    },
                  ]}
                >
                  <View style={styles.resultBody}>
                    <View style={styles.resultTickerRow}>
                      <Text style={[styles.resultTicker, { color: theme.text }]}>
                        {item.ticker}
                      </Text>
                      <Text style={[styles.resultExchange, { color: theme.faint }]}>
                        {item.exchange}
                      </Text>
                    </View>
                    <Text style={[styles.resultName, { color: theme.quiet }]} numberOfLines={1}>
                      {item.name_kr ?? item.name}
                    </Text>
                    <Text style={[styles.resultMeta, { color: theme.green }]}>
                      {item.coverage_state.replace(/_/g, " ")}
                    </Text>
                  </View>
                  <ConvictionBadge level={conviction} theme={theme} />
                </Pressable>
              );
            })}
            {resultsQuery.data && resultsQuery.data.items.length === 0 && !resultsQuery.isLoading ? (
              <View
                style={[
                  styles.emptyCard,
                  { backgroundColor: theme.panel, borderColor: theme.line },
                ]}
              >
                <Text style={[styles.emptyTitle, { color: theme.text }]}>No matches yet</Text>
                <Text style={[styles.emptyCopy, { color: theme.quiet }]}>
                  Try a ticker, company name, or switch the market and asset filters.
                </Text>
              </View>
            ) : null}
          </View>
        ) : (
          <>
            <View style={styles.section}>
              <Text style={[styles.sectionLabel, { color: theme.faint }]}>PINNED SYMBOLS</Text>
              <View style={styles.pinWrap}>
                {pinned.length > 0 ? (
                  pinned.map((item) => (
                    <Pressable
                      key={`${item.market}-${item.ticker}`}
                      onPress={() => router.push(`/instrument/${item.market}/${item.ticker}`)}
                      style={[
                        styles.pinChip,
                        {
                          backgroundColor: theme.bg3,
                          borderColor: theme.line,
                        },
                      ]}
                    >
                      <Text style={[styles.pinMarket, { color: theme.faint }]}>{item.market}</Text>
                      <Text style={[styles.pinTicker, { color: theme.text }]}>{item.ticker}</Text>
                    </Pressable>
                  ))
                ) : (
                  <Text style={[styles.emptyInline, { color: theme.quiet }]}>
                    Pin instruments from the detail screen to keep them here.
                  </Text>
                )}
              </View>
            </View>

            <View style={styles.section}>
              <Text style={[styles.sectionLabel, { color: theme.faint }]}>TRENDING TODAY</Text>
              {trending.map((item) => (
                <Pressable
                  key={`${item.market}-${item.ticker}`}
                  onPress={() => router.push(`/instrument/${item.market}/${item.ticker}`)}
                  style={[
                    styles.trendingRow,
                    {
                      backgroundColor: theme.bg3,
                      borderColor: theme.lineSoft,
                    },
                  ]}
                >
                  <View style={styles.trendingBody}>
                    <Text style={[styles.trendingTicker, { color: theme.text }]}>{item.ticker}</Text>
                    <Text style={[styles.trendingName, { color: theme.faint }]} numberOfLines={1}>
                      {item.name}
                    </Text>
                  </View>
                  <Sparkline
                    data={[
                      item.canslim_score,
                      item.piotroski_score * 10,
                      item.minervini_score * 10,
                      item.weinstein_score * 10,
                      item.final_score,
                    ]}
                    color={item.final_score >= 70 ? theme.green : theme.red}
                    width={48}
                    height={16}
                  />
                  <Text style={[styles.trendingScore, { color: theme.text }]}>
                    {item.final_score.toFixed(1)}
                  </Text>
                </Pressable>
              ))}
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  inner: { padding: 20, paddingBottom: 28 },
  title: { marginTop: 8 },
  searchBox: {
    marginTop: 16,
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  input: {
    flex: 1,
    fontSize: 15,
  },
  chips: {
    flexDirection: "row",
    gap: 6,
    flexWrap: "wrap",
    marginTop: 16,
  },
  chip: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 11,
    paddingVertical: 5,
  },
  chipText: {
    fontSize: 10,
    letterSpacing: 1.2,
    textTransform: "uppercase",
  },
  section: {
    marginTop: 24,
    gap: 10,
  },
  sectionLabel: {
    fontSize: 10,
    letterSpacing: 1.8,
    textTransform: "uppercase",
    fontWeight: "600",
  },
  pinWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  pinChip: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  pinMarket: {
    fontSize: 10,
    fontFamily: "JetBrainsMono_400Regular",
  },
  pinTicker: {
    fontSize: 12,
    fontFamily: "SpaceGrotesk_600SemiBold",
  },
  emptyInline: {
    fontSize: 13,
    lineHeight: 20,
  },
  trendingRow: {
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  trendingBody: {
    flex: 1,
    minWidth: 0,
  },
  trendingTicker: {
    fontSize: 14,
    fontFamily: "SpaceGrotesk_700Bold",
  },
  trendingName: {
    marginTop: 2,
    fontSize: 11,
  },
  trendingScore: {
    width: 42,
    textAlign: "right",
    fontSize: 12,
    fontFamily: "JetBrainsMono_600SemiBold",
  },
  loadingWrap: {
    paddingVertical: 20,
    alignItems: "center",
  },
  resultRow: {
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  resultBody: {
    flex: 1,
    minWidth: 0,
  },
  resultTickerRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 8,
  },
  resultTicker: {
    fontSize: 17,
    fontFamily: "SpaceGrotesk_700Bold",
  },
  resultExchange: {
    fontSize: 11,
    fontFamily: "JetBrainsMono_400Regular",
  },
  resultName: {
    marginTop: 3,
    fontSize: 12,
  },
  resultMeta: {
    marginTop: 4,
    fontSize: 9,
    textTransform: "uppercase",
    letterSpacing: 1.6,
    fontFamily: "SpaceGrotesk_600SemiBold",
  },
  emptyCard: {
    borderWidth: 1,
    borderRadius: 18,
    padding: 18,
  },
  emptyTitle: {
    fontSize: 18,
    fontFamily: "SpaceGrotesk_700Bold",
  },
  emptyCopy: {
    marginTop: 8,
    fontSize: 14,
    lineHeight: 21,
  },
});
