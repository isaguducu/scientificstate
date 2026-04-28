import React from "react";
import { useParams } from "@tanstack/react-router";

const DAEMON = "http://127.0.0.1:9473";

const S = {
  page: { padding: "24px", maxWidth: 760, margin: "0 auto" } as React.CSSProperties,
  h2: { marginBottom: 20, fontSize: 20, fontWeight: 600 } as React.CSSProperties,
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
    gap: 14, marginBottom: 20,
  } as React.CSSProperties,
  card: {
    background: "#1c1c1e", border: "1px solid #2c2c2e",
    borderRadius: 10, padding: "16px 18px",
    display: "flex", flexDirection: "column" as const, gap: 8,
  } as React.CSSProperties,
  formatLabel: { fontSize: 14, fontWeight: 600 } as React.CSSProperties,
  desc: { fontSize: 12, color: "#888", flex: 1 } as React.CSSProperties,
  btn: {
    alignSelf: "flex-start" as const,
    padding: "6px 16px", borderRadius: 6, border: "none",
    background: "#0a84ff", color: "#fff", fontSize: 12,
    cursor: "pointer", fontWeight: 600, marginTop: 4,
  } as React.CSSProperties,
  note: {
    background: "#1c1c1e", border: "1px solid #2c2c2e",
    borderRadius: 8, padding: "12px 16px",
    fontSize: 12, color: "#888", fontStyle: "italic",
  } as React.CSSProperties,
};

const FORMATS = [
  {
    label: "RO-Crate JSON-LD",
    endpoint: (runId: string) => `/export/rocrate/${runId}`,
    desc: "Research Object Crate v2 — standardised research package",
  },
  {
    label: "W3C PROV",
    endpoint: (runId: string) => `/export/prov/${runId}`,
    desc: "Provenance JSON — W3C PROV-O compliant activity graph",
  },
  {
    label: "OpenLineage",
    endpoint: (runId: string) => `/export/openlineage/${runId}`,
    desc: "Lineage event — OpenLineage 1.x job/run/dataset events",
  },
  {
    label: "CWL",
    endpoint: (runId: string) => `/export/cwl/${runId}`,
    desc: "Common Workflow Language — portable workflow description",
  },
  {
    label: "Parquet",
    endpoint: (runId: string) => `/export/parquet/${runId}`,
    desc: "Apache Parquet — columnar binary data format",
  },
  {
    label: "Zarr",
    endpoint: (runId: string) => `/export/zarr/${runId}`,
    desc: "Zarr — N-dimensional array archive (cloud-optimised)",
  },
];

export function ExportPanel() {
  const { runId } = useParams({ from: "/export/$runId" });

  return (
    <div style={S.page}>
      <h2 style={S.h2}>
        Export Panel
        <span style={{ fontSize: 13, fontWeight: 400, color: "#888", marginLeft: 10 }}>
          Run {runId}
        </span>
      </h2>

      <div style={S.grid}>
        {FORMATS.map(({ label, endpoint, desc }) => (
          <div key={label} style={S.card}>
            <div style={S.formatLabel}>{label}</div>
            <div style={S.desc}>{desc}</div>
            <button
              style={S.btn}
              onClick={() => window.open(DAEMON + endpoint(runId))}
            >
              Indir
            </button>
          </div>
        ))}
      </div>

      <div style={S.note}>
        P8 — Bu ekrandan indirilen dosyalar bir projeksiyon (projection) niteliğindedir.
        Yetkili kayıt, daemon'daki immutable ledger'da saklanmaktadir.
        Exported artefacts are snapshots; the authoritative record remains in the system ledger.
      </div>
    </div>
  );
}
