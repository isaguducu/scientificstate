import React from "react";
import { View, Text, FlatList, StyleSheet, ActivityIndicator } from "react-native";
import { useTranslation } from "react-i18next";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { ClaimCard } from "../components/ClaimCard";
import { useDiscoverFeed } from "../hooks/useDiscoverFeed";
import type { RootStackParamList } from "../navigation/AppNavigator";

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function DiscoverFeed() {
  const { t } = useTranslation();
  const nav = useNavigation<Nav>();
  const { claims, loading, error, refresh, loadMore } = useDiscoverFeed();

  if (loading && claims.length === 0) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#00ff88" />
        <Text style={styles.loadingText}>{t("common.loading")}</Text>
      </View>
    );
  }

  if (error && claims.length === 0) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{t("common.error")}</Text>
        <Text style={styles.retryText} onPress={refresh}>
          {t("common.retry")}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={claims}
        keyExtractor={(item) => item.claim_id}
        renderItem={({ item }) => (
          <ClaimCard
            claim={item}
            onPress={(id) => nav.navigate("ClaimDetail", { claimId: id })}
          />
        )}
        onRefresh={refresh}
        refreshing={loading}
        onEndReached={loadMore}
        onEndReachedThreshold={0.5}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.center}>
            <Text style={styles.emptyText}>{t("discover.emptyFeed")}</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0d0d1a",
  },
  list: {
    padding: 16,
    flexGrow: 1,
  },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#0d0d1a",
    padding: 24,
  },
  loadingText: {
    color: "#888",
    marginTop: 12,
    fontSize: 14,
  },
  errorText: {
    color: "#ff4444",
    fontSize: 16,
    marginBottom: 8,
  },
  retryText: {
    color: "#00ff88",
    fontSize: 14,
    fontWeight: "600",
  },
  emptyText: {
    color: "#666",
    fontSize: 14,
    textAlign: "center",
  },
});
