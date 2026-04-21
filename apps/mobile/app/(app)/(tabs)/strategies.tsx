import React, { useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { fetchStrategyRankings } from "@consensus/api-client";
import { getTheme } from "@/lib/theme";
import { MarketToggle } from "@/components/ui/market-toggle";
import { Panel } from "@/components/ui/panel";
import { RankingRow } from "@/components/ui/ranking-row";
import { Display, Kicker } from "@/components/ui/typography";

type StrategyKey = "canslim" | "piotroski" | "minervini";
type Market = "US" | "KR";

const STRATEGY_COPY: Record<StrategyKey, string> = {
  canslim:
    "William O'Neil's growth framework blending earnings, leadership, institutional demand, and market timing.",
  piotroski:
    "Joseph Piotroski's 9-factor fundamental score for balance-sheet quality, profitability, and efficiency.",
  minervini:
    "Mark Minervini's trend template for price leadership, moving-average alignment, and high-tight setups.",
};

export default function StrategiesScreen() {
  const theme = getTheme("dark");
  const router = useRouter();
  const [strategy, setStrategy] = useState<StrategyKey>("canslim");
  const [market, setMarket] = useState<Market>("US");
  const resolvedMarket = strategy === "canslim" ? "US" : market;

  const rankingsQuery = useQuery({
    queryKey: ["strategy-rankings", strategy, resolvedMarket],
    queryFn: () => fetchStrategyRankings(strategy, resolvedMarket),
  });

  const renderItem = ({
    item,
  }: {
    item: NonNullable<typeof rankingsQuery.data>["items"][number];
  }) => (
    <RankingRow
      item={item}
      theme={theme}
      onPress={() => router.push(`/instrument/${item.market}/${item.ticker}`)}
    />
  );

  if (rankingsQuery.isLoading && !rankingsQuery.data) {
    return (
      <SafeAreaView style={[styles.loadingWrap, { backgroundColor: theme.bg0 }]} edges={["top"]}>
        <ActivityIndicator color={theme.primary} size="large" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.bg0 }]} edges={["top"]}>
      <FlatList
        data={rankingsQuery.data?.items ?? []}
        keyExtractor={(item) => `${item.market}-${item.ticker}`}
        renderItem={renderItem}
        contentContainerStyle={styles.inner}
        ItemSeparatorComponent={() => <View style={{ height: 10 }} />}
        ListHeaderComponent={
          <View>
        <Kicker theme={theme}>Strategies</Kicker>
        <Display theme={theme} style={styles.title}>
          STRATEGY{"\n"}RANKINGS
        </Display>
            <Text style={[styles.copy, { color: theme.quiet }]}>
              Per-strategy ranks with the same conviction-forward card system as the main board.
            </Text>

            <View
              style={[
                styles.tabPillWrap,
                {
                  backgroundColor: theme.bg3,
                  borderColor: theme.line,
                },
              ]}
            >
              {(
                [
                  ["canslim", "CANSLIM"],
                  ["piotroski", "Piotroski"],
                  ["minervini", "Minervini"],
                ] as const
              ).map(([key, label]) => {
                const active = strategy === key;
                return (
                  <Pressable
                    key={key}
                    onPress={() => setStrategy(key)}
                    style={[
                      styles.tabPill,
                      {
                        backgroundColor: active ? theme.primaryDim : "transparent",
                        borderColor: active ? theme.primaryLine : "transparent",
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.tabPillText,
                        { color: active ? theme.text : theme.faint },
                      ]}
                    >
                      {label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>

            {strategy !== "canslim" ? (
              <View style={styles.marketToggleWrap}>
                <MarketToggle market={market} onChange={setMarket} theme={theme} />
              </View>
            ) : (
              <Text style={[styles.marketNote, { color: theme.faint }]}>
                CANSLIM remains a US-only growth strategy in this build.
              </Text>
            )}

            <Panel theme={theme} soft style={styles.explainerPanel}>
              <Kicker theme={theme}>{strategy.toUpperCase()} methodology</Kicker>
              <Text style={[styles.explainerCopy, { color: theme.quiet }]}>
                {STRATEGY_COPY[strategy]}
              </Text>
            </Panel>
          </View>
        }
        ListEmptyComponent={
          rankingsQuery.isError ? (
            <View
              style={[
                styles.emptyCard,
                { backgroundColor: theme.panel, borderColor: theme.line },
              ]}
            >
              <Text style={[styles.emptyTitle, { color: theme.text }]}>
                Strategy rankings unavailable
              </Text>
              <Text style={[styles.emptyCopy, { color: theme.quiet }]}>
                The API did not return a ranking set for this strategy and market yet.
              </Text>
            </View>
          ) : null
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  loadingWrap: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  inner: { padding: 20, paddingBottom: 28 },
  title: { marginTop: 8 },
  copy: { marginTop: 14, fontSize: 14, lineHeight: 21 },
  tabPillWrap: {
    marginTop: 20,
    borderWidth: 1,
    borderRadius: 999,
    padding: 3,
    flexDirection: "row",
    gap: 2,
  },
  tabPill: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 999,
    paddingVertical: 8,
    paddingHorizontal: 10,
    alignItems: "center",
  },
  tabPillText: {
    fontSize: 10,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    fontFamily: "SpaceGrotesk_600SemiBold",
  },
  marketToggleWrap: {
    marginTop: 16,
  },
  marketNote: {
    marginTop: 16,
    fontSize: 11,
    fontFamily: "JetBrainsMono_400Regular",
  },
  explainerPanel: {
    marginTop: 16,
  },
  explainerCopy: {
    marginTop: 8,
    fontSize: 12,
    lineHeight: 19,
  },
  emptyCard: {
    marginTop: 18,
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
