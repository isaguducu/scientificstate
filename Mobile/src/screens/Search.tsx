import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  FlatList,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { useTranslation } from "react-i18next";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { fetchEndorsedClaims, type EndorsedClaim } from "../services/api";
import { ClaimCard } from "../components/ClaimCard";
import type { RootStackParamList } from "../navigation/AppNavigator";

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function Search() {
  const { t } = useTranslation();
  const nav = useNavigation<Nav>();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<EndorsedClaim[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const doSearch = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      // Search by domain_id as a basic filter (portal API doesn't have full-text search yet)
      const data = await fetchEndorsedClaims({ domain_id: query.trim(), limit: 50 });
      setResults(data.claims);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [query]);

  return (
    <View style={styles.container}>
      <View style={styles.searchBar}>
        <TextInput
          style={styles.input}
          placeholder={t("discover.searchPlaceholder")}
          placeholderTextColor="#666"
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={doSearch}
          returnKeyType="search"
          autoCapitalize="none"
          autoCorrect={false}
        />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#00ff88" />
        </View>
      ) : (
        <FlatList
          data={results}
          keyExtractor={(item) => item.claim_id}
          renderItem={({ item }) => (
            <ClaimCard
              claim={item}
              onPress={(id) => nav.navigate("ClaimDetail", { claimId: id })}
            />
          )}
          contentContainerStyle={styles.list}
          ListEmptyComponent={
            searched ? (
              <View style={styles.center}>
                <Text style={styles.emptyText}>{t("discover.noResults")}</Text>
              </View>
            ) : null
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0d0d1a",
  },
  searchBar: {
    padding: 16,
    paddingBottom: 8,
  },
  input: {
    backgroundColor: "#1a1a2e",
    borderRadius: 10,
    paddingHorizontal: 16,
    paddingVertical: 12,
    color: "#ffffff",
    fontSize: 15,
    borderWidth: 1,
    borderColor: "#2a2a4a",
  },
  list: {
    padding: 16,
    paddingTop: 8,
    flexGrow: 1,
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
