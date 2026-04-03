/**
 * DaemonStatus — shows local daemon health and loaded domains.
 *
 * Phase 0 minimum health screen.
 * Polls GET /health every 5 seconds.
 *
 * Daemon response shapes (Execution_Plan_Phase0.md §4.1):
 *   /health → { status, version, uptime_seconds, active_runs, loaded_domains }
 *   /domains → DomainSummary[]  (plain array, NOT wrapped object)
 */

import { useState, useEffect, useCallback } from "react";
import { tauriInvoke } from "../App";

// ---------------------------------------------------------------------------
// Types — mirror daemon API models exactly
// ---------------------------------------------------------------------------

/** Matches daemon /health (plan §4.1) */
interface HealthResponse {
  status: "healthy" | "degraded" | "starting";
  version: string;
  uptime_seconds: number;
  active_runs: number;
  loaded_domains: string[];
}

/** Matches DomainModule.describe() — plan §4.1 + framework DomainModule */
interface DomainSummary {
  domain_id: string;
  domain_name: string;
  supported_data_types: string[];
  method_count: number;
}

type ConnectionState = "connecting" | "online" | "offline";

// ---------------------------------------------------------------------------
// DaemonStatus component
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 5000;

export function DaemonStatus() {
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [domains, setDomains] = useState<DomainSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const h = await tauriInvoke<HealthResponse>("get_daemon_health");
      setHealth(h);
      setConnection("online");
      setError(null);
    } catch (e) {
      setConnection("offline");
      setError(e instanceof Error ? e.message : String(e));
      setHealth(null);
    } finally {
      setLastChecked(new Date());
    }
  }, []);

  const fetchDomains = useCallback(async () => {
    try {
      // /domains returns a plain DomainSummary[] (not wrapped)
      const d = await tauriInvoke<DomainSummary[]>("get_domains");
      setDomains(Array.isArray(d) ? d : []);
    } catch {
      setDomains([]);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    fetchDomains();
    const timer = setInterval(() => {
      fetchHealth();
      fetchDomains();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [fetchHealth, fetchDomains]);

  return (
    <div style={styles.container}>
      {/* Health card */}
      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <span style={styles.cardTitle}>Local Daemon</span>
          <ConnectionBadge state={connection} />
        </div>

        {connection === "connecting" && (
          <p style={styles.mutedText}>Connecting to local daemon on 127.0.0.1:9473…</p>
        )}

        {connection === "offline" && (
          <div style={styles.errorBox}>
            <p style={styles.errorText}>Daemon unreachable</p>
            <p style={styles.mutedText}>{error}</p>
            <p style={styles.mutedText}>
              Start the daemon:{" "}
              <code style={styles.code}>
                cd Core/daemon &amp;&amp; uv run python src/main.py
              </code>
            </p>
          </div>
        )}

        {connection === "online" && health && (
          <dl style={styles.dl}>
            <dt style={styles.dt}>Status</dt>
            <dd style={styles.dd}>{health.status}</dd>

            <dt style={styles.dt}>Version</dt>
            <dd style={styles.dd}>{health.version}</dd>

            <dt style={styles.dt}>Uptime</dt>
            <dd style={styles.dd}>{health.uptime_seconds}s</dd>

            <dt style={styles.dt}>Active runs</dt>
            <dd style={styles.dd}>{health.active_runs}</dd>

            <dt style={styles.dt}>Loaded domains</dt>
            <dd style={styles.dd}>
              {health.loaded_domains.length === 0 ? (
                <span style={styles.mutedText}>none</span>
              ) : (
                health.loaded_domains.join(", ")
              )}
            </dd>
          </dl>
        )}

        {lastChecked && (
          <p style={{ ...styles.mutedText, marginTop: 12, fontSize: 11 }}>
            Last checked: {lastChecked.toLocaleTimeString()} · polling every{" "}
            {POLL_INTERVAL_MS / 1000}s
          </p>
        )}
      </div>

      {/* Domains card */}
      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <span style={styles.cardTitle}>Registered Domains</span>
          <span style={styles.badge}>{domains.length}</span>
        </div>

        {domains.length === 0 ? (
          <div style={styles.emptyState}>
            <p style={styles.emptyStateTitle}>No domains loaded</p>
            <p style={styles.mutedText}>
              Install a domain plugin, e.g.{" "}
              <code style={styles.code}>uv pip install -e Domains/polymer/</code>
            </p>
          </div>
        ) : (
          <div style={styles.domainList}>
            {domains.map((d) => (
              <DomainCard key={d.domain_id} domain={d} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ConnectionBadge({ state }: { state: ConnectionState }) {
  const cfg = {
    connecting: { color: "#ff9f0a", label: "Connecting…" },
    online: { color: "#34c759", label: "Online" },
    offline: { color: "#ff453a", label: "Offline" },
  }[state];

  return (
    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: cfg.color,
          display: "inline-block",
        }}
      />
      <span style={{ fontSize: 12, color: cfg.color, fontWeight: 500 }}>
        {cfg.label}
      </span>
    </span>
  );
}

function DomainCard({ domain }: { domain: DomainSummary }) {
  return (
    <div style={styles.domainCard}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <span style={styles.domainName}>{domain.domain_name}</span>
          <span style={styles.domainId}> ({domain.domain_id})</span>
        </div>
        <span style={styles.methodCount}>{domain.method_count} methods</span>
      </div>
      {domain.supported_data_types.length > 0 && (
        <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {domain.supported_data_types.map((t) => (
            <span key={t} style={styles.dataTypeChip}>{t}</span>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = {
  container: { display: "flex", flexDirection: "column" as const, gap: 16 },
  card: {
    background: "var(--ss-surface)",
    border: "1px solid var(--ss-border)",
    borderRadius: 10,
    padding: 20,
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  cardTitle: { fontSize: 15, fontWeight: 600, color: "var(--ss-text)" },
  badge: {
    background: "var(--ss-surface-2)",
    color: "var(--ss-text-muted)",
    fontSize: 12,
    fontWeight: 500,
    borderRadius: 999,
    padding: "2px 10px",
    border: "1px solid var(--ss-border)",
  },
  dl: { display: "grid", gridTemplateColumns: "140px 1fr", gap: "6px 12px" },
  dt: { fontSize: 12, color: "var(--ss-text-muted)", fontWeight: 500, paddingTop: 2 },
  dd: { fontSize: 13, color: "var(--ss-text)" },
  mutedText: { fontSize: 12, color: "var(--ss-text-muted)", lineHeight: 1.5 },
  errorBox: {
    background: "rgba(255,69,58,0.08)",
    border: "1px solid rgba(255,69,58,0.2)",
    borderRadius: 8,
    padding: 12,
    display: "flex",
    flexDirection: "column" as const,
    gap: 6,
  },
  errorText: { fontSize: 13, color: "#ff453a", fontWeight: 500 },
  code: {
    fontFamily: "ui-monospace,'SF Mono',Menlo,monospace",
    fontSize: 11,
    background: "var(--ss-surface-2)",
    padding: "2px 6px",
    borderRadius: 4,
    border: "1px solid var(--ss-border)",
  },
  emptyState: {
    textAlign: "center" as const,
    padding: "32px 0",
    display: "flex",
    flexDirection: "column" as const,
    gap: 8,
    alignItems: "center",
  },
  emptyStateTitle: { fontSize: 14, color: "var(--ss-text-muted)", fontWeight: 500 },
  domainList: { display: "flex", flexDirection: "column" as const, gap: 10 },
  domainCard: {
    background: "var(--ss-surface-2)",
    border: "1px solid var(--ss-border)",
    borderRadius: 8,
    padding: 14,
  },
  domainName: { fontSize: 13, fontWeight: 600, color: "var(--ss-text)" },
  domainId: { fontSize: 12, color: "var(--ss-text-muted)" },
  methodCount: { fontSize: 12, color: "var(--ss-text-muted)", fontWeight: 500 },
  dataTypeChip: {
    fontSize: 11,
    color: "var(--ss-accent)",
    background: "rgba(79,142,247,0.1)",
    border: "1px solid rgba(79,142,247,0.2)",
    borderRadius: 4,
    padding: "2px 8px",
    fontFamily: "ui-monospace,'SF Mono',Menlo,monospace",
  },
} as const;
