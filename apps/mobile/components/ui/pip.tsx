import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { AppTheme, FONTS } from "@/lib/theme";

export function Pip({
  active,
  label,
  theme,
}: {
  active: boolean;
  label: string;
  theme: AppTheme;
}) {
  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: active ? "rgba(116,211,155,0.14)" : "transparent",
          borderColor: active ? "rgba(116,211,155,0.4)" : theme.line,
        },
      ]}
    >
      <Text
        style={[
          styles.text,
          {
            color: active ? theme.green : theme.faint,
            fontFamily: FONTS.monoMedium,
          },
        ]}
      >
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    minWidth: 24,
    height: 20,
    paddingHorizontal: 6,
    borderRadius: 6,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  text: {
    fontSize: 9,
    lineHeight: 10,
  },
});

