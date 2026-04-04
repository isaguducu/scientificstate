import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { useTranslation } from "react-i18next";
import type { CitationChain } from "../services/api";

interface CitationTreeProps {
  citations: CitationChain;
  onClaimPress: (claimId: string) => void;
}

const RELATIONSHIP_LABELS: Record<string, string> = {
  builds_upon: "Builds Upon",
  extends: "Extends",
  replicates: "Replicates",
  contradicts: "Contradicts",
};

export function CitationTree({ citations, onClaimPress }: CitationTreeProps) {
  const { t } = useTranslation();

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>{t("claim.citations")}</Text>

      {citations.cites.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Cites ({citations.cites_count})</Text>
          {citations.cites.map((c) => (
            <TouchableOpacity
              key={c.claim_id}
              style={styles.citationRow}
              onPress={() => onClaimPress(c.claim_id)}
            >
              <Text style={styles.relationship}>
                {RELATIONSHIP_LABELS[c.relationship] || c.relationship}
              </Text>
              <Text style={styles.claimId} numberOfLines={1}>
                {c.claim_id}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {citations.cited_by.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Cited By ({citations.cited_by_count})</Text>
          {citations.cited_by.map((c) => (
            <TouchableOpacity
              key={c.claim_id}
              style={styles.citationRow}
              onPress={() => onClaimPress(c.claim_id)}
            >
              <Text style={styles.relationship}>
                {RELATIONSHIP_LABELS[c.relationship] || c.relationship}
              </Text>
              <Text style={styles.claimId} numberOfLines={1}>
                {c.claim_id}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {citations.cites.length === 0 && citations.cited_by.length === 0 && (
        <Text style={styles.empty}>No citations yet.</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginTop: 16,
  },
  heading: {
    color: "#ffffff",
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 12,
  },
  section: {
    marginBottom: 12,
  },
  sectionLabel: {
    color: "#888",
    fontSize: 13,
    fontWeight: "500",
    marginBottom: 6,
  },
  citationRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: "#1a1a2e",
    borderRadius: 8,
    marginBottom: 4,
    borderWidth: 1,
    borderColor: "#2a2a4a",
  },
  relationship: {
    color: "#00ff88",
    fontSize: 12,
    fontWeight: "500",
    marginRight: 8,
    minWidth: 80,
  },
  claimId: {
    color: "#ccc",
    fontSize: 12,
    flex: 1,
  },
  empty: {
    color: "#666",
    fontSize: 13,
    fontStyle: "italic",
  },
});
