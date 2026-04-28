import React, { useEffect, useState } from "react";
import { useParams } from "@tanstack/react-router";

const DAEMON = "http://127.0.0.1:9473";

const S = {
  page: { padding: "24px", maxWidth: 720, margin: "0 auto" } as React.CSSProperties,
  h2: { marginBottom: 20, fontSize: 20, fontWeight: 600 } as React.CSSProperties,
  card: {
    background: "#1c1c1e", border: "1px solid #2c2c2e",
    borderRadius: 10, padding: 20, marginBottom: 16,
  } as React.CSSProperties,
  cardTitle: { fontSize: 13, fontWeight: 600, color: "#888", marginBottom: 12 } as React.CSSProperties,
  label: { display: "block", fontSize: 12, color: "#888", marginBottom: 4 } as React.CSSProperties,
  field: { marginBottom: 12 } as React.CSSProperties,
  input: {
    width: "100%", boxSizing: "border-box" as const,
    padding: "7px 10px", borderRadius: 6,
    border: "1px solid #2c2c2e", background: "#0d0d0f",
    color: "#fff", fontSize: 13,
  } as React.CSSProperties,
  btn: {
    padding: "7px 18px", borderRadius: 6, border: "none",
    background: "#00B7C7", color: "#fff", fontSize: 13,
    cursor: "pointer", fontWeight: 600,
  } as React.CSSProperties,
  btnDisabled: {
    padding: "7px 18px", borderRadius: 6, border: "none",
    background: "#2c2c2e", color: "#555", fontSize: 13,
    cursor: "not-allowed", fontWeight: 600,
  } as React.CSSProperties,
  error: { color: "#ff453a", fontSize: 12, marginTop: 8 } as React.CSSProperties,
  success: { color: "#30d158", fontSize: 12, marginTop: 8 } as React.CSSProperties,
  gatesRow: { display: "flex", gap: 8, flexWrap: "wrap" as const, marginBottom: 16 } as React.CSSProperties,
};

type GateValue = boolean | null;

const GATES: Array<{ key: string; label: string }> = [
  { key: "E1_evidence", label: "E1 Evidence" },
  { key: "U1_uncertainty", label: "U1 Uncertainty" },
  { key: "V1_validity", label: "V1 Validity" },
  { key: "C1_contradiction", label: "C1 Contradiction" },
  { key: "H1_human", label: "H1 Human" },
];

function gateBadgeStyle(val: GateValue): React.CSSProperties {
  if (val === true) return { background: "#0d2b1a", color: "#30d158", border: "1px solid #30d158" };
  if (val === false) return { background: "#2b0d0d", color: "#ff453a", border: "1px solid #ff453a" };
  return { background: "#1c1c1e", color: "#555", border: "1px solid #2c2c2e" };
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "#888",
  UNDER_REVIEW: "#ff9f0a",
  ENDORSED: "#30d158",
  REJECTED: "#ff453a",
};

interface ClaimData {
  claim_id: string;
  claim_json: Record<string, unknown>;
  endorsed_at?: string;
  endorsed_by?: string;
}

