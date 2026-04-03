/*!
ScientificState Desktop — Tauri Rust Core (lib).

Responsibilities (thin layer):
- IPC gateway: WebView ↔ Rust command dispatch
- Daemon health polling
- Localhost boundary enforcement (daemon is always 127.0.0.1:9473)

Scientific computation lives in the Python daemon — NOT here.
*/

use serde::{Deserialize, Serialize};
use tauri::Manager;

// ---------------------------------------------------------------------------
// Daemon client types
// ---------------------------------------------------------------------------

const DAEMON_BASE_URL: &str = "http://127.0.0.1:9473";

/// Matches daemon /health response (Execution_Plan_Phase0.md §4.1)
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
    pub uptime_seconds: f64,
    pub active_runs: u32,
    pub loaded_domains: Vec<String>,
}

/// Matches DomainModule.describe() — plan §4.1 + framework DomainModule.describe()
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DomainSummary {
    pub domain_id: String,
    pub domain_name: String,
    pub supported_data_types: Vec<String>,
    pub method_count: u32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DaemonError {
    pub message: String,
    pub code: String,
}

// ---------------------------------------------------------------------------
// Tauri commands (IPC handlers)
// ---------------------------------------------------------------------------

/// Poll daemon health. Called by DaemonStatus component on mount + interval.
#[tauri::command]
async fn get_daemon_health() -> Result<HealthResponse, String> {
    let url = format!("{DAEMON_BASE_URL}/health");
    let resp = reqwest::get(&url).await.map_err(|e| {
        format!("Daemon unreachable: {e}")
    })?;
    let health: HealthResponse = resp.json().await.map_err(|e| {
        format!("Failed to parse health response: {e}")
    })?;
    Ok(health)
}

/// Get the list of registered domains from the daemon.
/// Daemon returns a plain JSON array (plan §4.1), not a wrapped object.
#[tauri::command]
async fn get_domains() -> Result<Vec<DomainSummary>, String> {
    let url = format!("{DAEMON_BASE_URL}/domains");
    let resp = reqwest::get(&url).await.map_err(|e| {
        format!("Daemon unreachable: {e}")
    })?;
    let domains: Vec<DomainSummary> = resp.json().await.map_err(|e| {
        format!("Failed to parse domains response: {e}")
    })?;
    Ok(domains)
}

/// Check if daemon is reachable (simple ping used by startup checks).
#[tauri::command]
async fn ping_daemon() -> bool {
    reqwest::get(format!("{DAEMON_BASE_URL}/health"))
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

// ---------------------------------------------------------------------------
// App setup
// ---------------------------------------------------------------------------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_http::init())
        .invoke_handler(tauri::generate_handler![
            get_daemon_health,
            get_domains,
            ping_daemon,
        ])
        .setup(|app| {
            #[cfg(debug_assertions)]
            {
                if let Some(window) = app.get_webview_window("main") {
                    window.open_devtools();
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Error while running ScientificState desktop application");
}
