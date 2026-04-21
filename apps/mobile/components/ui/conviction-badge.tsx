import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { ConvictionLevel } from "@consensus/api-client";
import { AppTheme, FONTS } from "@/lib/theme";

export function ConvictionBadge({
  level,
  theme,
  size = "sm",
}: {
  level: ConvictionLevel;
  theme: AppTheme;
  size?: "sm" | "md";
}) {
  const colors = theme.conviction[level] ?? theme.conviction.UNRANKED;
  const metrics = size === "md" ? styles.md : styles.sm;

  return (
    <View
      style={[
        styles.base,
        metrics,
        {
          backgroundColor: colors.bg,
          borderColor: colors.line,
        },
      ]}
    >
      <View style={[styles.dot, { backgroundColor: colors.text }]} />
      <Text
        style={[
          styles.label,
          {
            color: colors.text,
            fontFamily: FONTS.headingSemiBold,
            fontSize: size === "md" ? 10 : 9,
            letterSpacing: size === "md" ? 1.8 : 1.6,
          },
        ]}
      >
        {level}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: 999,
    alignSelf: "flex-start",
  },
  sm: {
    gap: 5,
    paddingHorizontal: 7,
    paddingVertical: 3,
  },
  md: {
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  dot: {
    width: 5,
    height: 5,
    borderRadius: 999,
  },
  label: {
    textTransform: "uppercase",
  },
});

