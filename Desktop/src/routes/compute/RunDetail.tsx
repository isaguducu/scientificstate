import React, { useEffect, useState } from "react";
import { useParams } from "@tanstack/react-router";
import { ComputeRunForm } from "../../features/compute/ComputeRunForm";

const DAEMON = "http://127.0.0.1:9473";

interface ComputeRunResult {
  run_id: string;
  workspace_id: string;
  domain_id: string;
  method_id: string;
  status: "pending" | "running" | "succeeded" | "failed";
  started_at: string;
  finished_at?: string;
  ssv_ref?: string;
  result?: Record<string, unknown>;
  error?: { error_code: string; message: string };
  execution_witness?: { compute_class: string; backend_id: string };
}

const statusColor: Record<string, string> = {
  pending: "#ff9f0a",
  running: "#0a84ff",
  succeeded: "#34c759",
  failed: "#ff453a",
};

export function RunDetail() {
  const { runId } = useParams({ from: "/compute/$runId" });

  // "new?ws=..." pattern from Dashboard's Compute button → show form
  const isNewForm = runId.startsWith("new");
  const workspaceId = isNewForm ? new URLSearchParams(runId.split("?")[1]).get("ws") ?? "" : "";

  const [run, setRun] = useState<ComputeRunResult | null>(null);
  const [loading, setLoading] = useState(!isNewForm);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isNewForm) return;
    fetch(`${DAEMON}/runs/${runId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setRun)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [runId, isNewForm]);

  if (isNewForm) {
    return (
      <div style={{ padding: "24px", maxWidth: 600, margin: "0 auto" }}>
        <h2 style={{ marginBottom: 16 }}>New Compute Run</h2>
        <ComputeRunForm workspaceId={workspaceId} />
      </div>
    );
  }

  if (loading) return <div style={{ padding: 24 }}>Loading run…</div>;
  if (error) return <div style={{ padding: 24, color: "#ff453a" }}>Error: {error}</div>;
  if (!run) return null;

  const color = statusColor[run.status] ?? "#888";

  return (
    <div style={{ padding: "24px", maxWidth: 800, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 4 }}>Run Detail</h2>
      <p style={{ color: "#888", fontSize: 12, marginBottom: 16 }}>{run.run_id}</p>

      <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
        <span
          style={{
            background: color,
            color: "#000",
            padding: "3px 10px",
            borderRadius: 999,
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          {run.status.toUpperCase()}
        </span>
        <span style={{ color: "#aaa", fontSize: 12, alignSelf: "center" }}>
          {run.domain_id} / {run.method_id}
        </span>
      </div>

      {run.ssv_ref && (
        <div style={{ background: "#1c1c1e", borderRadius: 8, padding: "10px 14px", marginBottom: 12 }}>
          <span style={{ fontSize: 12, color: "#aaa" }}>SSV ref: </span>
          <code style={{ fontSize: 12, color: "#34c759" }}>{run.ssv_ref}</code>
        </div>
      )}

      {run.status === "succeeded" && run.result && (
        <div>
          <h3 style={{ marginBottom: 8 }}>Result</h3>
          <pre
            style={{
              background: "#1c1c1e",
              border: "1px solid #2c2c2e",
              borderRadius: 8,
              padding: 14,
              fontSize: 11,
              overflow: "auto",
              maxHeight: 400,
              color: "#e0e0e0",
            }}
          >
            {JSON.stringify(run.result, null, 2)}
          </pre>
        </div>
      )}

      {run.status === "failed" && run.error && (
        <div style={{ background: "#2c1c1c", border: "1px solid #ff453a", borderRadius: 8, padding: 14 }}>
          <div style={{ color: "#ff453a", fontWeight: 600, marginBottom: 4 }}>
            {run.error.error_code}
          </div>
          <div style={{ color: "#e0e0e0", fontSize: 13 }}>{run.error.message}</div>
        </div>
      )}
    </div>
  );
}
