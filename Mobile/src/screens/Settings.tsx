import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Switch,
  Alert,
} from "react-native";
import { useTranslation } from "react-i18next";
import { LanguagePicker } from "../components/LanguagePicker";
import { signOut, getSession } from "../services/auth";
import { setupPushNotifications } from "../services/push";

export function Settings() {
  const { t } = useTranslation();
  const [pushEnabled, setPushEnabled] = useState(false);
  const [isSignedIn, setIsSignedIn] = useState(false);

  useEffect(() => {
    getSession().then((s) => setIsSignedIn(!!s));
  }, []);

  async function handleTogglePush(value: boolean) {
    setPushEnabled(value);
    if (value) {
      const session = await getSession();
      if (session) {
        const token = await setupPushNotifications(session.access_token);
        if (!token) {
          setPushEnabled(false);
          Alert.alert("Permission Required", "Push notifications permission was denied.");
        }
      }
    }
  }

  async function handleSignOut() {
    await signOut();
    setIsSignedIn(false);
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Language */}
      <Text style={styles.sectionTitle}>{t("settings.language")}</Text>
      <LanguagePicker />

      {/* Push Notifications */}
      <View style={styles.row}>
        <Text style={styles.rowLabel}>{t("settings.pushNotifications")}</Text>
        <Switch
          value={pushEnabled}
          onValueChange={handleTogglePush}
          trackColor={{ false: "#333", true: "#00ff88" }}
          thumbColor="#fff"
        />
      </View>
      <Text style={styles.hint}>{t("settings.pushHint")}</Text>

      {/* Sign Out */}
      {isSignedIn && (
        <TouchableOpacity style={styles.signOutButton} onPress={handleSignOut}>
          <Text style={styles.signOutText}>{t("auth.signOut")}</Text>
        </TouchableOpacity>
      )}

      <View style={styles.footer}>
        <Text style={styles.version}>ScientificState Mobile v0.1.0</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0d0d1a",
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  sectionTitle: {
    color: "#ffffff",
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 8,
    marginTop: 16,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: "#2a2a4a",
    marginTop: 16,
  },
  rowLabel: {
    color: "#ccc",
    fontSize: 16,
  },
  hint: {
    color: "#666",
    fontSize: 12,
    marginTop: 4,
  },
  signOutButton: {
    marginTop: 32,
    backgroundColor: "#1a1a2e",
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#ff4444",
  },
  signOutText: {
    color: "#ff4444",
    fontSize: 16,
    fontWeight: "600",
  },
  footer: {
    marginTop: 32,
    alignItems: "center",
  },
  version: {
    color: "#444",
    fontSize: 12,
  },
});
