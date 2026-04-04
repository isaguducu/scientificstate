import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";
import { useTranslation } from "react-i18next";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { fetchCollections, type Collection } from "../services/api";
import { useOfflineCache } from "../hooks/useOfflineCache";
import type { RootStackParamList } from "../navigation/AppNavigator";

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function Collections() {
  const { t } = useTranslation();
  const nav = useNavigation<Nav>();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const { getCached, setCached } = useOfflineCache<Collection[]>("collections");

  const load = useCallback(async () => {
    setLoading(true);
    const cached = await getCached();
    if (cached) setCollections(cached);

    try {
      const data = await fetchCollections();
      setCollections(data.collections);
      await setCached(data.collections);
    } catch {
      // use cache
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <View style={styles.container}>
      <FlatList
        data={collections}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.card}
            onPress={() => {
              if (item.claim_ids.length > 0) {
                nav.navigate("ClaimDetail", { claimId: item.claim_ids[0] });
              }
            }}
          >
            <Text style={styles.title}>{item.title}</Text>
            <Text style={styles.desc} numberOfLines={2}>
              {item.description}
            </Text>
            <View style={styles.footer}>
              <Text style={styles.count}>
                {item.claim_ids.length} claim{item.claim_ids.length !== 1 ? "s" : ""}
              </Text>
              <Text style={styles.author}>{item.author_orcid}</Text>
            </View>
          </TouchableOpacity>
        )}
        onRefresh={load}
        refreshing={loading}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          loading ? (
            <View style={styles.center}>
              <ActivityIndicator size="large" color="#00ff88" />
            </View>
          ) : (
            <View style={styles.center}>
              <Text style={styles.emptyText}>No collections found.</Text>
            </View>
          )
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
  card: {
    backgroundColor: "#1a1a2e",
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#2a2a4a",
  },
  title: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 6,
  },
  desc: {
    color: "#999",
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 8,
  },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  count: {
    color: "#00ff88",
    fontSize: 12,
    fontWeight: "500",
  },
  author: {
    color: "#666",
    fontSize: 11,
  },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: 40,
  },
  emptyText: {
    color: "#666",
    fontSize: 14,
  },
});
