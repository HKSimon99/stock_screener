import React, { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { RankingItem, StrategyRankingItem } from "@consensus/api-client";
import { AppTheme, FONTS } from "@/lib/theme";
import { ConvictionBadge } from "@/components/ui/conviction-badge";
import { Sparkline } from "@/components/ui/sparkline";

type MobileRankingItem = RankingItem | StrategyRankingItem;

function buildScoreSparkline(item: MobileRankingItem): number[] {
  if ("final_score" in item) {
    return [
      item.canslim_score,
      item.piotroski_score * 10,
      item.minervini_score * 10,
      item.weinstein_score * 10,
      item.final_score,
    ];
  }

  const base = typeof item.score === "number" ? item.score : 50;
  return [base - 6, base - 2, base + 1, base + 3, base];
}

function getDisplayScore(item: MobileRankingItem): number {
  return "final_score" in item ? item.final_score : item.score ?? 0;
}

function getConviction(item: MobileRankingItem) {
  return "conviction_level" in item ? item.conviction_level : "UNRANKED";
}

export function RankingRow({
  item,
  theme,
  density = "rich",
  onPress,
}: {
  item: MobileRankingItem;
  theme: AppTheme;
  density?: "rich" | "compact";
  onPress: () => void;
}) {
  const conviction = getConviction(item);
  const convictionColors = theme.conviction[conviction] ?? theme.conviction.UNRANKED;
  const score = getDisplayScore(item);
  const sparkline = useMemo(() => buildScoreSparkline(item), [item]);
  const passes = "strategy_pass_count" in item ? item.strategy_pass_count : undefined;

  if (density === "compact") {
    return (
      <Pressable
        onPress={onPress}
        style={({ pressed }) => [
          styles.compactRow,
          {
            borderBottomColor: theme.lineSoft,
            opacity: pressed ? 0.92 : 1,
          },
        ]}
      >
        <Text style={[styles.compactRank, { color: theme.faint, fontFamily: FONTS.monoMedium }]}>
          #{String(item.rank).padStart(2, "0")}
        </Text>
        <View style={styles.compactBody}>
          <Text style={[styles.compactTicker, { color: theme.text, fontFamily: FONTS.headingBold }]}>
            {item.ticker}
          </Text>
          <Text style={[styles.compactName, { color: theme.quiet }]} numberOfLines={1}>
            {item.name}
          </Text>
        </View>
        <View style={[styles.compactEdge, { backgroundColor: convictionColors.text }]} />
        <Text style={[styles.compactScore, { color: theme.text, fontFamily: FONTS.monoSemiBold }]}>
          {score.toFixed(1)}
        </Text>
      </Pressable>
    );
  }

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.richCard,
        {
          backgroundColor: theme.panel,
          borderColor: theme.line,
          shadowColor: theme.shadow,
          opacity: pressed ? 0.95 : 1,
        },
      ]}
    >
      <View style={[styles.edgeBar, { backgroundColor: convictionColors.text }]} />
      <View style={styles.topRow}>
        <View style={styles.identity}>
          <View style={styles.rankLine}>
            <Text style={[styles.rankText, { color: theme.faint, fontFamily: FONTS.monoMedium }]}>
              #{String(item.rank).padStart(2, "0")}
            </Text>
            {"regime_warning" in item && item.regime_warning ? (
              <Text style={[styles.regimeFlag, { color: theme.amber, fontFamily: FONTS.headingSemiBold }]}>
                REGIME
              </Text>
            ) : null}
          </View>
          <Text style={[styles.ticker, { color: theme.text, fontFamily: FONTS.headingBold }]}>
            {item.ticker}
          </Text>
          <Text style={[styles.name, { color: theme.quiet }]} numberOfLines={1}>
            {item.name}
          </Text>
        </View>

        <Sparkline
          data={sparkline}
          color={score >= 70 ? theme.green : theme.red}
          width={60}
          height={22}
        />

        <View style={styles.scoreBlock}>
          <Text style={[styles.score, { color: theme.text, fontFamily: FONTS.monoSemiBold }]}>
            {score.toFixed(1)}
          </Text>
          <Text style={[styles.scoreLabel, { color: theme.faint, fontFamily: FONTS.headingSemiBold }]}>
            SCORE
          </Text>
        </View>
      </View>

      <View style={[styles.footer, { borderTopColor: theme.lineSoft }]}>
        <ConvictionBadge level={conviction} theme={theme} />
        {typeof passes === "number" ? (
          <View style={styles.passWrap}>
            <View style={styles.pips}>
              {[1, 2, 3, 4, 5].map((index) => (
                <View
                  key={index}
                  style={[
                    styles.pip,
                    {
                      backgroundColor: index <= passes ? theme.primary : theme.lineSoft,
                    },
                  ]}
                />
              ))}
            </View>
            <Text style={[styles.passText, { color: theme.faint, fontFamily: FONTS.monoMedium }]}>
              {passes}/5
            </Text>
          </View>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  richCard: {
    borderWidth: 1,
    borderRadius: 18,
    paddingVertical: 14,
    paddingHorizontal: 16,
    overflow: "hidden",
    shadowOffset: { width: 0, height: 18 },
    shadowOpacity: 0.18,
    shadowRadius: 24,
    elevation: 8,
  },
  edgeBar: {
    position: "absolute",
    left: 0,
    top: 12,
    bottom: 12,
    width: 3,
    borderTopRightRadius: 2,
    borderBottomRightRadius: 2,
  },
  topRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
  },
  identity: {
    flex: 1,
    minWidth: 0,
  },
  rankLine: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 2,
  },
  rankText: {
    fontSize: 10,
  },
  regimeFlag: {
    fontSize: 9,
    letterSpacing: 1.6,
    textTransform: "uppercase",
  },
  ticker: {
    fontSize: 20,
    lineHeight: 20,
  },
  name: {
    fontSize: 12,
    marginTop: 4,
  },
  scoreBlock: {
    alignItems: "flex-end",
    minWidth: 58,
  },
  score: {
    fontSize: 22,
    lineHeight: 24,
  },
  scoreLabel: {
    marginTop: 3,
    fontSize: 10,
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
  footer: {
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  passWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  pips: {
    flexDirection: "row",
    gap: 3,
  },
  pip: {
    width: 12,
    height: 3,
    borderRadius: 2,
  },
  passText: {
    fontSize: 10,
  },
  compactRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  compactRank: {
    width: 28,
    fontSize: 11,
    textAlign: "center",
  },
  compactBody: {
    flex: 1,
    minWidth: 0,
  },
  compactTicker: {
    fontSize: 15,
  },
  compactName: {
    fontSize: 11,
    marginTop: 2,
  },
  compactEdge: {
    width: 3,
    height: 20,
    borderRadius: 2,
  },
  compactScore: {
    minWidth: 44,
    textAlign: "right",
    fontSize: 14,
  },
});

