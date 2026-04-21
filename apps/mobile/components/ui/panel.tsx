import React from "react";
import { StyleProp, StyleSheet, View, ViewStyle } from "react-native";
import { AppTheme, SPACING } from "@/lib/theme";

export function Panel({
  children,
  theme,
  soft = false,
  style,
}: {
  children: React.ReactNode;
  theme: AppTheme;
  soft?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View
      style={[
        styles.base,
        {
          backgroundColor: soft ? theme.bg3 : theme.panel,
          borderColor: soft ? theme.lineSoft : theme.line,
          shadowColor: theme.shadow,
        },
        style,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    borderWidth: 1,
    borderRadius: SPACING.radius,
    padding: SPACING.card,
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: 0.18,
    shadowRadius: 28,
    elevation: 8,
  },
});

