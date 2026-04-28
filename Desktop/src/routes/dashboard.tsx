import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { tauriInvoke } from "../App";

const DAEMON = "http://127.0.0.1:9473";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface WorkspaceSummary {
  workspace_id: string;
  name: string;
  created_at: string;
}

interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds: number;
  active_runs: number;
  loaded_domains: string[];
}

interface DomainSummary {
  domain_id: string;
  domain_name: string;
  supported_data_types: string[];
  method_count: number;
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
export function Dashboard() {
  const navigate = useNavigate();

  // workspaces
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [newName, setNewName] = useState("");
  const [wsLoading, setWsLoading] = useState(true);
  const [wsError, setWsError] = useState<string | null>(null);

  // daemon status
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [domains, setDomains] = useState<DomainSummary[]>([]);
  const [daemonState, setDaemonState] = useState<"connecting" | "online" | "offline">("connecting");
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  // ── workspace helpers ────────────────────────────────────────────────────
  const loadWorkspaces = useCallback(async () => {
    try {
      const resp = await fetch(`${DAEMON}/workspaces`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setWorkspaces(await resp.json());
      setWsError(null);
    } catch (e) {
      setWsError(String(e));
    } finally {
      setWsLoading(false);
    }
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

  // ── daemon polling ───────────────────────────────────────────────────────
  const pollDaemon = useCallback(async () => {
    try {
      const h = await tauriInvoke<HealthResponse>("get_daemon_health");
      setHealth(h);
      setDaemonState("online");
    } catch {
      setDaemonState("offline");
      setHealth(null);
    }
    setLastChecked(new Date());
  }, []);

  const pollDomains = useCallback(async () => {
    try {
      const d = await tauriInvoke<DomainSummary[]>("get_domains");
      setDomains(Array.isArray(d) ? d : []);
    } catch {
      setDomains([]);
    }
  }, []);

  useEffect(() => {
    loadWorkspaces();
    pollDaemon();
    pollDomains();
    const t = setInterval(() => { pollDaemon(); pollDomains(); }, 5000);
    return () => clearInterval(t);
  }, [loadWorkspaces, pollDaemon, pollDomains]);

  // ── render ───────────────────────────────────────────────────────────────
  return (
    <div style={s.page}>

      {/* ── LEFT: workspaces ─────────────────────────────────────────── */}
      <div style={s.left}>
        <div style={s.sectionHeader}>
          <h2 style={s.sectionTitle}>Workspaces</h2>
          <span style={s.sectionCount}>{workspaces.length}</span>
        </div>

        <form onSubmit={handleCreate} style={s.createForm}>
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="New workspace name…"
            style={s.input}
          />
          <button type="submit" style={s.createBtn}>Create</button>
        </form>

        {wsLoading && <p style={s.muted}>Loading…</p>}
        {wsError && <p style={s.error}>Error: {wsError}</p>}

        {!wsLoading && workspaces.length === 0 && (
          <div style={s.emptyState}>
            <div style={s.emptyIcon}>🔬</div>
            <p style={s.emptyTitle}>No workspaces yet</p>
            <p style={s.muted}>Create your first workspace to start a scientific inquiry.</p>
          </div>
        )}

        <div style={s.wsList}>
          {workspaces.map((ws) => (
            <WorkspaceCard
              key={ws.workspace_id}
              ws={ws}
              onOpen={() => navigate({ to: "/workspace/$workspaceId", params: { workspaceId: ws.workspace_id } })}
            />
          ))}
        </div>
      </div>

      {/* ── RIGHT: daemon + domains ───────────────────────────────────── */}
      <div style={s.right}>
        {/* Daemon health */}
        <div style={s.card}>
          <div style={s.cardHeader}>
            <span style={s.cardTitle}>Local Daemon</span>
            <StatusBadge state={daemonState} />
          </div>

          {daemonState === "offline" && (
            <div style={s.offlineBox}>
              <p style={s.offlineText}>Daemon unreachable</p>
              <code style={s.codeBlock}>cd Core/daemon && uv run python src/main.py</code>
            </div>
          )}

          {daemonState === "online" && health && (
            <dl style={s.dl}>
              <dt style={s.dt}>Status</dt><dd style={s.dd}>{health.status}</dd>
              <dt style={s.dt}>Version</dt><dd style={s.dd}>{health.version}</dd>
              <dt style={s.dt}>Uptime</dt><dd style={s.dd}>{Math.floor(health.uptime_seconds / 3600)}h {Math.floor((health.uptime_seconds % 3600) / 60)}m</dd>
              <dt style={s.dt}>Active runs</dt><dd style={s.dd}>{health.active_runs}</dd>
            </dl>
          )}

          {lastChecked && (
            <p style={s.lastChecked}>
              Checked {lastChecked.toLocaleTimeString()} · every 5s
            </p>
          )}
        </div>

        {/* Domains */}
        <div style={s.card}>
          <div style={s.cardHeader}>
            <span style={s.cardTitle}>Domains</span>
            <span style={s.countBadge}>{domains.length}</span>
          </div>

          {domains.length === 0 ? (
            <div style={s.domainsEmpty}>
              <p style={s.muted}>No domains loaded</p>
              <code style={s.codeSmall}>uv pip install -e Domains/polymer/</code>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {domains.map((d) => (
                <div key={d.domain_id} style={s.domainRow}>
                  <div style={{ flex: 1 }}>
                    <div style={s.domainName}>{d.domain_name}</div>
                    <div style={s.domainId}>{d.domain_id} · {d.method_count} methods</div>
                  </div>
                  <div style={s.chips}>
                    {d.supported_data_types.slice(0, 3).map((t) => (
                      <span key={t} style={s.chip}>{t}</span>
                    ))}
                    {d.supported_data_types.length > 3 && (
                      <span style={s.chip}>+{d.supported_data_types.length - 3}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quick actions */}
        <div style={s.card}>
          <div style={s.cardTitle} >Quick Actions</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
            <QuickAction icon="📥" label="Ingest data" onClick={() => navigate({ to: "/ingest" })} />
            <QuickAction icon="🧩" label="Browse modules" onClick={() => navigate({ to: "/modules" })} />
            <QuickAction icon="⚙️" label="QPU settings" onClick={() => navigate({ to: "/settings/qpu" })} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function WorkspaceCard({ ws, onOpen }: { ws: WorkspaceSummary; onOpen: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <div
      style={{ ...s.wsCard, ...(hover ? s.wsCardHover : {}) }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div style={s.wsInfo}>
        <span style={s.wsIcon}>🔬</span>
        <div>
          <div style={s.wsName}>{ws.name}</div>
          <div style={s.wsDate}>{new Date(ws.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</div>
        </div>
      </div>
      <button onClick={onOpen} style={s.openBtn}>Open →</button>
    </div>
  );
}

function StatusBadge({ state }: { state: "connecting" | "online" | "offline" }) {
  const cfg = {
    connecting: { color: "#ff9f0a", label: "Connecting" },
    online:     { color: "#34c759", label: "Online" },
    offline:    { color: "#ff453a", label: "Offline" },
  }[state];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      <div style={{ width: 7, height: 7, borderRadius: "50%", background: cfg.color, boxShadow: `0 0 6px ${cfg.color}` }} />
      <span style={{ fontSize: 12, color: cfg.color, fontWeight: 600 }}>{cfg.label}</span>
    </div>
  );
}

function QuickAction({ icon, label, onClick }: { icon: string; label: string; onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      style={{ ...s.qaBtn, ...(hover ? s.qaBtnHover : {}) }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <span style={{ fontSize: 15 }}>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const s = {
  page: {
    display: "grid",
    gridTemplateColumns: "1fr 320px",
    gap: 24,
    padding: "28px 28px 28px 28px",
    maxWidth: 1200,
    margin: "0 auto",
    width: "100%",
    minHeight: "calc(100vh - 48px)",
    alignItems: "start",
  },
  left: { display: "flex", flexDirection: "column" as const, gap: 16 },
  right: { display: "flex", flexDirection: "column" as const, gap: 16 },

  sectionHeader: { display: "flex", alignItems: "center", gap: 10, marginBottom: 4 },
  sectionTitle: { fontSize: 20, fontWeight: 700, color: "var(--ss-text)" },
  sectionCount: {
    background: "var(--ss-surface-2)",
    border: "1px solid var(--ss-border)",
    color: "var(--ss-text-muted)",
    fontSize: 12, fontWeight: 600,
    padding: "2px 8px", borderRadius: 999,
  },

  createForm: { display: "flex", gap: 8 },
  input: {
    flex: 1, padding: "9px 14px", borderRadius: 8,
    border: "1px solid var(--ss-border)",
    background: "var(--ss-surface)",
    color: "var(--ss-text)", fontSize: 13,
    outline: "none",
  },
  createBtn: {
    padding: "9px 20px", borderRadius: 8,
    background: "var(--ss-accent)", border: "none",
    color: "#fff", fontSize: 13, fontWeight: 600,
    cursor: "pointer",
  },

  emptyState: {
    display: "flex", flexDirection: "column" as const,
    alignItems: "center", padding: "48px 0", gap: 8,
  },
  emptyIcon: { fontSize: 40, marginBottom: 4 },
  emptyTitle: { fontSize: 15, fontWeight: 600, color: "var(--ss-text)" },

  wsList: { display: "flex", flexDirection: "column" as const, gap: 8 },
  wsCard: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    background: "var(--ss-surface)",
    border: "1px solid var(--ss-border)",
    borderRadius: 10, padding: "14px 18px",
    cursor: "pointer", transition: "border-color 0.15s",
  },
  wsCardHover: { borderColor: "var(--ss-accent)" },
  wsInfo: { display: "flex", alignItems: "center", gap: 12 },
  wsIcon: { fontSize: 20 },
  wsName: { fontSize: 14, fontWeight: 600, color: "var(--ss-text)" },
  wsDate: { fontSize: 12, color: "var(--ss-text-muted)", marginTop: 2 },
  openBtn: {
    padding: "6px 16px", borderRadius: 7,
    background: "var(--ss-accent)", border: "none",
    color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer",
  },

  card: {
    background: "var(--ss-surface)",
    border: "1px solid var(--ss-border)",
    borderRadius: 12, padding: 18,
  },
  cardHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 },
  cardTitle: { fontSize: 14, fontWeight: 700, color: "var(--ss-text)" },
  countBadge: {
    background: "var(--ss-surface-2)", border: "1px solid var(--ss-border)",
    color: "var(--ss-text-muted)", fontSize: 12, fontWeight: 600,
    padding: "2px 8px", borderRadius: 999,
  },
  dl: { display: "grid", gridTemplateColumns: "100px 1fr", rowGap: 8, columnGap: 12 },
  dt: { fontSize: 12, color: "var(--ss-text-muted)", fontWeight: 500, alignSelf: "center" },
  dd: { fontSize: 13, color: "var(--ss-text)", fontWeight: 500 },
  lastChecked: { fontSize: 11, color: "var(--ss-text-muted)", marginTop: 12 },

  offlineBox: {
    background: "rgba(255,69,58,0.08)", border: "1px solid rgba(255,69,58,0.2)",
    borderRadius: 8, padding: 12,
  },
  offlineText: { fontSize: 13, color: "#ff453a", fontWeight: 600, marginBottom: 6 },
  codeBlock: {
    display: "block", fontSize: 11,
    fontFamily: "ui-monospace,'SF Mono',monospace",
    background: "var(--ss-surface-2)", border: "1px solid var(--ss-border)",
    borderRadius: 6, padding: "6px 10px", color: "var(--ss-text-muted)",
    whiteSpace: "pre-wrap" as const,
  },

  domainsEmpty: { display: "flex", flexDirection: "column" as const, gap: 8 },
  codeSmall: {
    fontSize: 11, fontFamily: "ui-monospace,'SF Mono',monospace",
    background: "var(--ss-surface-2)", border: "1px solid var(--ss-border)",
    borderRadius: 6, padding: "4px 8px", color: "var(--ss-text-muted)",
  },
  domainRow: {
    background: "var(--ss-surface-2)", border: "1px solid var(--ss-border)",
    borderRadius: 8, padding: "10px 12px",
    display: "flex", flexDirection: "column" as const, gap: 6,
  },
  domainName: { fontSize: 13, fontWeight: 600, color: "var(--ss-text)" },
  domainId: { fontSize: 11, color: "var(--ss-text-muted)" },
  chips: { display: "flex", flexWrap: "wrap" as const, gap: 4 },
  chip: {
    fontSize: 10, color: "var(--ss-accent)",
    background: "rgba(79,142,247,0.1)", border: "1px solid rgba(79,142,247,0.2)",
    borderRadius: 4, padding: "2px 6px",
    fontFamily: "ui-monospace,'SF Mono',monospace",
  },

  muted: { fontSize: 12, color: "var(--ss-text-muted)" },
  error: { fontSize: 12, color: "var(--ss-error)" },

  qaBtn: {
    display: "flex", alignItems: "center", gap: 10,
    padding: "9px 14px", borderRadius: 8,
    background: "var(--ss-surface-2)", border: "1px solid var(--ss-border)",
    color: "var(--ss-text)", fontSize: 13, fontWeight: 500, cursor: "pointer",
    width: "100%", textAlign: "left" as const,
    transition: "border-color 0.1s",
  },
  qaBtnHover: { borderColor: "var(--ss-accent)" },
} as const;
