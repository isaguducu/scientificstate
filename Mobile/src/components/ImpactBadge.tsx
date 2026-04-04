import React from "react";
import { View, Text, StyleSheet } from "react-native";

interface ImpactBadgeProps {
  score: number;
}

function getColor(score: number): string {
  if (score >= 80) return "#00ff88";
  if (score >= 50) return "#ffaa00";
  if (score >= 20) return "#ff8800";
  return "#ff4444";
}

export function ImpactBadge({ score }: ImpactBadgeProps) {
  const color = getColor(score);

  return (
    <View style={[styles.badge, { borderColor: color }]}>
      <Text style={[styles.text, { color }]}>{score.toFixed(0)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderWidth: 1.5,
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 2,
    alignItems: "center",
    justifyContent: "center",
    minWidth: 36,
  },
  text: {
    fontSize: 13,
    fontWeight: "700",
  },
});
