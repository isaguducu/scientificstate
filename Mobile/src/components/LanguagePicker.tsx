import React from "react";
import { View, Text, StyleSheet, TouchableOpacity, FlatList } from "react-native";
import { useTranslation } from "react-i18next";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "tr", label: "Türkçe" },
  { code: "de", label: "Deutsch" },
  { code: "fr", label: "Français" },
  { code: "es", label: "Español" },
  { code: "zh", label: "中文" },
  { code: "ja", label: "日本語" },
] as const;

export function LanguagePicker() {
  const { i18n } = useTranslation();
  const current = i18n.language;

  return (
    <View style={styles.container}>
      <FlatList
        data={LANGUAGES}
        keyExtractor={(item) => item.code}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[styles.row, current === item.code && styles.rowActive]}
            onPress={() => i18n.changeLanguage(item.code)}
          >
            <Text style={[styles.label, current === item.code && styles.labelActive]}>
              {item.label}
            </Text>
            {current === item.code && <Text style={styles.check}>✓</Text>}
          </TouchableOpacity>
        )}
        scrollEnabled={false}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginVertical: 8,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#2a2a4a",
  },
  rowActive: {
    backgroundColor: "rgba(0, 255, 136, 0.08)",
  },
  label: {
    color: "#ccc",
    fontSize: 16,
  },
  labelActive: {
    color: "#00ff88",
    fontWeight: "600",
  },
  check: {
    color: "#00ff88",
    fontSize: 18,
  },
});
