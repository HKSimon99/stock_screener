import "../global.css";
import { ClerkProvider, ClerkLoaded } from "@clerk/clerk-expo";
import { Slot } from "expo-router";
import { tokenCache } from "../lib/tokenCache";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { queryClient, asyncStoragePersister } from "../lib/queryClient";
import { configureApiClient } from "@consensus/api-client";
import * as SplashScreen from "expo-splash-screen";
import Constants from "expo-constants";
import * as Device from "expo-device";
import { useEffect } from "react";
import { Platform, useColorScheme } from "react-native";
import { useFonts as useSpaceGroteskFonts, SpaceGrotesk_500Medium, SpaceGrotesk_600SemiBold, SpaceGrotesk_700Bold } from "@expo-google-fonts/space-grotesk";
import { useFonts as useJetBrainsMonoFonts, JetBrainsMono_400Regular, JetBrainsMono_500Medium, JetBrainsMono_600SemiBold } from "@expo-google-fonts/jetbrains-mono";
import { useFonts as useInstrumentSerifFonts, InstrumentSerif_400Regular } from "@expo-google-fonts/instrument-serif";
import * as SystemUI from "expo-system-ui";
import { getTheme } from "@/lib/theme";

SplashScreen.preventAutoHideAsync().catch(() => {
  // Already prevented in dev fast refresh.
});

const publishableKey = process.env.EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY!;

if (!publishableKey) {
  throw new Error("Missing EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY in .env");
}

function extractHost(candidate?: string | null) {
  if (!candidate) {
    return null;
  }

  try {
    const normalized = candidate.includes("://") ? candidate : `http://${candidate}`;
    return new URL(normalized).hostname;
  } catch {
    return null;
  }
}

function resolveApiBaseUrl() {
  const envBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();
  const envHost = extractHost(envBaseUrl);
  const devHost =
    extractHost(Constants.expoConfig?.hostUri) ??
    extractHost(Constants.platform?.hostUri) ??
    extractHost(Constants.linkingUri);

  // `10.0.2.2` only works on the Android emulator. For Expo Go, iOS simulator,
  // and physical devices, prefer the packager host so the app can reach the API.
  if (envBaseUrl && envHost !== "10.0.2.2") {
    return envBaseUrl;
  }

  if (envHost === "10.0.2.2" && Platform.OS === "android" && !Device.isDevice) {
    return envBaseUrl!;
  }

  if (devHost) {
    return `http://${devHost}:8000/api/v1`;
  }

  return envBaseUrl || "http://localhost:8000/api/v1";
}

export default function RootLayout() {
  const colorScheme = useColorScheme();
  const theme = getTheme(colorScheme === "light" ? "light" : "dark");
  const resolvedApiBaseUrl = resolveApiBaseUrl();
  const [spaceLoaded] = useSpaceGroteskFonts({
    SpaceGrotesk_500Medium,
    SpaceGrotesk_600SemiBold,
    SpaceGrotesk_700Bold,
  });
  const [monoLoaded] = useJetBrainsMonoFonts({
    JetBrainsMono_400Regular,
    JetBrainsMono_500Medium,
    JetBrainsMono_600SemiBold,
  });
  const [serifLoaded] = useInstrumentSerifFonts({
    InstrumentSerif_400Regular,
  });

  const fontsLoaded = spaceLoaded && monoLoaded && serifLoaded;

  configureApiClient({
    baseUrl: resolvedApiBaseUrl,
  });

  useEffect(() => {
    SystemUI.setBackgroundColorAsync(theme.bg0).catch(() => {
      // Ignore unsupported platforms.
    });
  }, [theme.bg0]);

  useEffect(() => {
    if (fontsLoaded) {
      SplashScreen.hideAsync().catch(() => {
        // Ignore splash hide errors during hot reload.
      });
    }
  }, [fontsLoaded]);

  if (!fontsLoaded) {
    return null;
  }

  return (
    <ClerkProvider publishableKey={publishableKey} tokenCache={tokenCache}>
      <PersistQueryClientProvider
        client={queryClient}
        persistOptions={{
          persister: asyncStoragePersister,
          buster: resolvedApiBaseUrl,
        }}
      >
        <ClerkLoaded>
          <Slot />
        </ClerkLoaded>
      </PersistQueryClientProvider>
    </ClerkProvider>
  );
}
