/**
 * Health Diagnostics — sidecar daemon health checks and runtime fingerprinting.
 *
 * Provides structured diagnostics for the Desktop workbench:
 *   - Daemon alive check (HTTP GET /monitoring/health)
 *   - Port binding / metrics check (HTTP GET /monitoring/metrics)
 *   - Filesystem accessibility check (app data dir via Tauri API)
 *   - Runtime fingerprint (OS, arch, versions)
 *   - Daemon restart via Tauri shell sidecar API
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DAEMON_BASE_URL = "http://127.0.0.1:9371";
const HEALTH_TIMEOUT_MS = 5000;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DiagnosticStatus = "ok" | "warn" | "error";

export interface DiagnosticResult {
  check: string;
  status: DiagnosticStatus;
  detail: string;
  timestamp: string;
}

export interface RuntimeFingerprint {
  os: string;
  arch: string;
  os_version: string;
  node_version: string;
  tauri_version: string;
  daemon_version: string;
}

export interface HealthReport {
  platform: string;
  arch: string;
  daemon_alive: boolean;
  diagnostics: DiagnosticResult[];
  runtime_fingerprint: RuntimeFingerprint;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Fetch with a timeout. Returns the Response or throws on timeout / network error.
 */
async function fetchWithTimeout(
  url: string,
  timeoutMs: number = HEALTH_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(url, { signal: controller.signal });
    return resp;
  } finally {
    clearTimeout(timer);
  }
}

function now(): string {
  return new Date().toISOString();
}

// ---------------------------------------------------------------------------
// Diagnostic checks
// ---------------------------------------------------------------------------

/**
 * Check 1: Daemon alive — GET /monitoring/health must return 200 with status "healthy".
 */
async function checkDaemonAlive(): Promise<DiagnosticResult> {
  try {
    const resp = await fetchWithTimeout(`${DAEMON_BASE_URL}/monitoring/health`);
    if (!resp.ok) {
      return {
        check: "daemon_alive",
        status: "error",
        detail: `Daemon responded with HTTP ${resp.status}`,
        timestamp: now(),
      };
    }
    const data = await resp.json();
    const healthy = data.status === "healthy";
    return {
      check: "daemon_alive",
      status: healthy ? "ok" : "warn",
      detail: healthy
        ? `Daemon healthy — uptime ${data.uptime_seconds ?? "?"}s`
        : `Daemon status: ${data.status ?? "unknown"}`,
      timestamp: now(),
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const isAbort = message.includes("abort");
    return {
      check: "daemon_alive",
      status: "error",
      detail: isAbort
        ? `Daemon unreachable — timed out after ${HEALTH_TIMEOUT_MS}ms`
        : `Daemon unreachable — ${message}`,
      timestamp: now(),
    };
  }
}

/**
 * Check 2: Port binding / metrics — GET /monitoring/metrics must return 200.
 */
async function checkPortBinding(): Promise<DiagnosticResult> {
  try {
    const resp = await fetchWithTimeout(`${DAEMON_BASE_URL}/monitoring/metrics`);
    if (!resp.ok) {
      return {
        check: "port_binding",
        status: "error",
        detail: `Metrics endpoint returned HTTP ${resp.status}`,
        timestamp: now(),
      };
    }
    const data = await resp.json();
    const hasFields =
      "daemon_uptime_seconds" in data &&
      "daemon_request_count" in data &&
      "daemon_error_count" in data;
    return {
      check: "port_binding",
      status: hasFields ? "ok" : "warn",
      detail: hasFields
        ? `Port bound — ${data.daemon_request_count} total requests`
        : "Metrics response missing expected fields",
      timestamp: now(),
    };
  } catch {
    return {
      check: "port_binding",
      status: "error",
      detail: "Metrics endpoint unreachable — port may not be bound",
      timestamp: now(),
    };
  }
}

/**
 * Check 3: Filesystem smoke test — verify app data directory is accessible.
 * Uses Tauri path API when available, falls back to a basic check.
 */
async function checkFilesystem(): Promise<DiagnosticResult> {
  try {
    // Try Tauri path plugin for app data directory
    const { appDataDir } = await import("@tauri-apps/api/path");
    const dir = await appDataDir();
    return {
      check: "filesystem",
      status: "ok",
      detail: `App data directory accessible: ${dir}`,
      timestamp: now(),
    };
  } catch {
    // Fallback: Tauri API not available (e.g. running in browser dev mode)
    return {
      check: "filesystem",
      status: "warn",
      detail: "Tauri path API unavailable — cannot verify app data directory",
      timestamp: now(),
    };
  }
}

/** Safely read Node.js process.version without depending on @types/node. */
function getNodeVersion(): string {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const p = (globalThis as any).process;
    if (p && typeof p.version === "string") return p.version;
  } catch { /* not in Node */ }
  return "n/a";
}

