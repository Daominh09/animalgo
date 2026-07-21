import { useEffect } from "react";
import { Stack } from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import "../global.css";
import { registerForPushNotifications } from "../src/notifications/registerForPushNotifications";

const queryClient = new QueryClient();

export default function RootLayout() {
  useEffect(() => {
    // Week 1: best-effort registration with no auth token yet (device.register
    // requires a Bearer token, so this is a no-op 401 until real auth lands).
    // Week 2: call this after login succeeds, passing the Supabase session token.
    registerForPushNotifications().catch(() => {});
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <Stack screenOptions={{ headerShown: false }} />
    </QueryClientProvider>
  );
}
