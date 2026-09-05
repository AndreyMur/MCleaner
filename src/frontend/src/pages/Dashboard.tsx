import { useState, useEffect } from "react";

interface DashboardStats {
  cache_size: number;
  package_count: number;
  os_name: string;
}

const Dashboard = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [cleaning, setCleaning] = useState(false);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    setLoading(true);
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const data = await invoke<DashboardStats>("get_dashboard_stats");
      setStats(data);
    } catch (error) {
      console.error("Failed to load stats:", error);
      setStats({ cache_size: 0, package_count: 0, os_name: "Linux" });
    } finally {
      setLoading(false);
    }
  };

  const handleCleanCache = async () => {
    setCleaning(true);
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("clean_cache");
      await loadStats();
    } catch (error) {
      console.error("Failed to clean cache:", error);
    } finally {
      setCleaning(false);
    }
  };

  const formatSize = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  return (
    <div>
      <h1 className="page-title">Dashboard</h1>
      <p className="page-subtitle">System overview and quick actions</p>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-header">
            <div>
              <div className="stat-card-icon blue">💾</div>
            </div>
          </div>
          {loading ? (
            <>
              <div className="loading-skeleton skeleton-value"></div>
              <div className="loading-skeleton skeleton-text" style={{ width: "80%" }}></div>
            </>
          ) : (
            <>
              <div className="stat-card-value">{formatSize(stats?.cache_size || 0)}</div>
              <div className="stat-card-label">Cache Size</div>
            </>
          )}
          <div className="stat-card-action">
            <button
              className="btn btn-primary"
              onClick={handleCleanCache}
              disabled={loading || cleaning}
            >
              {cleaning ? "Cleaning..." : "Clean Cache"}
            </button>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <div>
              <div className="stat-card-icon green">📦</div>
            </div>
          </div>
          {loading ? (
            <>
              <div className="loading-skeleton skeleton-value"></div>
              <div className="loading-skeleton skeleton-text" style={{ width: "60%" }}></div>
            </>
          ) : (
            <>
              <div className="stat-card-value">{stats?.package_count || 0}</div>
              <div className="stat-card-label">Installed Packages</div>
            </>
          )}
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <div>
              <div className="stat-card-icon orange">🖥️</div>
            </div>
          </div>
          {loading ? (
            <>
              <div className="loading-skeleton skeleton-value"></div>
              <div className="loading-skeleton skeleton-text" style={{ width: "70%" }}></div>
            </>
          ) : (
            <>
              <div className="stat-card-value" style={{ fontSize: "24px" }}>{stats?.os_name || "Unknown"}</div>
              <div className="stat-card-label">Operating System</div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
