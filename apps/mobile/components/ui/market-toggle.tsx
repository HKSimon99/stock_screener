import React, { useEffect, useRef } from "react";
import {
  Animated,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { AppTheme, FONTS } from "@/lib/theme";

type Market = "US" | "KR";

export function MarketToggle({
  market,
  onChange,
  theme,
}: {
  market: Market;
  onChange: (market: Market) => void;
  theme: AppTheme;
}) {
  const animation = useRef(new Animated.Value(market === "US" ? 0 : 1)).current;

  useEffect(() => {
    Animated.spring(animation, {
      toValue: market === "US" ? 0 : 1,
      useNativeDriver: false,
      damping: 20,
      stiffness: 220,
      mass: 0.9,
    }).start();
  }, [animation, market]);

  const left = animation.interpolate({
    inputRange: [0, 1],
    outputRange: [3, 57],
  });

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: theme.bg3,
          borderColor: theme.line,
        },
      ]}
    >
      <Animated.View
        style={[
          styles.activePill,
          {
            left,
            backgroundColor: theme.primaryDim,
            borderColor: theme.primaryLine,
          },
        ]}
      />
      {(["US", "KR"] as const).map((value) => {
        const active = market === value;
        return (
          <Pressable
            key={value}
            onPress={() => onChange(value)}
            style={styles.button}
          >
            <Text
              style={[
                styles.label,
                {
                  color: active ? theme.text : theme.faint,
                  fontFamily: FONTS.headingSemiBold,
                },
              ]}
            >
              {value}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: 110,
    height: 36,
    borderRadius: 999,
    borderWidth: 1,
    flexDirection: "row",
    padding: 3,
    position: "relative",
  },
  activePill: {
    position: "absolute",
    top: 3,
    width: 50,
    height: 28,
    borderRadius: 999,
    borderWidth: 1,
  },
  button: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1,
  },
  label: {
    fontSize: 11,
    letterSpacing: 1.8,
    textTransform: "uppercase",
  },
});

