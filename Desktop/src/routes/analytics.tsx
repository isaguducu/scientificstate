import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

const DAEMON_URL = "http://127.0.0.1:9473";

interface Alert {
  severity: "critical" | "warning" | "info";
  type: string;
  message: string;
}

interface MetricsData {
  daemon_uptime_seconds: number;
  daemon_request_count: number;
  daemon_error_count: number;
  daemon_db_size_bytes: number;
}

interface AlertsData {
  alerts: Alert[];
  count: number;
  checked_at: string;
}

// ── Claim lifecycle canonical 7-state ─────────────────────────────────────
const CLAIM_STATES = [
  "draft",
  "under_review",
  "provisionally_supported",
  "endorsable",
  "endorsed",
  "contested",
  "retracted",
] as const;

const STATE_COLORS: Record<string, string> = {
  draft: "bg-gray-200",
  under_review: "bg-blue-200",
  provisionally_supported: "bg-yellow-200",
  endorsable: "bg-emerald-200",
  endorsed: "bg-green-400",
  contested: "bg-orange-300",
  retracted: "bg-red-300",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: "bg-red-500 text-white",
    warning: "bg-yellow-400 text-black",
    info: "bg-blue-200 text-blue-900",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${colors[severity] ?? "bg-gray-200"}`}
    >
      {severity}
    </span>
  );
}

export function Analytics() {
  const { t } = useTranslation();

  const metrics = useQuery<MetricsData>({
    queryKey: ["monitoring-metrics"],
    queryFn: () => fetch(`${DAEMON_URL}/monitoring/metrics`).then((r) => r.json()),
    refetchInterval: 10_000,
  });

  const alertsQuery = useQuery<AlertsData>({
    queryKey: ["monitoring-alerts"],
    queryFn: () => fetch(`${DAEMON_URL}/monitoring/alerts`).then((r) => r.json()),
    refetchInterval: 30_000,
  });

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold">{t("nav.analytics", "Analytics")}</h1>

      {/* ── Daemon Metrics ──────────────────────────────────────── */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Uptime"
          value={
            metrics.data
              ? formatUptime(metrics.data.daemon_uptime_seconds)
              : "—"
          }
        />
        <MetricCard
          label="Requests"
          value={metrics.data?.daemon_request_count?.toString() ?? "—"}
        />
        <MetricCard
          label="Errors"
          value={metrics.data?.daemon_error_count?.toString() ?? "—"}
        />
        <MetricCard
          label="DB Size"
          value={
            metrics.data
              ? formatBytes(metrics.data.daemon_db_size_bytes)
              : "—"
          }
        />
      </section>

      {/* ── Alerts ──────────────────────────────────────────────── */}
      <section>
        <h2 className="text-lg font-semibold mb-2">Alerts</h2>
        {alertsQuery.data?.count === 0 ? (
          <p className="text-green-600 text-sm">No active alerts</p>
        ) : (
          <ul className="space-y-2">
            {alertsQuery.data?.alerts.map((a, i) => (
              <li
                key={i}
                className="flex items-center gap-2 p-2 rounded border"
              >
                <SeverityBadge severity={a.severity} />
                <span className="text-sm">{a.message}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ── Claim Lifecycle Funnel ──────────────────────────────── */}
      <section>
        <h2 className="text-lg font-semibold mb-2">
          Claim Lifecycle (7-state)
        </h2>
        <div className="flex flex-wrap gap-2">
          {CLAIM_STATES.map((state) => (
            <div
              key={state}
              className={`px-3 py-2 rounded text-xs font-mono ${STATE_COLORS[state]}`}
            >
              {state.replace(/_/g, " ")}
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-1">
          draft → under_review → provisionally_supported → endorsable →
          endorsed | contested | retracted
        </p>
      </section>

      {/* ── Replication Status ──────────────────────────────────── */}
      <section>
        <h2 className="text-lg font-semibold mb-2">Replication</h2>
        <div className="flex gap-4 text-sm">
          <div className="px-3 py-2 bg-green-100 rounded">
            confirmed
          </div>
          <div className="px-3 py-2 bg-yellow-100 rounded">
            partially_confirmed
          </div>
          <div className="px-3 py-2 bg-red-100 rounded">not_confirmed</div>
        </div>
      </section>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-4 rounded-lg border bg-white shadow-sm">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-xl font-bold mt-1">{value}</p>
    </div>
  );
}
