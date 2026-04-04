/**
 * ExploratoryBadge — visual indicator for exploratory quantum runs.
 *
 * Main_Source §9A.3: Quantum simulation runs are automatically exploratory.
 * Exploratory results cannot enter the endorsable claim path.
 *
 * Shows "Exploratory · Simulator" (or appropriate label) when the compute
 * class is not "classical".
 */

import React from "react";

interface ExploratoryBadgeProps {
  /** Compute class from execution_witness (e.g. "quantum_sim", "quantum_hw", "hybrid") */
  computeClass: string;
  /** Optional backend_id for more specific labelling */
  backendId?: string;
}

const LABELS: Record<string, string> = {
  quantum_sim: "Simulator",
  quantum_hw: "Hardware",
  hybrid: "Hybrid",
};

const badgeStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  background: "#332800",
  border: "1px solid #ff9f0a",
  color: "#ff9f0a",
  padding: "3px 10px",
  borderRadius: 999,
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: 0.3,
};

const dotStyle: React.CSSProperties = {
  width: 6,
  height: 6,
  borderRadius: "50%",
  background: "#ff9f0a",
};

export function ExploratoryBadge({ computeClass, backendId }: ExploratoryBadgeProps) {
  if (computeClass === "classical") return null;

  const subLabel = LABELS[computeClass] ?? computeClass;

  return (
    <span style={badgeStyle} title={`Exploratory run — ${subLabel}${backendId ? ` (${backendId})` : ""}`}>
      <span style={dotStyle} />
      Exploratory &middot; {subLabel}
    </span>
  );
}
