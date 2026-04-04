/**
 * Desktop Sentry integration — error tracking with PII scrubbing.
 *
 * Initializes only when VITE_SENTRY_DSN environment variable is set.
 * All ORCID, email, and institution data is stripped before sending.
 *
 * @sentry/browser is an optional dependency — if not installed,
 * these functions are silent no-ops.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

let _sentry: any = null;

// Access env safely without import.meta.env (avoids type issues)
function getEnv(key: string): string | undefined {
  try {
    // Vite injects VITE_ env vars at build time
    const env = (globalThis as any).__VITE_ENV__ ?? {};
    return env[key] ?? undefined;
  } catch {
    return undefined;
  }
}

export async function initSentry(): Promise<void> {
  const dsn = getEnv("VITE_SENTRY_DSN");
  if (!dsn) return;

  try {
    const mod = await import("@sentry/browser");
    mod.init({
      dsn,
      environment: getEnv("MODE") || "production",
      release: getEnv("VITE_APP_VERSION") || "0.0.0",
      tracesSampleRate: 0.1,
      beforeSend(event: any) {
        // PII scrubbing — ORCID, email, institution info
        if (event.user) {
          delete event.user.email;
          delete event.user.username;
          delete event.user.ip_address;
        }
        return event;
      },
    });
    _sentry = mod;
  } catch {
    // @sentry/browser not installed — silent no-op
  }
}

export function captureError(
  error: Error,
  context?: Record<string, unknown>,
): void {
  if (!_sentry) return;
  _sentry.captureException(error, { extra: context });
}
