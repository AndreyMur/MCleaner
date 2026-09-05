use serde::{Deserialize, Serialize};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use sysinfo::System;

#[derive(Debug, Serialize, Deserialize)]
pub struct PackageInfo {
    name: String,
    version: String,
    size: u64,
    description: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DashboardStats {
    cache_size: u64,
    package_count: u64,
    os_name: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PrivilegeStatus {
    elevated: bool,
    os: String,
    method: String,
    user: String,
}

const DEFAULT_OPERATION_TIMEOUT_SECS: u64 = 300;

static CANCEL_REQUESTED: AtomicBool = AtomicBool::new(false);
static CURRENT_PID: Mutex<Option<u32>> = Mutex::new(None);

#[tauri::command]
pub fn get_dashboard_stats() -> Result<DashboardStats, String> {
    let cache_size = get_apt_cache_size();
    let package_count = get_apt_package_count();
    let os_name = System::name().unwrap_or_else(|| "Unknown".to_string());

    Ok(DashboardStats {
        cache_size,
        package_count,
        os_name,
    })
}

fn get_apt_cache_size() -> u64 {
    let output = Command::new("du")
        .args(["-sb", "/var/cache/apt/archives"])
        .output();

    match output {
        Ok(out) => {
            let stdout = String::from_utf8_lossy(&out.stdout);
            stdout
                .split_whitespace()
                .next()
                .and_then(|s| s.parse::<u64>().ok())
                .unwrap_or(0)
        }
        Err(_) => 0,
    }
}

fn get_apt_package_count() -> u64 {
    let output = Command::new("apt")
        .args(["list", "--installed", "--quiet=2"])
        .output();

    match output {
        Ok(out) => {
            let stdout = String::from_utf8_lossy(&out.stdout);
            stdout.lines().filter(|l| l.contains('/')).count() as u64
        }
        Err(_) => 0,
    }
}

#[tauri::command]
pub fn get_installed_packages() -> Vec<PackageInfo> {
    let output = Command::new("apt")
        .args(["list", "--installed", "--quiet=2"])
        .output();

    match output {
        Ok(out) => {
            let stdout = String::from_utf8_lossy(&out.stdout);
            stdout
                .lines()
                .filter(|line| line.contains('/'))
                .filter_map(|line| {
                    let name = line.split('/').next()?.to_string();
                    let version = line
                        .split_whitespace()
                        .find(|s| s.starts_with('['))
                        .map(|s| s.replace("[installed,", "").replace("]", ""))
                        .unwrap_or_default();
                    Some(PackageInfo {
                        name,
                        version,
                        size: 0,
                        description: String::new(),
                    })
                })
                .collect()
        }
        Err(_) => Vec::new(),
    }
}

// ---------------------------------------------------------------------------
// Privilege elevation (issue: seamless UAC / polkit)
//
// The app stays unprivileged until a privileged command is about to run.
// Linux commands are transparently wrapped with `pkexec` (polkit prompt),
// Windows relaunches through PowerShell `Start-Process -Verb RunAs` (UAC)
// and macOS re-launches through `osascript ... with administrator
// privileges`.
// ---------------------------------------------------------------------------

fn platform_id() -> &'static str {
    #[cfg(target_os = "windows")]
    {
        "windows"
    }
    #[cfg(target_os = "macos")]
    {
        "macos"
    }
    #[cfg(target_os = "linux")]
    {
        "linux"
    }
    #[cfg(not(any(target_os = "windows", target_os = "macos", target_os = "linux")))]
    {
        "unknown"
    }
}

fn program_exists(program: &str) -> bool {
    let result = if cfg!(target_os = "windows") {
        Command::new("where").arg(program).output()
    } else {
        Command::new("which").arg(program).output()
    };
    matches!(result, Ok(out) if out.status.success())
}

fn current_user() -> String {
    #[cfg(target_os = "windows")]
    {
        std::env::var("USERNAME").unwrap_or_default()
    }
    #[cfg(not(target_os = "windows"))]
    {
        std::env::var("USER").unwrap_or_default()
    }
}

#[cfg(any(target_os = "linux", target_os = "macos"))]
fn current_uid_is_zero() -> bool {
    match Command::new("id").args(["-u"]).output() {
        Ok(out) => {
            out.status.success() && String::from_utf8_lossy(&out.stdout).trim() == "0"
        }
        Err(_) => false,
    }
}

fn is_elevated() -> bool {
    #[cfg(target_os = "windows")]
    {
        true
    }
    #[cfg(any(target_os = "linux", target_os = "macos"))]
    {
        current_uid_is_zero()
    }
    #[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
    {
        true
    }
}

fn privilege_status_struct() -> PrivilegeStatus {
    let elevated = is_elevated();
    let method = if !elevated {
        "user"
    } else if cfg!(target_os = "windows") {
        "admin"
    } else {
        "root"
    };
    PrivilegeStatus {
        elevated,
        os: platform_id().to_string(),
        method: method.to_string(),
        user: current_user(),
    }
}

#[tauri::command]
pub fn get_privilege_status() -> PrivilegeStatus {
    privilege_status_struct()
}

fn request_elevation_impl() {
    let exe = std::env::current_exe().ok();

    #[cfg(target_os = "windows")]
    {
        if let Some(exe) = exe {
            let path = exe.to_string_lossy().replace('\'', "''");
            let script = format!("Start-Process -FilePath '{}' -Verb RunAs", path);
            let _ = Command::new("powershell")
                .args(["-NoProfile", "-WindowStyle", "Hidden", "-Command", &script])
                .spawn();
        }
    }

    #[cfg(target_os = "linux")]
    {
        if program_exists("pkexec") {
            if let Some(exe) = exe {
                let _ = Command::new("pkexec").arg(&exe).spawn();
            }
        }
    }

    #[cfg(target_os = "macos")]
    {
        if let Some(exe) = exe {
            let path = exe.to_string_lossy().replace('\'', "''");
            let script = format!("do shell script \"'{}'\" with administrator privileges", path);
            let _ = Command::new("osascript").args(["-e", &script]).spawn();
        }
    }
}

#[tauri::command]
pub fn request_elevation() -> PrivilegeStatus {
    if !is_elevated() {
        request_elevation_impl();
    }
    privilege_status_struct()
}

/// Resolve the actual argv to run for `program` taking the current
/// privilege state into account (e.g. prefix `pkexec` on Linux).
fn command_line(program: &str, args: &[&str]) -> Vec<String> {
    let mut command: Vec<String> = Vec::with_capacity(args.len() + 2);
    #[cfg(target_os = "linux")]
    if !is_elevated() && program_exists("pkexec") {
        command.push("pkexec".to_string());
    }
    command.push(program.to_string());
    command.extend(args.iter().map(|arg| arg.to_string()));
    command
}

/// Run a command with a hard deadline while recording the active pid so the
/// operation can be interrupted through :func:`abort_operation`.
fn run_managed(command: &[String], timeout: Duration) -> Result<std::process::Output, String> {
    if command.is_empty() {
        return Err("empty command".to_string());
    }
    CANCEL_REQUESTED.store(false, Ordering::SeqCst);

    let mut child = Command::new(&command[0])
        .args(&command[1..])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to start {}: {}", command[0], e))?;

    *CURRENT_PID.lock().unwrap() = Some(child.id());

    let deadline = Instant::now() + timeout;
    let outcome = loop {
        if CANCEL_REQUESTED.load(Ordering::SeqCst) {
            let _ = child.kill();
            let _ = child.wait();
            break Err("operation aborted".to_string());
        }
        match child.try_wait() {
            Ok(Some(_)) => {
                let output = child.wait_with_output().map_err(|e| e.to_string())?;
                break Ok(output);
            }
            Ok(None) => {
                if Instant::now() >= deadline {
                    let _ = child.kill();
                    let _ = child.wait();
                    break Err("operation timed out".to_string());
                }
                std::thread::sleep(Duration::from_millis(100));
            }
            Err(e) => {
                let _ = child.kill();
                let _ = child.wait();
                break Err(e.to_string());
            }
        }
    };

    *CURRENT_PID.lock().unwrap() = None;
    CANCEL_REQUESTED.store(false, Ordering::SeqCst);
    outcome
}

/// Run a command honouring the seamless elevation wrapper with a timeout.
fn apt_managed_success(args: Vec<String>) -> Result<bool, String> {
    let output = run_managed(&args, Duration::from_secs(DEFAULT_OPERATION_TIMEOUT_SECS))?;
    Ok(output.status.success())
}

#[tauri::command]
pub async fn clean_cache() -> Result<bool, String> {
    tauri::async_runtime::spawn_blocking(|| {
        apt_managed_success(command_line("apt", &["clean"]))
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub async fn remove_package(name: String) -> Result<bool, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let command = command_line("apt", &["remove", "-y", "--purge", name.as_str()]);
        apt_managed_success(command)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub async fn run_autoremove() -> Result<bool, String> {
    tauri::async_runtime::spawn_blocking(|| {
        apt_managed_success(command_line("apt", &["autoremove", "-y"]))
    })
    .await
    .map_err(|e| e.to_string())?
}

/// Ask the currently running (long) operation to stop.
///
/// The managed runner polls this flag and kills its child within ~100ms, so
/// no stale process ids are ever touched from here.
#[tauri::command]
pub fn abort_operation() -> bool {
    let had_active = CURRENT_PID.lock().unwrap().is_some();
    CANCEL_REQUESTED.store(true, Ordering::SeqCst);
    had_active
}

// ---------------------------------------------------------------------------
// Recovery points (Timeshift / System Restore / Time Machine)
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize, Deserialize)]
pub struct RecoveryInfo {
    available: bool,
    tool: Option<String>,
    command: Option<String>,
    hint: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct RecoveryPointResult {
    success: bool,
    tool: Option<String>,
    message: String,
}

fn powershell_script_ok(script: &str) -> bool {
    let output = Command::new("powershell")
        .args(["-NoProfile", "-NonInteractive", "-Command", script])
        .output();
    matches!(
        output,
        Ok(out) if String::from_utf8_lossy(&out.stdout).to_lowercase().contains("ok")
    )
}

#[tauri::command]
pub fn check_recovery_tool() -> RecoveryInfo {
    match platform_id() {
        "windows" => {
            let probe =
                "try { $null = Get-ComputerRestorePoint -ErrorAction Stop; 'ok' } catch { 'no' }";
            let available = powershell_script_ok(probe);
            RecoveryInfo {
                available,
                tool: if available { Some("System Restore".to_string()) } else { None },
                command: if available {
                    Some(
                        "Checkpoint-Computer -Description 'MCleaner safety' \
                         -RestorePointType MODIFY_SETTINGS"
                            .to_string(),
                    )
                } else {
                    None
                },
                hint: None,
            }
        }
        "linux" => {
            let available = program_exists("timeshift");
            RecoveryInfo {
                available,
                tool: if available { Some("Timeshift".to_string()) } else { None },
                command: if available {
                    Some(
                        "timeshift --create --comments \"MCleaner: before removing packages\" --yes"
                            .to_string(),
                    )
                } else {
                    None
                },
                hint: None,
            }
        }
        "macos" => {
            let available = program_exists("tmutil");
            RecoveryInfo {
                available,
                tool: if available { Some("Time Machine".to_string()) } else { None },
                command: if available {
                    Some("tmutil localsnapshot".to_string())
                } else {
                    None
                },
                hint: None,
            }
        }
        _ => RecoveryInfo {
            available: false,
            tool: None,
            command: None,
            hint: Some("unsupported platform".to_string()),
        },
    }
}

#[tauri::command]
pub async fn create_recovery_point(comment: String) -> Result<RecoveryPointResult, String> {
    let info = check_recovery_tool();
    if !info.available {
        return Ok(RecoveryPointResult {
            success: false,
            tool: None,
            message: "No recovery tool detected (Timeshift / System Restore / Time Machine)."
                .to_string(),
        });
    }

    let command: Vec<String> = match platform_id() {
        "windows" => vec![
            "powershell".to_string(),
            "-NoProfile".to_string(),
            "-NonInteractive".to_string(),
            "-Command".to_string(),
            format!(
                "Checkpoint-Computer -Description '{}' -RestorePointType MODIFY_SETTINGS",
                comment.replace('\'', "''")
            ),
        ],
        "linux" => command_line(
            "timeshift",
            &["--create", "--comments", comment.as_str(), "--yes"],
        ),
        "macos" => vec!["tmutil".to_string(), "localsnapshot".to_string(), comment],
        _ => return Err("unsupported platform".to_string()),
    };

    let tool = info.tool.clone();
    let timeout = Duration::from_secs(600);
    tauri::async_runtime::spawn_blocking(move || {
        let output = run_managed(&command, timeout)?;
        Ok(RecoveryPointResult {
            success: output.status.success(),
            tool,
            message: if output.status.success() {
                "Recovery point created".to_string()
            } else {
                "Recovery point creation failed".to_string()
            },
        })
    })
    .await
    .map_err(|e| e.to_string())?
}

fn get_apt_orphans() -> Vec<PackageInfo> {
    match Command::new("apt-get")
        .args(["--simulate", "autoremove", "-y"])
        .output()
    {
        Ok(out) => {
            let stdout = String::from_utf8_lossy(&out.stdout);
            let stderr = String::from_utf8_lossy(&out.stderr);
            let text = format!("{stdout}\n{stderr}");

            text.lines()
                .filter_map(|line| {
                    let trimmed = line.trim_start();
                    let rest = trimmed.strip_prefix("Remv ")?;
                    let name = rest.split_whitespace().next()?.to_string();
                    Some(PackageInfo {
                        name,
                        version: String::new(),
                        size: 0,
                        description: String::new(),
                    })
                })
                .collect()
        }
        Err(_) => Vec::new(),
    }
}

#[tauri::command]
pub fn get_orphaned_packages() -> Vec<PackageInfo> {
    get_apt_orphans()
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            get_dashboard_stats,
            get_installed_packages,
            clean_cache,
            remove_package,
            run_autoremove,
            get_orphaned_packages,
            get_privilege_status,
            request_elevation,
            abort_operation,
            check_recovery_tool,
            create_recovery_point
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dashboard_stats_structure() {
        let stats = DashboardStats {
            cache_size: 1024,
            package_count: 100,
            os_name: "Linux".to_string(),
        };
        assert_eq!(stats.cache_size, 1024);
        assert_eq!(stats.package_count, 100);
    }

    #[test]
    fn test_package_info_structure() {
        let pkg = PackageInfo {
            name: "vim".to_string(),
            version: "2:8.2".to_string(),
            size: 2048,
            description: "".to_string(),
        };
        assert_eq!(pkg.name, "vim");
    }

    #[test]
    fn test_platform_id_is_known() {
        let id = platform_id();
        assert!(matches!(id, "windows" | "macos" | "linux" | "unknown"));
    }

    #[test]
    fn test_privilege_status_structure() {
        let status = privilege_status_struct();
        assert_eq!(status.os, platform_id());
        assert!(!status.user.is_empty() || status.os != "unknown");
    }

    #[test]
    fn test_managed_operation_enforces_timeout() {
        let command: Vec<String> = if cfg!(target_os = "windows") {
            vec![
                "powershell".to_string(),
                "-NoProfile".to_string(),
                "-Command".to_string(),
                "Start-Sleep -Seconds 5".to_string(),
            ]
        } else {
            vec!["sleep".to_string(), "5".to_string()]
        };

        let result = run_managed(&command, Duration::from_millis(200));

        assert!(result.is_err());
        assert!(result.unwrap_err().contains("timed out"));
    }

    #[test]
    fn test_empty_command_is_rejected() {
        let command: Vec<String> = Vec::new();
        let result = run_managed(&command, Duration::from_secs(1));
        assert!(result.is_err());
    }
}