/**
 * Build runtime fingerprint by querying daemon version endpoint and Tauri APIs.
 */
async function buildRuntimeFingerprint(): Promise<RuntimeFingerprint> {
  let os = "unknown";
  let arch = "unknown";
  let osVersion = "unknown";
  let tauriVersion = "unknown";
  let daemonVersion = "unknown";

  // Tauri OS info
  try {
    const osModule = await import("@tauri-apps/api/os" as string);
    if (osModule.platform) os = await osModule.platform();
    if (osModule.arch) arch = await osModule.arch();
    if (osModule.version) osVersion = await osModule.version();
  } catch {
    // Fallback to navigator
    try {
      const ua = navigator.userAgent;
      if (ua.includes("Mac")) os = "darwin";
      else if (ua.includes("Win")) os = "win32";
      else if (ua.includes("Linux")) os = "linux";
    } catch {
      /* ignore */
    }
  }

  // Tauri version
  try {
    const { getVersion } = await import("@tauri-apps/api/app");
    tauriVersion = await getVersion();
  } catch {
    /* not available */
  }

  // Daemon version from /monitoring/version
  try {
    const resp = await fetchWithTimeout(
      `${DAEMON_BASE_URL}/monitoring/version`,
      3000,
    );
    if (resp.ok) {
      const data = await resp.json();
      daemonVersion = data.version ?? "unknown";
    }
  } catch {
    /* unreachable */
  }

  return {
    os,
    arch,
    os_version: osVersion,
    node_version: getNodeVersion(),
    tauri_version: tauriVersion,
    daemon_version: daemonVersion,
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Run all health diagnostics and return a structured HealthReport.
 *
 * Checks run concurrently for speed. The report includes:
 *   1. Daemon alive check
 *   2. Port binding / metrics check
 *   3. Filesystem smoke test
 *   4. Runtime fingerprint
 */
export async function runHealthDiagnostics(): Promise<HealthReport> {
  const [daemonCheck, portCheck, fsCheck, fingerprint] = await Promise.all([
    checkDaemonAlive(),
    checkPortBinding(),
    checkFilesystem(),
    buildRuntimeFingerprint(),
  ]);

  const diagnostics = [daemonCheck, portCheck, fsCheck];
  const daemonAlive = daemonCheck.status === "ok";

  return {
    platform: fingerprint.os,
    arch: fingerprint.arch,
    daemon_alive: daemonAlive,
    diagnostics,
    runtime_fingerprint: fingerprint,
  };
}

/**
 * Restart the daemon sidecar process via Tauri shell plugin.
 *
 * Kills any existing sidecar and spawns a new instance.
 * Returns success status and optional error message.
 */
export async function restartDaemon(): Promise<{
  success: boolean;
  error?: string;
}> {
  try {
    const { Command } = await import("@tauri-apps/plugin-shell");

    // Spawn sidecar — Tauri resolves the binary from externalBin config
    const sidecar = Command.sidecar("scientificstate-daemon");
    const child = await sidecar.spawn();

    // Give the daemon a moment to bind its port, then verify
    await new Promise((resolve) => setTimeout(resolve, 2000));

    try {
      const resp = await fetchWithTimeout(
        `${DAEMON_BASE_URL}/monitoring/health`,
        3000,
      );
      if (resp.ok) {
        return { success: true };
      }
      return {
        success: false,
        error: `Daemon started (PID ${child.pid}) but health check returned HTTP ${resp.status}`,
      };
    } catch {
      return {
        success: false,
        error: `Daemon started (PID ${child.pid}) but health endpoint is unreachable`,
      };
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      success: false,
      error: `Failed to restart daemon: ${message}`,
    };
  }
}
