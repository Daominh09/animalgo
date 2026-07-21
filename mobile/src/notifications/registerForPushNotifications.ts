import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import Constants from "expo-constants";

import { apiFetch } from "../api/client";

// Owner: Person D — Economy, Shop & Shared Infra
// Week 1: request permission, grab the Expo push token, register it with the backend
// Week 2: use the stored token to push "your battle was resolved" notifications

export async function registerForPushNotifications(authToken?: string): Promise<string | null> {
  if (!Device.isDevice) {
    // Push tokens aren't available on simulators/emulators.
    return null;
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;
  if (existingStatus !== "granted") {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }
  if (finalStatus !== "granted") {
    return null;
  }

  const projectId = Constants.expoConfig?.extra?.eas?.projectId;
  const { data: pushToken } = await Notifications.getExpoPushTokenAsync(
    projectId ? { projectId } : undefined,
  );

  const params = new URLSearchParams({ push_token: pushToken });
  await apiFetch(`/devices/register?${params.toString()}`, { method: "POST" }, authToken);

  return pushToken;
}
