import { useAuth } from "@clerk/clerk-expo";
import { Redirect, Stack } from "expo-router";
import BiometricGate from "../../components/BiometricGate";

export default function AppLayout() {
  const { isSignedIn, isLoaded } = useAuth();

  if (!isLoaded) {
    return null;
  }

  if (!isSignedIn) {
    return <Redirect href="/sign-in" />;
  }

  return (
    <BiometricGate>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen
          name="instrument/[market]/[ticker]"
          options={{
            animation: "slide_from_right",
          }}
        />
      </Stack>
    </BiometricGate>
  );
}
