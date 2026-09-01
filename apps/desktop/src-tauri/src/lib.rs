//! Hermetic desktop shell — Tauri v2 builder (build log D15 / Phase 0c).
//!
//! Three-context model (specs/pyodide-wasm-sandbox-2026-08-26.md §4a):
//!
//! ```text
//! Rust core ── spawns ──▶ Node sidecar (TRUSTED)     Webview (UNTRUSTED content)
//! (this crate)            the Next standalone server   the Next UI + the Pyodide/
//!                         (lib pipeline/orchestrator)   DuckDB-WASM execution worker
//! ```
//!
//! Security posture (§7):
//!   - §7 #1: the IPC surface reachable from webview JS is EMPTY of host-touching
//!     commands. NO custom `invoke` handlers; the capability set grants only
//!     `core:default` + window basics; `withGlobalTauri:false` removes
//!     `window.__TAURI__`. The sidecar is spawned from RUST via `std::process`
//!     (NOT a shell plugin), so no spawn/exec command is ever exposed to the page.
//!   - §7 #2: the execution worker gets its OWN stricter CSP at runtime (D8=self:
//!     `script-src 'self' 'wasm-unsafe-eval' blob:; connect-src 'self'`), served on
//!     the /api/wasm-worker response — NOT the app CSP here.
//!
//! Runtime: in release the sidecar serves the app on a loopback port and the window
//! loads it; in `tauri dev` (debug) the window uses the dev server (devUrl) and no
//! sidecar is spawned. The sidecar's lifecycle is tied to the app — killed on exit.

use std::fs::{self, File};
use std::net::{TcpListener, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use uuid::Uuid;

/// Processes started by this app. External dev services are never adopted or killed.
struct ManagedChildren {
    backend: Mutex<Option<Child>>,
    ui: Mutex<Option<Child>>,
}

/// Pick a free loopback TCP port by binding :0 and reading the assigned port.
fn free_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    Ok(listener.local_addr()?.port())
}

/// Block until the sidecar accepts connections on `port` (or time out).
fn wait_ready(port: u16, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if TcpStream::connect(("127.0.0.1", port)).is_ok() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(150));
    }
    false
}

/// Resolve the bundled sidecar dir (the assembled Next standalone server + node +
/// assets). Bundled under the app resource dir as `sidecar/` (tauri.conf resources).
fn sidecar_dir(app: &tauri::App) -> Option<PathBuf> {
    // Explicit override (dev / testing): point at an already-assembled sidecar so the
    // packaged code path can be exercised from a fast debug build, without a full
    // `tauri build`. Wins over the bundled resource dir.
    if let Ok(d) = std::env::var("HERMETIC_SIDECAR_DIR") {
        let p = PathBuf::from(d);
        if p.join("server.js").exists() {
            return Some(p);
        }
    }
    let dir = app.path().resource_dir().ok()?.join("sidecar");
    if dir.join("server.js").exists() {
        Some(dir)
    } else {
        None
    }
}

/// Resolve the bundled deterministic Python backend assembled by PyInstaller.
fn backend_dir(app: &tauri::App) -> Option<PathBuf> {
    if let Ok(d) = std::env::var("LAC_BACKEND_DIR") {
        let p = PathBuf::from(d);
        if backend_executable(&p).exists() {
            return Some(p);
        }
    }
    let dir = app.path().resource_dir().ok()?.join("lac-backend");
    if backend_executable(&dir).exists() {
        Some(dir)
    } else {
        None
    }
}

fn backend_executable(dir: &std::path::Path) -> PathBuf {
    dir.join(if cfg!(windows) {
        "lac-backend.exe"
    } else {
        "lac-backend"
    })
}

#[cfg(windows)]
fn hide_child_window(command: &mut Command) {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    command.creation_flags(CREATE_NO_WINDOW);
}

#[cfg(not(windows))]
fn hide_child_window(_command: &mut Command) {}

