import { useEffect, useRef } from "react";
import * as Notifications from "expo-notifications";
import { useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";

import { useAppStore } from "../store/useAppStore";

// Owner: Person C — Battle System
// The receiving half of the push wiring. Person D registers the device token
// (registerForPushNotifications); this decides what happens when one of our
// notifications actually arrives.
//
// Both battle pushes carry {"type": "battle", "battle_id": ...} — see
// backend/app/services/push.py.

/** A push we sent, once its payload has been checked. */
function battleIdFrom(response: Notifications.NotificationResponse | null): string | null {
  // The payload crosses a process boundary and is typed `unknown` for good reason: it can
  // be anything, including a notification from a future build of the app. Anything that
  // isn't recognisably ours is ignored rather than navigated on.
  const data = response?.notification?.request?.content?.data as
    | { type?: unknown; battle_id?: unknown }
    | undefined;

  if (!data || data.type !== "battle" || typeof data.battle_id !== "string") return null;
  return data.battle_id;
}

/**
 * Foreground presentation. Without this, a notification that arrives while the app is
 * open is delivered silently — which is exactly when a battle result matters most,
 * because the other player is acting right now.
 *
 * Set at module scope rather than in the hook: it is global to the app, and setting it
 * from an effect would re-register it on every mount.
 */
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

/**
 * Opens the battle behind a tapped notification, and keeps the battle list fresh when one
 * arrives without being tapped.
 *
 * Mounted once, from the root layout.
 */
export function useBattleNotifications() {
  const queryClient = useQueryClient();
  const userId = useAppStore((s) => s.userId);

  // Covers the cold-start case: a tap on a notification while the app was killed
  // launches it, and the response is already waiting rather than arriving as an event.
  const lastResponse = Notifications.useLastNotificationResponse();
  const handledResponse = useRef<string | null>(null);

  useEffect(() => {
    const battleId = battleIdFrom(lastResponse ?? null);
    if (!battleId) return;

    // The hook keeps returning the same response, so without this guard the app would
    // re-navigate to the battle every time anything re-rendered — including after the
    // player had deliberately navigated away.
    const identifier = lastResponse?.notification?.request?.identifier ?? battleId;
    if (handledResponse.current === identifier) return;
    handledResponse.current = identifier;

    router.push(`/battles/${battleId}`);
  }, [lastResponse]);

  useEffect(() => {
    // A notification received while the app is open means something changed on the
    // server that this device did not do. Invalidating rather than navigating: the
    // player is in the middle of something, and yanking them to another screen because a
    // push landed would be hostile. The Battle tab polls too; this makes it immediate.
    const subscription = Notifications.addNotificationReceivedListener((notification) => {
      const data = notification.request.content.data as { type?: unknown } | undefined;
      if (data?.type !== "battle") return;
      queryClient.invalidateQueries({ queryKey: ["battles", userId] });
      queryClient.invalidateQueries({ queryKey: ["battle", userId] });
    });

    return () => subscription.remove();
  }, [queryClient, userId]);
}
