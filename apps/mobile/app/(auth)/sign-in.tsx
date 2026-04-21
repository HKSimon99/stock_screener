import React from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useSSO } from "@clerk/clerk-expo";
import { Ionicons } from "@expo/vector-icons";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { ConvictionBadge } from "@/components/ui/conviction-badge";
import { getTheme } from "@/lib/theme";
import { Kicker } from "@/components/ui/typography";

WebBrowser.maybeCompleteAuthSession();

export default function SignInScreen() {
  const { startSSOFlow } = useSSO();
  const theme = getTheme("dark");
  const [email, setEmail] = React.useState("");
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const onPressGoogle = React.useCallback(async () => {
    try {
      setErrorMessage(null);
      const redirectUrl = Linking.createURL("/");
      const { createdSessionId, setActive } = await startSSOFlow({
        strategy: "oauth_google",
        redirectUrl,
      });

      if (createdSessionId && setActive) {
        setActive({ session: createdSessionId });
      }
    } catch (err) {
      console.error("OAuth error", err);
      setErrorMessage("Google sign-in didn't complete. Please try again.");
    }
  }, [startSSOFlow]);

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.bg0 }]} edges={["top"]}>
      <View
        style={[
          styles.glow,
          styles.topGlow,
          { backgroundColor: theme.primaryDim },
        ]}
      />
      <View
        style={[
          styles.glow,
          styles.bottomGlow,
          { backgroundColor: "rgba(140,217,207,0.12)" },
        ]}
      />

      <View style={styles.logoRow}>
        <View style={[styles.logoMark, { backgroundColor: theme.primary }]}>
          <Text style={[styles.logoMarkText, { color: theme.bg0 }]}>C</Text>
        </View>
        <Text style={[styles.logoText, { color: theme.text }]}>CONSENSUS</Text>
      </View>

      <View style={styles.hero}>
        <Kicker theme={theme}>Signal over noise</Kicker>
        <Text style={[styles.heroText, { color: theme.text }]}>
          Four strategies.{"\n"}
          <Text style={[styles.heroAccent, { color: theme.primary }]}>One verdict.</Text>
        </Text>
        <Text style={[styles.heroCopy, { color: theme.quiet }]}>
          CANSLIM, Piotroski, Minervini and Weinstein, ranked together across US and Korean markets.
        </Text>

        <View style={styles.badgeRow}>
          {["DIAMOND", "PLATINUM", "GOLD", "SILVER", "BRONZE"].map((level) => (
            <ConvictionBadge
              key={level}
              level={level as "DIAMOND" | "PLATINUM" | "GOLD" | "SILVER" | "BRONZE"}
              theme={theme}
            />
          ))}
        </View>
      </View>

      <View style={styles.form}>
        <View
          style={[
            styles.emailShell,
            {
              backgroundColor: theme.bg2,
              borderColor: theme.line,
            },
          ]}
        >
          <Ionicons name="mail-outline" size={16} color={theme.faint} />
          <TextInput
            value={email}
            onChangeText={setEmail}
            placeholder="you@firm.com"
            placeholderTextColor={theme.faint}
            style={[styles.emailInput, { color: theme.text }]}
            keyboardType="email-address"
            autoCapitalize="none"
          />
        </View>

        <Pressable
          onPress={onPressGoogle}
          style={[
            styles.primaryButton,
            {
              backgroundColor: theme.primary,
            },
          ]}
        >
          <Text style={[styles.primaryButtonText, { color: theme.bg0 }]}>Continue</Text>
        </Pressable>

        <View style={styles.dividerRow}>
          <View style={[styles.dividerLine, { backgroundColor: theme.lineSoft }]} />
          <Text style={[styles.dividerText, { color: theme.faint }]}>OR</Text>
          <View style={[styles.dividerLine, { backgroundColor: theme.lineSoft }]} />
        </View>

        <View style={styles.ssoRow}>
          <Pressable
            style={[
              styles.secondaryButton,
              {
                borderColor: theme.line,
              },
            ]}
          >
            <Text style={[styles.secondaryButtonText, { color: theme.text }]}>Apple</Text>
          </Pressable>
          <Pressable
            onPress={onPressGoogle}
            style={[
              styles.secondaryButton,
              {
                borderColor: theme.line,
              },
            ]}
          >
            <Text style={[styles.secondaryButtonText, { color: theme.text }]}>Google</Text>
          </Pressable>
        </View>

        <Text style={[styles.helperCopy, { color: theme.faint }]}>
          Google SSO is the active auth path in this build.
        </Text>
        {errorMessage ? (
          <Text style={[styles.errorText, { color: theme.red }]}>{errorMessage}</Text>
        ) : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 40,
    paddingBottom: 32,
    position: "relative",
    overflow: "hidden",
  },
  glow: {
    position: "absolute",
    borderRadius: 999,
    opacity: 1,
  },
  topGlow: {
    top: -120,
    right: -80,
    width: 280,
    height: 280,
  },
  bottomGlow: {
    bottom: -80,
    left: -60,
    width: 220,
    height: 220,
  },
  logoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 28,
  },
  logoMark: {
    width: 32,
    height: 32,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  logoMarkText: {
    fontSize: 16,
    fontFamily: "SpaceGrotesk_700Bold",
  },
  logoText: {
    fontSize: 14,
    letterSpacing: 1.2,
    fontFamily: "SpaceGrotesk_600SemiBold",
  },
  hero: {
    flex: 1,
    justifyContent: "center",
  },
  heroText: {
    marginTop: 14,
    fontSize: 44,
    lineHeight: 46,
    fontFamily: "InstrumentSerif_400Regular",
  },
  heroAccent: {
    fontStyle: "italic",
  },
  heroCopy: {
    marginTop: 16,
    fontSize: 14,
    lineHeight: 21,
    maxWidth: 320,
  },
  badgeRow: {
    marginTop: 32,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  form: {
    gap: 10,
  },
  emailShell: {
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  emailInput: {
    flex: 1,
    fontSize: 15,
  },
  primaryButton: {
    borderRadius: 14,
    paddingVertical: 15,
    alignItems: "center",
  },
  primaryButtonText: {
    fontSize: 13,
    letterSpacing: 1.6,
    textTransform: "uppercase",
    fontFamily: "SpaceGrotesk_600SemiBold",
  },
  dividerRow: {
    marginTop: 4,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  dividerLine: {
    flex: 1,
    height: 1,
  },
  dividerText: {
    fontSize: 11,
    letterSpacing: 1.8,
    textTransform: "uppercase",
  },
  ssoRow: {
    flexDirection: "row",
    gap: 8,
  },
  secondaryButton: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 14,
    paddingVertical: 12,
    alignItems: "center",
  },
  secondaryButtonText: {
    fontSize: 13,
    fontFamily: "SpaceGrotesk_500Medium",
  },
  helperCopy: {
    marginTop: 4,
    fontSize: 11,
    lineHeight: 17,
    textAlign: "center",
  },
  errorText: {
    fontSize: 12,
    lineHeight: 18,
    textAlign: "center",
  },
});
