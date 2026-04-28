import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "@tanstack/react-router";

const DAEMON = "http://127.0.0.1:9473";

const S = {
  page: { padding: "24px", maxWidth: 880, margin: "0 auto" } as React.CSSProperties,
  h2: { marginBottom: 20, fontSize: 20, fontWeight: 600 } as React.CSSProperties,
  card: {
    background: "#1c1c1e", border: "1px solid #2c2c2e",
    borderRadius: 10, padding: 18, marginBottom: 14,
  } as React.CSSProperties,
  cardTitle: { fontSize: 13, fontWeight: 600, color: "#00B7C7", marginBottom: 10 } as React.CSSProperties,
  sectionLabel: { fontSize: 11, color: "#888", fontWeight: 600, marginBottom: 4 } as React.CSSProperties,
  highlight: {
    background: "#002226", border: "1px solid #00B7C7",
    borderRadius: 7, padding: "10px 14px", marginBottom: 10,
  } as React.CSSProperties,
  highlightTitle: { fontSize: 12, color: "#00B7C7", fontWeight: 600, marginBottom: 4 } as React.CSSProperties,
  pre: {
    background: "#0d0d0f", borderRadius: 7,
    padding: 14, fontSize: 11, overflowX: "auto" as const,
    color: "#ccc", lineHeight: 1.6, border: "1px solid #2c2c2e",
  } as React.CSSProperties,
  accordion: {
    border: "1px solid #2c2c2e", borderRadius: 7,
    marginBottom: 6, overflow: "hidden",
  } as React.CSSProperties,
  accordionHeader: (open: boolean): React.CSSProperties => ({
    padding: "9px 14px", cursor: "pointer",
    background: open ? "#002226" : "#1c1c1e",
    display: "flex", alignItems: "center", justifyContent: "space-between",
    fontSize: 13, fontWeight: 600, userSelect: "none",
  }),
  accordionBody: {
    padding: "12px 14px", background: "#0d0d0f",
  } as React.CSSProperties,
  btn: {
    padding: "7px 16px", borderRadius: 6, border: "none",
    background: "#0a84ff", color: "#fff", fontSize: 12,
    cursor: "pointer", fontWeight: 600, marginRight: 8,
  } as React.CSSProperties,
  btnAccent: {
    padding: "7px 16px", borderRadius: 6, border: "none",
    background: "#00B7C7", color: "#fff", fontSize: 12,
    cursor: "pointer", fontWeight: 600, marginRight: 8,
  } as React.CSSProperties,
};

const SSV_SECTIONS: Array<{ key: string; label: string }> = [
  { key: "D", label: "D — Data" },
  { key: "I", label: "I — Instrument" },
  { key: "A", label: "A — Analysis" },
  { key: "T", label: "T — Transformation" },
  { key: "R", label: "R — Result" },
  { key: "U", label: "U — Uncertainty" },
  { key: "V", label: "V — Validity" },
  { key: "P", label: "P — Provenance" },
];

function AccordionSection({
  label,
  data,
}: {
  label: string;
  data: unknown;
}) {
  const [open, setOpen] = useState(false);
  if (data === undefined || data === null) return null;
  return (
    <div style={S.accordion}>
      <div style={S.accordionHeader(open)} onClick={() => setOpen((v) => !v)}>
        <span>{label}</span>
        <span style={{ color: "#888", fontSize: 11 }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={S.accordionBody}>
          <pre style={{ ...S.pre, margin: 0 }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

interface RunData {
  run_id: string;
  status: string;
  workspace_id?: string;
  result_json?: Record<string, unknown>;
}

export function EvidenceExplorer() {
  const { runId } = useParams({ from: "/evidence/$runId" });
  const navigate = useNavigate();
  const [run, setRun] = useState<RunData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${DAEMON}/runs/${runId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setRun)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) return <div style={{ padding: 24, color: "#888" }}>Loading evidence…</div>;
  if (error) return <div style={{ padding: 24, color: "#ff453a" }}>Error: {error}</div>;
  if (!run) return null;

  const rj = run.result_json ?? {};
  const uncertaintySummary = rj.uncertainty_summary ?? rj.U ?? null;
  const validityScope = rj.validity_scope ?? rj.V ?? null;

  return (
    <div style={S.page}>
      <h2 style={S.h2}>
        Evidence Explorer
        <span style={{ fontSize: 13, fontWeight: 400, color: "#888", marginLeft: 10 }}>
          Run {runId}
        </span>
      </h2>

      <div style={S.card}>
        <div style={S.cardTitle}>Run Summary</div>
        <div style={{ fontSize: 12, color: "#888" }}>
          Status: <span style={{ color: "#fff" }}>{run.status}</span>
          {run.workspace_id && (
            <span style={{ marginLeft: 16 }}>
              Workspace: <span style={{ color: "#fff" }}>{run.workspace_id}</span>
            </span>
          )}
        </div>
      </div>

      {/* Highlighted fields */}
      {uncertaintySummary && (
        <div style={S.highlight}>
          <div style={S.highlightTitle}>Uncertainty Summary</div>
          <pre style={{ ...S.pre, margin: 0 }}>
            {JSON.stringify(uncertaintySummary, null, 2)}
          </pre>
        </div>
      )}

      {validityScope && (
        <div style={{ ...S.highlight, borderColor: "#30d158", background: "#0d2b1a" }}>
          <div style={{ ...S.highlightTitle, color: "#30d158" }}>Validity Scope</div>
          <pre style={{ ...S.pre, margin: 0 }}>
            {JSON.stringify(validityScope, null, 2)}
          </pre>
        </div>
      )}

      {/* SSV accordion sections */}
      <div style={{ ...S.card, padding: 14 }}>
        <div style={S.cardTitle}>SSV Components</div>
        {SSV_SECTIONS.map(({ key, label }) => (
          <AccordionSection key={key} label={label} data={rj[key]} />
        ))}
      </div>

      {/* Full result JSON */}
      <div style={S.card}>
        <div style={S.cardTitle}>Full Result JSON</div>
        <pre style={S.pre}>{JSON.stringify(rj, null, 2)}</pre>
      </div>

      {/* Export buttons */}
      <div style={S.card}>
        <div style={S.cardTitle}>Export</div>
        <button style={S.btnAccent} onClick={() => window.open(`${DAEMON}/export/rocrate/${runId}`)}>
          RO-Crate
        </button>
        <button style={S.btn} onClick={() => window.open(`${DAEMON}/export/prov/${runId}`)}>
          W3C PROV
        </button>
        <button
          style={{ ...S.btn, background: "#5e5ce6" }}
          onClick={() => navigate({ to: "/export/$runId", params: { runId } })}
        >
          All Formats
        </button>
      </div>
    </div>
  );
}
