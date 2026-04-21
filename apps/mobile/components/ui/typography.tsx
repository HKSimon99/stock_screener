import React from "react";
import { StyleProp, StyleSheet, Text, TextProps, TextStyle } from "react-native";
import { AppTheme, FONTS } from "@/lib/theme";

type ThemedTextProps = TextProps & {
  theme: AppTheme;
  style?: StyleProp<TextStyle>;
};

export function Kicker({ theme, style, children, ...props }: ThemedTextProps) {
  return (
    <Text
      {...props}
      style={[
        styles.kicker,
        {
          color: theme.faint,
          fontFamily: FONTS.headingSemiBold,
        },
        style,
      ]}
    >
      {children}
    </Text>
  );
}

export function Display({
  theme,
  style,
  children,
  ...props
}: ThemedTextProps & { size?: number }) {
  return (
    <Text
      {...props}
      style={[
        styles.display,
        {
          color: theme.text,
          fontFamily: FONTS.headingBold,
        },
        style,
      ]}
    >
      {children}
    </Text>
  );
}

const styles = StyleSheet.create({
  kicker: {
    fontSize: 10,
    letterSpacing: 2.2,
    textTransform: "uppercase",
  },
  display: {
    fontSize: 34,
    lineHeight: 34,
    letterSpacing: -1.2,
    textTransform: "uppercase",
  },
});

