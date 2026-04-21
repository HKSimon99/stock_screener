import React from "react";
import { Ionicons } from "@expo/vector-icons";
import { BottomTabBarProps } from "@react-navigation/bottom-tabs";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { getTheme, FONTS } from "@/lib/theme";

const TAB_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  rankings: "bar-chart-outline",
  search: "search-outline",
  strategies: "pulse-outline",
  me: "person-outline",
};

const TAB_LABELS: Record<string, string> = {
  rankings: "Rankings",
  search: "Search",
  strategies: "Strategies",
  me: "Me",
};

export function TabBar({ state, descriptors, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const theme = getTheme("dark");

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: "rgba(14,17,22,0.94)",
          borderTopColor: theme.line,
          paddingBottom: Math.max(insets.bottom, 18),
        },
      ]}
    >
      <View style={styles.row}>
        {state.routes.map((route, index) => {
          const isFocused = state.index === index;
          const { options } = descriptors[route.key];
          const label =
            typeof options.tabBarLabel === "string"
              ? options.tabBarLabel
              : TAB_LABELS[route.name] ?? route.name;

          const onPress = () => {
            const event = navigation.emit({
              type: "tabPress",
              target: route.key,
              canPreventDefault: true,
            });

            if (!isFocused && !event.defaultPrevented) {
              navigation.navigate(route.name, route.params);
            }
          };

          return (
            <Pressable key={route.key} style={styles.tab} onPress={onPress}>
              <Ionicons
                name={TAB_ICONS[route.name] ?? "ellipse-outline"}
                size={20}
                color={isFocused ? theme.primary : theme.faint}
              />
              <Text
                style={[
                  styles.label,
                  {
                    color: isFocused ? theme.primary : theme.faint,
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
  );
}

const styles = StyleSheet.create({
  container: {
    borderTopWidth: 1,
    paddingTop: 8,
    paddingHorizontal: 4,
  },
  row: {
    flexDirection: "row",
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    paddingVertical: 6,
  },
  label: {
    fontSize: 10,
  },
});
