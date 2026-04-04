import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { registerPushToken } from "./api";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

/**
 * Request push permission, get Expo push token, and register with backend.
 * Field-based notifications — the backend filters by domain/method, not person.
 */
export async function setupPushNotifications(authToken: string): Promise<string | null> {
  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== "granted") {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== "granted") {
    return null;
  }

  const tokenData = await Notifications.getExpoPushTokenAsync();
  const deviceToken = tokenData.data;
  const platform = Platform.OS === "ios" ? "ios" : "android";

  await registerPushToken(authToken, deviceToken, platform);

  return deviceToken;
}

/** Listen for notification taps and return the deep link URL if present. */
export function addNotificationResponseListener(
  callback: (url: string) => void,
): Notifications.Subscription {
  return Notifications.addNotificationResponseReceivedListener((response) => {
    const data = response.notification.request.content.data as
      | { url?: string }
      | undefined;
    if (data?.url) {
      callback(data.url);
    }
  });
}
