import React from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { useTranslation } from "react-i18next";
import { useRoute, useNavigation } from "@react-navigation/native";
import type { RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { ImpactBadge } from "../components/ImpactBadge";
import { CitationTree } from "../components/CitationTree";
import { useClaimDetail } from "../hooks/useClaimDetail";
import type { RootStackParamList } from "../navigation/AppNavigator";

type RouteProps = RouteProp<RootStackParamList, "ClaimDetail">;
type Nav = NativeStackNavigationProp<RootStackParamList>;

/** SSV field labels — scientific terms stay in English per spec. */
const SSV_FIELDS = [
  { key: "d", label: "D (Data)" },
  { key: "i", label: "I (Instrument)" },
  { key: "a", label: "A (Assumption)" },
  { key: "t", label: "T (Transformation)" },
  { key: "r", label: "R (Result)" },
  { key: "u", label: "U (Uncertainty)" },
  { key: "v", label: "V (Validity)" },
  { key: "p", label: "P (Provenance)" },
] as const;

export function ClaimDetail() {
  const { t } = useTranslation();
  const route = useRoute<RouteProps>();
  const nav = useNavigation<Nav>();
  const { claimId } = route.params;
  const { claim, impact, citations, loading } = useClaimDetail(claimId);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#00ff88" />
      </View>
    );
  }

  if (!claim) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{t("common.error")}</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Title + Impact */}
      <View style={styles.header}>
        <Text style={styles.title}>{claim.title}</Text>
        {impact && <ImpactBadge score={impact.score} />}
      </View>

      {/* Meta */}
      <View style={styles.metaRow}>
        <Text style={styles.metaLabel}>{t("claim.domain")}:</Text>
        <Text style={styles.metaValue}>{claim.domain_id}</Text>
      </View>
      <View style={styles.metaRow}>
        <Text style={styles.metaLabel}>{t("claim.method")}:</Text>
        <Text style={styles.metaValue}>{claim.method_id}</Text>
      </View>
      <View style={styles.metaRow}>
        <Text style={styles.metaLabel}>ORCID:</Text>
        <Text style={styles.metaValue}>{claim.researcher_orcid}</Text>
      </View>

      {/* SSV 7-tuple (8 fields, lowercase) */}
      <Text style={styles.sectionTitle}>{t("claim.ssv")}</Text>
      <View style={styles.ssvGrid}>
        {SSV_FIELDS.map((f) => (
          <View key={f.key} style={styles.ssvCell}>
            <Text style={styles.ssvLabel}>{f.label}</Text>
            <Text style={styles.ssvValue}>
              {(claim as Record<string, unknown>)[f.key] != null
                ? String((claim as Record<string, unknown>)[f.key])
                : "—"}
            </Text>
          </View>
        ))}
      </View>

      {/* Gate Results */}
      <Text style={styles.sectionTitle}>{t("claim.gates")}</Text>
      <View style={styles.gateGrid}>
        {Object.entries(claim.gate_status).map(([gate, passed]) => (
          <View key={gate} style={styles.gateCell}>
            <Text style={[styles.gateIcon, passed ? styles.gatePass : styles.gateFail]}>
              {passed ? "✓" : "✗"}
            </Text>
            <Text style={styles.gateName}>{gate}</Text>
          </View>
        ))}
      </View>

      {/* Impact Breakdown */}
      {impact && (
        <>
          <Text style={styles.sectionTitle}>{t("claim.impactScore")}</Text>
          <View style={styles.impactGrid}>
            <ImpactRow label="Replication" value={impact.breakdown.replication_count} />
            <ImpactRow label="Citation" value={impact.breakdown.citation_count} />
            <ImpactRow label="Gate Completeness" value={impact.breakdown.gate_completeness} />
            <ImpactRow label="Institutional Diversity" value={impact.breakdown.institutional_diversity} />
          </View>
        </>
      )}

      {/* Citation Chain */}
      {citations && (
        <CitationTree
          citations={citations}
          onClaimPress={(id) => nav.push("ClaimDetail", { claimId: id })}
        />
      )}
    </ScrollView>
  );
}

function ImpactRow({ label, value }: { label: string; value: number }) {
  return (
    <View style={styles.impactRow}>
      <Text style={styles.impactLabel}>{label}</Text>
      <Text style={styles.impactValue}>{value}</Text>
    </View>
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
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  title: {
    color: "#ffffff",
    fontSize: 20,
    fontWeight: "700",
    flex: 1,
    marginRight: 12,
  },
  metaRow: {
    flexDirection: "row",
    marginBottom: 4,
  },
  metaLabel: {
    color: "#888",
    fontSize: 13,
    marginRight: 6,
  },
  metaValue: {
    color: "#ccc",
    fontSize: 13,
  },
  sectionTitle: {
    color: "#ffffff",
    fontSize: 18,
    fontWeight: "600",
    marginTop: 20,
    marginBottom: 12,
  },
  ssvGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  ssvCell: {
    width: "47%",
    backgroundColor: "#1a1a2e",
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: "#2a2a4a",
  },
  ssvLabel: {
    color: "#00ff88",
    fontSize: 11,
    fontWeight: "600",
    marginBottom: 4,
  },
  ssvValue: {
    color: "#ccc",
    fontSize: 13,
  },
  gateGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  gateCell: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1a1a2e",
    borderRadius: 8,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderWidth: 1,
    borderColor: "#2a2a4a",
  },
  gateIcon: {
    fontSize: 14,
    fontWeight: "700",
    marginRight: 6,
  },
  gatePass: {
    color: "#00ff88",
  },
  gateFail: {
    color: "#ff4444",
  },
  gateName: {
    color: "#ccc",
    fontSize: 12,
  },
  impactGrid: {
    backgroundColor: "#1a1a2e",
    borderRadius: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: "#2a2a4a",
  },
  impactRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
  },
  impactLabel: {
    color: "#888",
    fontSize: 13,
  },
  impactValue: {
    color: "#ffffff",
    fontSize: 13,
    fontWeight: "600",
  },
});
