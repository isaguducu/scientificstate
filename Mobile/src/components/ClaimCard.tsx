import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { useTranslation } from "react-i18next";
import type { EndorsedClaim } from "../services/api";
import { ImpactBadge } from "./ImpactBadge";

interface ClaimCardProps {
  claim: EndorsedClaim;
  impactScore?: number;
  onPress: (claimId: string) => void;
}

export function ClaimCard({ claim, impactScore, onPress }: ClaimCardProps) {
  const { t } = useTranslation();

  const passedGates = Object.values(claim.gate_status).filter(Boolean).length;
  const totalGates = Object.keys(claim.gate_status).length;

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={() => onPress(claim.claim_id)}
      activeOpacity={0.7}
    >
      <View style={styles.header}>
        <Text style={styles.title} numberOfLines={2}>
          {claim.title}
        </Text>
        {impactScore != null && <ImpactBadge score={impactScore} />}
      </View>

      <View style={styles.meta}>
        <Text style={styles.metaText}>
          {t("claim.domain")}: {claim.domain_id}
        </Text>
        <Text style={styles.metaText}>
          {t("claim.method")}: {claim.method_id}
        </Text>
      </View>

      <View style={styles.footer}>
        <Text style={styles.gates}>
          Gate: {passedGates}/{totalGates}
        </Text>
        <Text style={styles.orcid}>{claim.researcher_orcid}</Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#1a1a2e",
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#2a2a4a",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 8,
  },
  title: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "600",
    flex: 1,
    marginRight: 8,
  },
  meta: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 8,
  },
  metaText: {
    color: "#888",
    fontSize: 12,
  },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  gates: {
    color: "#00ff88",
    fontSize: 12,
    fontWeight: "500",
  },
  orcid: {
    color: "#666",
    fontSize: 11,
  },
});
