import { useEffect } from "react";
import { View, ActivityIndicator } from "react-native";
import { Stack, useRouter, useSegments } from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import "../global.css";
import { useSession } from "../src/auth/useSession";
import { registerForPushNotifications } from "../src/notifications/registerForPushNotifications";
import { useAppStore } from "../src/store/useAppStore";

const queryClient = new QueryClient();

export default function RootLayout() {
  const { loading, signedIn } = useSession();
  const accessToken = useAppStore((s) => s.accessToken);
  const segments = useSegments();
  const router = useRouter();

  // The guard lives here rather than in each screen, so a new tab is protected by
  // existing rather than by remembering to add a check.
  useEffect(() => {
    if (loading) return; // still reading the stored session; redirecting now would bounce a signed-in user out
    const onSignIn = segments[0] === "sign-in";
    if (!signedIn && !onSignIn) router.replace("/sign-in");
    else if (signedIn && onSignIn) router.replace("/camera");
  }, [loading, signedIn, segments, router]);

  useEffect(() => {
    // Only meaningful once signed in: /devices/register needs a bearer token, and the
    // push row is keyed on the user it identifies. Before auth existed this ran at
    // startup and could only 401.
    if (!accessToken) return;
    registerForPushNotifications(accessToken).catch(() => {});
  }, [accessToken]);

  if (loading) {
    // Held until the persisted session has been read. Rendering the app first would
    // flash the sign-in screen at every returning user.
    return (
      <View className="flex-1 items-center justify-center bg-slate-50">
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <Stack screenOptions={{ headerShown: false }} />
    </QueryClientProvider>
  );
}
