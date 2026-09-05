use serde::{Deserialize, Serialize};
use std::process::Command;
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

#[tauri::command]
pub fn clean_cache() -> Result<bool, String> {
    let output = Command::new("apt")
        .arg("clean")
        .output()
        .map_err(|e| e.to_string())?;

    Ok(output.status.success())
}

#[tauri::command]
pub fn remove_package(name: String) -> Result<bool, String> {
    let output = Command::new("apt")
        .args(["remove", "-y", "--purge"])
        .arg(name)
        .output()
        .map_err(|e| e.to_string())?;

    Ok(output.status.success())
}

#[tauri::command]
pub fn run_autoremove() -> Result<bool, String> {
    let output = Command::new("apt")
        .args(["autoremove", "-y"])
        .output()
        .map_err(|e| e.to_string())?;

    Ok(output.status.success())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            get_dashboard_stats,
            get_installed_packages,
            clean_cache,
            remove_package,
            run_autoremove
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
}