fn app_data_root(app: &tauri::App, fallback: &PathBuf) -> std::io::Result<PathBuf> {
    let data = app.path().app_data_dir().unwrap_or_else(|_| fallback.clone());
    for directory in ["workspace", "config", "logs", "data", "user", "scratch"] {
        fs::create_dir_all(data.join(directory))?;
    }
    Ok(data)
}

fn log_file(data: &std::path::Path, name: &str) -> std::io::Result<File> {
    File::create(data.join("logs").join(name))
}

/// Spawn the packaged deterministic analytics backend on an ephemeral loopback port.
fn spawn_backend(dir: &PathBuf, data: &PathBuf) -> std::io::Result<(Child, String, String)> {
    let port = free_port()?;
    let token = Uuid::new_v4().simple().to_string();
    let mut command = Command::new(backend_executable(dir));
    command
        .current_dir(dir)
        .env("LAC_BRIDGE_PORT", port.to_string())
        .env("LAC_WORKSPACE", data.join("workspace"))
        .env("LAC_CONFIG_DIR", data.join("config"))
        .env("LAC_API_TOKEN", &token)
        .env("PYTHONUTF8", "1")
        .env("PYTHONIOENCODING", "utf-8")
        .stdin(Stdio::null())
        .stdout(Stdio::from(log_file(data, "backend.stdout.log")?))
        .stderr(Stdio::from(log_file(data, "backend.stderr.log")?));
    hide_child_window(&mut command);
    let child = command.spawn()?;
    Ok((child, format!("http://127.0.0.1:{port}"), token))
}

