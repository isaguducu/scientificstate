import React, { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";

const DAEMON = "http://127.0.0.1:9473";

interface WorkspaceSummary {
  workspace_id: string;
  name: string;
  created_at: string;
}

export function Dashboard() {
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [newName, setNewName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function loadWorkspaces() {
    try {
      const resp = await fetch(`${DAEMON}/workspaces`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setWorkspaces(await resp.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadWorkspaces();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    const resp = await fetch(`${DAEMON}/workspaces`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName.trim() }),
    });
    if (resp.ok) {
      setNewName("");
      loadWorkspaces();
    }
  }

  return (
    <div style={{ padding: "24px", maxWidth: 800, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 16 }}>Workspaces</h2>

      <form onSubmit={handleCreate} style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="New workspace name…"
          style={{ flex: 1, padding: "6px 10px", borderRadius: 6, border: "1px solid #444", background: "#1c1c1e", color: "#fff" }}
        />
        <button
          type="submit"
          style={{ padding: "6px 16px", borderRadius: 6, background: "#00B7C7", border: "none", color: "#fff", cursor: "pointer" }}
        >
          Create
        </button>
      </form>

      {loading && <p style={{ color: "#888" }}>Loading…</p>}
      {error && <p style={{ color: "#ff453a" }}>Error: {error}</p>}

      {workspaces.length === 0 && !loading && (
        <p style={{ color: "#888" }}>No workspaces yet. Create one above.</p>
      )}

      {workspaces.map((ws) => (
        <div
          key={ws.workspace_id}
          style={{
            background: "#1c1c1e",
            border: "1px solid #2c2c2e",
            borderRadius: 10,
            padding: "14px 18px",
            marginBottom: 10,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ fontWeight: 600 }}>{ws.name}</div>
            <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>
              {new Date(ws.created_at).toLocaleString()}
            </div>
          </div>
          <button
            onClick={() =>
              navigate({
                to: "/compute/$runId",
                params: { runId: `new?ws=${ws.workspace_id}` },
              })
            }
            style={{ padding: "5px 14px", borderRadius: 6, background: "#0a84ff", border: "none", color: "#fff", cursor: "pointer" }}
          >
            Compute
          </button>
        </div>
      ))}
    </div>
  );
}
