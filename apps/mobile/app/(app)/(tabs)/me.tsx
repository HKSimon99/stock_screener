import React, { useMemo, useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuth, useUser } from "@clerk/clerk-expo";
import { useFocusEffect, useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, fetchRankings } from "@consensus/api-client";
import { getTheme } from "@/lib/theme";
import { ConvictionBadge } from "@/components/ui/conviction-badge";
import { Panel } from "@/components/ui/panel";
import { Display, Kicker } from "@/components/ui/typography";
import { getPinnedInstruments, type PinnedInstrument } from "@/lib/pinned";
import { registerForPushNotificationsAsync } from "@/lib/notifications";
import { storage } from "@/lib/storage";

const NOTIFICATIONS_ENABLED_KEY = "notifications-enabled";

function getInitials(value: string) {
  const parts = value.trim().split(/\s+/).filter(Boolean);
  return (parts[0]?.[0] ?? "C") + (parts[1]?.[0] ?? "");
}

export default function MeScreen() {
  const theme = getTheme("dark");
  const router = useRouter();
  const { user } = useUser();
  const { signOut, getToken } = useAuth();
  const [pinned, setPinned] = useState<PinnedInstrument[]>([]);
  const [notificationsEnabled, setNotificationsEnabled] = useState(
    storage.getBoolean(NOTIFICATIONS_ENABLED_KEY) ?? false
  );
  const [isSavingNotifications, setIsSavingNotifications] = useState(false);

  useFocusEffect(
    React.useCallback(() => {
      setPinned(getPinnedInstruments());
    }, [])
  );

  const usQuery = useQuery({
    queryKey: ["me-pinned-ranking", "US"],
    queryFn: () => fetchRankings({ market: "US", limit: 50 }),
  });
  const krQuery = useQuery({
    queryKey: ["me-pinned-ranking", "KR"],
    queryFn: () => fetchRankings({ market: "KR", limit: 50 }),
  });

  const convictionLookup = useMemo(
    () =>
      new Map(
        [...(usQuery.data?.items ?? []), ...(krQuery.data?.items ?? [])].map((item) => [
          `${item.market}-${item.ticker}`,
          item.conviction_level,
        ])
      ),
    [krQuery.data?.items, usQuery.data?.items]
  );

  const primaryIdentity =
    user?.fullName ?? user?.primaryEmailAddress?.emailAddress ?? "Consensus Member";
  const secondaryIdentity = user?.primaryEmailAddress?.emailAddress ?? "Signed in";

  async function handleNotificationsToggle(nextValue: boolean) {
    setNotificationsEnabled(nextValue);
    storage.set(NOTIFICATIONS_ENABLED_KEY, nextValue);

    if (!nextValue) {
      return;
    }

    try {
      setIsSavingNotifications(true);
      const expoToken = await registerForPushNotificationsAsync();
      if (!expoToken) {
        Alert.alert("Notifications unavailable", "Push registration requires a physical device and granted permission.");
        setNotificationsEnabled(false);
        storage.set(NOTIFICATIONS_ENABLED_KEY, false);
        return;
      }

      const bearerToken = await getToken();
      if (!bearerToken) {
        throw new Error("Missing auth token");
      }

      await apiFetch("/me/push-token", {
        method: "POST",
        bearerToken,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ token: expoToken }),
      });
    } catch (error) {
      setNotificationsEnabled(false);
      storage.set(NOTIFICATIONS_ENABLED_KEY, false);
      Alert.alert("Push registration failed", "We couldn't register this device for notifications right now.");
      console.error(error);
    } finally {
      setIsSavingNotifications(false);
    }
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.bg0 }]} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.inner} showsVerticalScrollIndicator={false}>
        <Kicker theme={theme}>Profile</Kicker>
        <Display theme={theme} style={styles.title}>
          ME
        </Display>
        <Text style={[styles.copy, { color: theme.quiet }]}>
          Your profile, pinned watchlist, and device alert controls now live together here.
        </Text>

        <Panel theme={theme} style={styles.profilePanel}>
          <View style={styles.profileRow}>
            <View style={[styles.avatar, { backgroundColor: theme.primaryDim, borderColor: theme.primaryLine }]}>
              <Text style={[styles.avatarText, { color: theme.primary }]}>{getInitials(primaryIdentity)}</Text>
            </View>
            <View style={styles.profileText}>
              <Text style={[styles.profileName, { color: theme.text }]}>{primaryIdentity}</Text>
              <Text style={[styles.profileEmail, { color: theme.quiet }]}>{secondaryIdentity}</Text>
            </View>
          </View>

          <Pressable
            onPress={() => signOut()}
            style={[
              styles.signOutButton,
              {
                backgroundColor: theme.bg3,
                borderColor: theme.line,
              },
            ]}
          >
            <Text style={[styles.signOutText, { color: theme.text }]}>Sign out</Text>
          </Pressable>
        </Panel>

        <Panel theme={theme} style={styles.sectionPanel}>
          <View style={styles.sectionHeader}>
            <Text style={[styles.sectionTitle, { color: theme.text }]}>Pinned Instruments</Text>
            <Text style={[styles.sectionMeta, { color: theme.faint }]}>{pinned.length} saved</Text>
          </View>

          {pinned.length > 0 ? (
            pinned.map((item) => (
              <Pressable
                key={`${item.market}-${item.ticker}`}
                onPress={() => router.push(`/instrument/${item.market}/${item.ticker}`)}
                style={[
                  styles.pinnedRow,
                  {
                    backgroundColor: theme.bg3,
                    borderColor: theme.lineSoft,
                  },
                ]}
              >
                <View style={styles.pinnedBody}>
                  <Text style={[styles.pinnedTicker, { color: theme.text }]}>{item.ticker}</Text>
                  <Text style={[styles.pinnedName, { color: theme.quiet }]} numberOfLines={1}>
                    {item.name_kr ?? item.name}
                  </Text>
                </View>
                <ConvictionBadge
                  level={convictionLookup.get(`${item.market}-${item.ticker}`) ?? "UNRANKED"}
                  theme={theme}
                />
              </Pressable>
            ))
          ) : (
            <Text style={[styles.emptyCopy, { color: theme.quiet }]}>
              Pin instruments from the detail view to build your mobile watchlist.
            </Text>
          )}
        </Panel>

        <Panel theme={theme} style={styles.sectionPanel}>
          <View style={styles.notificationsRow}>
            <View style={styles.notificationsText}>
              <Text style={[styles.sectionTitle, { color: theme.text }]}>Notifications</Text>
              <Text style={[styles.notificationCopy, { color: theme.quiet }]}>
                Register this device for conviction-upgrade alerts.
              </Text>
            </View>
            <Switch
              value={notificationsEnabled}
              onValueChange={handleNotificationsToggle}
              disabled={isSavingNotifications}
              thumbColor={notificationsEnabled ? theme.primary : "#f4f2ec"}
              trackColor={{ false: theme.lineSoft, true: theme.primaryLine }}
            />
          </View>
        </Panel>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  inner: { padding: 20, paddingBottom: 28 },
  title: { marginTop: 8 },
  copy: { marginTop: 14, fontSize: 14, lineHeight: 21 },
  profilePanel: {
    marginTop: 20,
  },
  profileRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 999,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: {
    fontSize: 18,
    fontFamily: "JetBrainsMono_600SemiBold",
  },
  profileText: {
    flex: 1,
    minWidth: 0,
  },
  profileName: {
    fontSize: 18,
    fontFamily: "SpaceGrotesk_700Bold",
  },
  profileEmail: {
    marginTop: 4,
    fontSize: 13,
  },
  signOutButton: {
    marginTop: 16,
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
  },
  signOutText: {
    fontSize: 12,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    fontFamily: "SpaceGrotesk_600SemiBold",
  },
  sectionPanel: {
    marginTop: 16,
  },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 16,
    fontFamily: "SpaceGrotesk_700Bold",
  },
  sectionMeta: {
    fontSize: 11,
    fontFamily: "JetBrainsMono_400Regular",
  },
  pinnedRow: {
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginTop: 8,
  },
  pinnedBody: {
    flex: 1,
    minWidth: 0,
  },
  pinnedTicker: {
    fontSize: 15,
    fontFamily: "SpaceGrotesk_700Bold",
  },
  pinnedName: {
    marginTop: 3,
    fontSize: 12,
  },
  emptyCopy: {
    fontSize: 13,
    lineHeight: 20,
  },
  notificationsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  notificationsText: {
    flex: 1,
  },
  notificationCopy: {
    marginTop: 4,
    fontSize: 13,
    lineHeight: 20,
  },
});