/// Spawn `node server.js` from the sidecar dir with the packaged environment, and
/// return the child + the loopback URL it serves.
fn spawn_sidecar(
    dir: &PathBuf,
    data: &PathBuf,
    lac_base: &str,
    api_token: &str,
) -> std::io::Result<(Child, String)> {
    let port = free_port()?;
    let node = dir.join(if cfg!(windows) { "node.exe" } else { "node" });
    let egress = dir
        .join("bin")
        .join(if cfg!(windows) { "egress-fetch.exe" } else { "egress-fetch" });

    let mut command = Command::new(node);
    command
        // Preload the hashed-externals hook (build log D16) — works around the Next 16
        // Turbopack production bug where external modules (pg, @napi-rs/keyring, …) are
        // required under an unresolvable content-hash suffix. Then the standalone entry.
        .arg("--require")
        .arg("./hash-externals-hook.cjs")
        .arg("server.js")
        .current_dir(dir)
        .env("HOSTNAME", "127.0.0.1")
        .env("PORT", port.to_string())
        .env("NEXT_PUBLIC_LAC_HYBRID", "1")
        .env("LAC_BRIDGE_URL", lac_base)
        .env("LAC_API_TOKEN", api_token)
        .env("HERMETIC_ASSET_ROOT", dir)
        .env("HERMETIC_DATA_ROOT", data.join("data"))
        .env("HERMETIC_USER_ROOT", data.join("user"))
        .env("HERMETIC_SCRATCH_ROOT", data.join("scratch"))
        .env("HERMETIC_PYODIDE_DIR", dir.join("pyodide"))
        .env("HERMETIC_EGRESS_FETCH_BIN", egress)
        // The desktop ships the WASM tier + no Docker — force it, predictably.
        .env("HERMETIC_FORCE_RUNTIME", "wasm")
        .stdin(Stdio::null())
        .stdout(Stdio::from(log_file(data, "ui.stdout.log")?))
        .stderr(Stdio::from(log_file(data, "ui.stderr.log")?));
    hide_child_window(&mut command);
    let child = command.spawn()?;

    Ok((child, format!("http://127.0.0.1:{port}")))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // No `.invoke_handler(...)` on purpose (§7 #1): a custom command would be
        // reachable from untrusted webview JS. The sidecar is spawned from Rust below.
        .manage(ManagedChildren {
            backend: Mutex::new(None),
            ui: Mutex::new(None),
        })
        .setup(|app| {
            // DEV (`tauri dev`, debug build): use the hot-reload Next dev server (devUrl)
            // and never spawn a (possibly stale) sidecar — UNLESS HERMETIC_SIDECAR_DIR is
            // set to explicitly test the packaged path. RELEASE: always spawn the sidecar.
            let force_sidecar = std::env::var("HERMETIC_SIDECAR_DIR").is_ok();
            let bundled = if cfg!(debug_assertions) && !force_sidecar {
                None
            } else {
                sidecar_dir(app)
            };
            let url = match bundled {
                Some(dir) => {
                    let backend = backend_dir(app).ok_or_else(|| {
                        std::io::Error::new(
                            std::io::ErrorKind::NotFound,
                            "bundled LAC backend resource is missing",
                        )
                    })?;
                    let data = app_data_root(app, &dir)?;
                    let (mut backend_child, lac_base, api_token) =
                        spawn_backend(&backend, &data)?;
                    if !wait_ready(url_port(&lac_base), Duration::from_secs(60)) {
                        let _ = backend_child.kill();
                        return Err(std::io::Error::new(
                            std::io::ErrorKind::TimedOut,
                            "deterministic LAC backend did not become ready; see backend.stderr.log",
                        )
                        .into());
                    }
                    app.state::<ManagedChildren>()
                        .backend
                        .lock()
                        .unwrap()
                        .replace(backend_child);

                    let (mut ui_child, base) =
                        match spawn_sidecar(&dir, &data, &lac_base, &api_token) {
                            Ok(value) => value,
                            Err(error) => {
                                if let Some(mut child) = app
                                    .state::<ManagedChildren>()
                                    .backend
                                    .lock()
                                    .unwrap()
                                    .take()
                                {
                                    let _ = child.kill();
                                }
                                return Err(error.into());
                            }
                        };
                    if !wait_ready(url_port(&base), Duration::from_secs(60)) {
                        let _ = ui_child.kill();
                        if let Some(mut child) = app
                            .state::<ManagedChildren>()
                            .backend
                            .lock()
                            .unwrap()
                            .take()
                        {
                            let _ = child.kill();
                        }
                        return Err(std::io::Error::new(
                            std::io::ErrorKind::TimedOut,
                            "desktop UI did not become ready; see ui.stderr.log",
                        )
                        .into());
                    }
                    app.state::<ManagedChildren>()
                        .ui
                        .lock()
                        .unwrap()
                        .replace(ui_child);
                    WebviewUrl::External(base.parse().expect("valid loopback url"))
                }
                // Dev / unbundled: load the Next dev server the developer is running
                // (`pnpm dev`, matching tauri.conf devUrl). No sidecar is spawned.
                None => WebviewUrl::External(
                    "http://127.0.0.1:3000".parse().expect("valid dev url"),
                ),
            };

            WebviewWindowBuilder::new(app, "main", url)
                .title("Local Analytics Copilot")
                .inner_size(1280.0, 832.0)
                .min_inner_size(800.0, 600.0)
                .build()?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building the Local Analytics Copilot desktop application")
        .run(|app, event| {
            // Kill the sidecar when the app exits so no orphan node lingers.
            if let RunEvent::Exit = event {
                let children = app.state::<ManagedChildren>();
                let ui_child = children.ui.lock().unwrap().take();
                if let Some(mut child) = ui_child {
                    let _ = child.kill();
                }
                let backend_child = children.backend.lock().unwrap().take();
                if let Some(mut child) = backend_child {
                    let _ = child.kill();
                }
            }
        });
}

/// Extract the port from a `http://127.0.0.1:PORT` base (built by spawn_sidecar).
fn url_port(base: &str) -> u16 {
    base.rsplit(':').next().and_then(|p| p.parse().ok()).unwrap_or(0)
}
