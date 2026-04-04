import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { useTranslation } from "react-i18next";
import { useRoute, useNavigation } from "@react-navigation/native";
import type { RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { fetchProfile, type ResearcherProfile as ProfileData } from "../services/api";
import { ClaimCard } from "../components/ClaimCard";
import { useOfflineCache } from "../hooks/useOfflineCache";
import type { RootStackParamList } from "../navigation/AppNavigator";

type RouteProps = RouteProp<RootStackParamList, "ResearcherProfile">;
type Nav = NativeStackNavigationProp<RootStackParamList>;

export function ResearcherProfile() {
  const { t } = useTranslation();
  const route = useRoute<RouteProps>();
  const nav = useNavigation<Nav>();
  const { orcid } = route.params;
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const { getCached, setCached } = useOfflineCache<ProfileData>(`profile:${orcid}`);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Try cache first
      const cached = await getCached();
      if (cached && !cancelled) {
        setProfile(cached);
        setLoading(false);
      }

      try {
        const data = await fetchProfile(orcid);
        if (!cancelled) {
          setProfile(data);
          await setCached(data);
        }
      } catch {
        // If network fails, use cache (already set above)
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [orcid]);

  if (loading && !profile) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#00ff88" />
      </View>
    );
  }

  if (!profile) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{t("common.error")}</Text>
      </View>
    );
  }

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={styles.content}
      data={profile.endorsed_claims}
      keyExtractor={(item) => item.claim_id}
      renderItem={({ item }) => (
        <ClaimCard
          claim={item}
          onPress={(id) => nav.navigate("ClaimDetail", { claimId: id })}
        />
      )}
      ListHeaderComponent={
        <View>
          <Text style={styles.name}>{profile.display_name}</Text>
          <Text style={styles.orcid}>ORCID: {profile.orcid}</Text>
          {profile.bio ? <Text style={styles.bio}>{profile.bio}</Text> : null}

          {profile.research_areas.length > 0 && (
            <View style={styles.areas}>
              {profile.research_areas.map((area) => (
                <View key={area} style={styles.areaBadge}>
                  <Text style={styles.areaText}>{area}</Text>
                </View>
              ))}
            </View>
          )}

          <View style={styles.statsRow}>
            <View style={styles.statBox}>
              <Text style={styles.statValue}>{profile.impact_stats.claim_count}</Text>
              <Text style={styles.statLabel}>{t("profile.endorsedClaims")}</Text>
            </View>
            <View style={styles.statBox}>
              <Text style={styles.statValue}>
                {profile.impact_stats.total_score.toFixed(1)}
              </Text>
              <Text style={styles.statLabel}>Impact Score</Text>
            </View>
          </View>

          <Text style={styles.sectionTitle}>{t("profile.endorsedClaims")}</Text>
        </View>
      }
      ListEmptyComponent={
        <Text style={styles.emptyText}>No endorsed claims yet.</Text>
      }
    />
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
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#0d0d1a",
  },
  errorText: {
    color: "#ff4444",
    fontSize: 16,
  },
  name: {
    color: "#ffffff",
    fontSize: 24,
    fontWeight: "700",
    marginBottom: 4,
  },
  orcid: {
    color: "#00ff88",
    fontSize: 13,
    marginBottom: 8,
  },
  bio: {
    color: "#ccc",
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 12,
  },
  areas: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginBottom: 16,
  },
  areaBadge: {
    backgroundColor: "#1a1a2e",
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: "#2a2a4a",
  },
  areaText: {
    color: "#ccc",
    fontSize: 12,
  },
  statsRow: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 20,
  },
  statBox: {
    flex: 1,
    backgroundColor: "#1a1a2e",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#2a2a4a",
  },
  statValue: {
    color: "#00ff88",
    fontSize: 22,
    fontWeight: "700",
  },
  statLabel: {
    color: "#888",
    fontSize: 11,
    marginTop: 4,
  },
  sectionTitle: {
    color: "#ffffff",
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 12,
  },
  emptyText: {
    color: "#666",
    fontSize: 13,
    fontStyle: "italic",
  },
});