export function ClaimDetail() {
  const { claimId } = useParams({ from: "/claims/$claimId" });
  const [claim, setClaim] = useState<ClaimData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Endorse form
  const [researcherId, setResearcherId] = useState("");
  const [note, setNote] = useState("");
  const [endorsing, setEndorsing] = useState(false);
  const [endorseError, setEndorseError] = useState<string | null>(null);
  const [endorseSuccess, setEndorseSuccess] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch(`${DAEMON}/claims/${claimId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setClaim)
      .catch((e) => setLoadError(String(e)))
      .finally(() => setLoading(false));
  }, [claimId]);

  async function handleEndorse(e: React.FormEvent) {
    e.preventDefault();
    setEndorseError(null);
    setEndorseSuccess(null);
    setEndorsing(true);
    try {
      const resp = await fetch(`${DAEMON}/claims/${claimId}/endorse`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ researcher_id: researcherId, note }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setEndorseSuccess(`Endorsed at ${data.endorsed_at ?? new Date().toISOString()}`);
      setClaim((prev) =>
        prev
          ? {
              ...prev,
              endorsed_at: data.endorsed_at,
              endorsed_by: researcherId,
              claim_json: { ...prev.claim_json, epistemic_status: "ENDORSED" },
            }
          : prev
      );
    } catch (err) {
      setEndorseError(String(err));
    } finally {
      setEndorsing(false);
    }
  }

  if (loading) return <div style={{ padding: 24, color: "#888" }}>Loading claim…</div>;
  if (loadError) return <div style={{ padding: 24, color: "#ff453a" }}>Error: {loadError}</div>;
  if (!claim) return null;

  const cj = claim.claim_json;
  const claimText = (cj.text ?? cj.id ?? claimId) as string;
  const epistemicStatus = (cj.epistemic_status ?? "DRAFT") as string;
  const gates = (cj.gates ?? {}) as Record<string, GateValue>;
  const isEndorsed = !!claim.endorsed_at;

  return (
    <div style={S.page}>
      <h2 style={S.h2}>Claim Detail</h2>

      {/* Main claim card */}
      <div style={S.card}>
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, lineHeight: 1.5 }}>
          {claimText}
        </div>

        {/* Epistemic status badge */}
        <div style={{ marginBottom: 16 }}>
          <span
            style={{
              display: "inline-block", fontSize: 12, fontWeight: 700,
              padding: "4px 12px", borderRadius: 6,
              background: "#1c1c1e",
              color: STATUS_COLORS[epistemicStatus] ?? "#888",
              border: `1px solid ${STATUS_COLORS[epistemicStatus] ?? "#2c2c2e"}`,
            }}
          >
            {epistemicStatus}
          </span>
        </div>

        {/* Gate badges */}
        <div style={S.cardTitle}>Gate Durumlari</div>
        <div style={S.gatesRow}>
          {GATES.map(({ key, label }) => {
            const val = gates[key] ?? null;
            return (
              <span
                key={key}
                style={{
                  fontSize: 11, fontWeight: 600,
                  padding: "4px 10px", borderRadius: 5,
                  ...gateBadgeStyle(val as GateValue),
                }}
              >
                {label}
                {val === true ? " ✓" : val === false ? " ✗" : " —"}
              </span>
            );
          })}
        </div>

        {isEndorsed && (
          <div style={{ fontSize: 12, color: "#30d158", marginTop: 8 }}>
            Endorsed by <strong>{claim.endorsed_by}</strong> at {claim.endorsed_at}
          </div>
        )}
      </div>

      {/* Endorse card */}
      <div style={S.card}>
        <div style={S.cardTitle}>H1 Human Gate — Endorse</div>
        {isEndorsed ? (
          <div style={{ fontSize: 13, color: "#30d158" }}>
            This claim has already been endorsed.
          </div>
        ) : (
          <form onSubmit={handleEndorse}>
            <div style={S.field}>
              <label style={S.label}>Researcher ID</label>
              <input
                value={researcherId}
                onChange={(e) => setResearcherId(e.target.value)}
                placeholder="researcher@org"
                required
                style={S.input}
              />
            </div>
            <div style={S.field}>
              <label style={S.label}>Note (optional)</label>
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Endorse note…"
                style={S.input}
              />
            </div>
            <button
              type="submit"
              style={endorsing ? S.btnDisabled : S.btn}
              disabled={endorsing}
            >
              {endorsing ? "Endorsing…" : "Endorse"}
            </button>
            {endorseError && <div style={S.error}>{endorseError}</div>}
            {endorseSuccess && <div style={S.success}>{endorseSuccess}</div>}
          </form>
        )}
      </div>
    </div>
  );
}
