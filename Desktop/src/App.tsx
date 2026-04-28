import React, { useState, useEffect } from "react";
import { Link, useRouterState } from "@tanstack/react-router";

// ---------------------------------------------------------------------------
// Tauri IPC — falls back to direct HTTP in browser / dev mode
// ---------------------------------------------------------------------------
async function tauriInvoke<T>(cmd: string): Promise<T> {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    return await invoke<T>(cmd);
  } catch {
    const urlMap: Record<string, string> = {
      get_daemon_health: "http://127.0.0.1:9473/health",
      get_domains: "http://127.0.0.1:9473/domains",
    };
    const url = urlMap[cmd];
    if (!url) throw new Error(`No browser fallback for command: ${cmd}`);
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as T;
  }
}

export { tauriInvoke };

// ---------------------------------------------------------------------------
// Mini daemon status dot (used in the top nav)
// ---------------------------------------------------------------------------
type DaemonState = "connecting" | "online" | "offline";

function DaemonDot() {
  const [state, setState] = useState<DaemonState>("connecting");

  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        await tauriInvoke("get_daemon_health");
        if (alive) setState("online");
      } catch {
        if (alive) setState("offline");
      }
    }
    poll();
    const t = setInterval(poll, 5000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const color = state === "online" ? "#34c759" : state === "offline" ? "#ff453a" : "#ff9f0a";
  const label = state === "online" ? "Online" : state === "offline" ? "Offline" : "…";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{
        width: 7, height: 7, borderRadius: "50%", background: color,
        boxShadow: `0 0 6px ${color}`,
      }} />
      <span style={{ fontSize: 12, color, fontWeight: 500 }}>{label}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// App shell
// ---------------------------------------------------------------------------
interface Props { children?: React.ReactNode }

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/ingest", label: "Ingest" },
  { to: "/modules", label: "Modules" },
  { to: "/settings/qpu", label: "Settings" },
] as const;

function App({ children }: Props) {
  const routerState = useRouterState();
  const currentPath = routerState.location.pathname;

  return (
    <div style={shell.root}>
      {/* ── Top nav ──────────────────────────────────────────────────── */}
      <header style={shell.header}>
        <Link to="/" style={shell.logo}>
          <span style={{ fontSize: 18 }}>⚗️</span>
          <span style={shell.logoText}>ScientificState</span>
        </Link>
        <nav style={shell.nav}>
          {NAV.map(({ to, label }) => {
            const active = to === "/" ? currentPath === "/" : currentPath.startsWith(to);
            return (
              <Link
                key={to}
                to={to}
                style={{ ...shell.navLink, ...(active ? shell.navLinkActive : {}) }}
              >
                {label}
              </Link>
            );
          })}
        </nav>
        <div style={{ marginLeft: "auto" }}>
          <DaemonDot />
        </div>
      </header>

      {/* ── Page content ─────────────────────────────────────────────── */}
      <main style={shell.main}>
        {children}
      </main>
    </div>
  );
}

export default App;

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const shell = {
  root: {
    display: "flex",
    flexDirection: "column" as const,
    minHeight: "100vh",
    background: "var(--ss-bg)",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "0 24px",
    height: 48,
    background: "var(--ss-surface)",
    borderBottom: "1px solid var(--ss-border)",
    position: "sticky" as const,
    top: 0,
    zIndex: 100,
    flexShrink: 0,
  },
  logo: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    textDecoration: "none",
    color: "inherit",
    marginRight: 16,
  },
  logoText: {
    fontSize: 15,
    fontWeight: 700,
    letterSpacing: "-0.3px",
    color: "var(--ss-text)",
  },
  nav: {
    display: "flex",
    gap: 2,
  },
  navLink: {
    fontSize: 13,
    fontWeight: 500,
    color: "var(--ss-text-muted)",
    textDecoration: "none",
    padding: "5px 12px",
    borderRadius: 6,
    transition: "color 0.1s, background 0.1s",
  },
  navLinkActive: {
    color: "var(--ss-text)",
    background: "var(--ss-surface-2)",
  },
  main: {
    flex: 1,
    overflow: "auto",
  },
} as const;
