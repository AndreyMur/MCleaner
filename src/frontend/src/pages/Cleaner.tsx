import { useEffect, useMemo, useState } from "react";
import type { CleanerStats } from "../api/cleaner";
import { cleanCache, getCleanerStats, removeOrphans } from "../api/cleaner";
import { formatSize } from "../api/format";
import { useJournal } from "../context/JournalContext";
import { useToast } from "../context/ToastContext";
import ConfirmOrphansModal from "../components/ConfirmOrphansModal";

const Cleaner = () => {
  const [stats, setStats] = useState<CleanerStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [cleaning, setCleaning] = useState(false);
  const [cacheProgress, setCacheProgress] = useState(0);
  const [cacheMessage, setCacheMessage] = useState("");

  const [confirmingOrphans, setConfirmingOrphans] = useState(false);
  const [removingOrphans, setRemovingOrphans] = useState(false);
  const [orphanProgress, setOrphanProgress] = useState(0);
  const [orphanMessage, setOrphanMessage] = useState("");

  const { append, setRunning } = useJournal();
  const { push } = useToast();

  const orphans = stats?.orphans ?? [];
  const totalOrphanSize = useMemo(
    () => orphans.reduce((sum, orphan) => sum + orphan.size, 0),
    [orphans]
  );
  const cacheSize = stats?.cache_size ?? 0;

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await getCleanerStats();
      setStats(data);
    } catch (error) {
      console.error("Failed to load cleaner stats:", error);
      setLoadError("Failed to load cleaner information.");
    } finally {
      setLoading(false);
    }
  };

  const handleCleanCache = async () => {
    if (!stats || stats.cache_size === 0) return;
    const freed = stats.cache_size;
    setCleaning(true);
    setCacheProgress(0);
    setCacheMessage("");
    append("$ apt clean", "cmd");
    setRunning("Cleaning cache…");

    const result = await cleanCache((percent, message) => {
      setCacheProgress(percent);
      setCacheMessage(message);
    });

    if (result.success) {
      append(`Cache cleaned · freed ${formatSize(freed)}`, "ok");
      push("success", `Cache cleaned · ${formatSize(freed)} freed`);
    } else {
      append("Cache clean failed", "err");
      push("error", "Cache clean failed");
    }
    setRunning(null);
    setCleaning(false);
    await loadStats();
  };

  const handleConfirmRemoveOrphans = async () => {
    setRemovingOrphans(true);
    setOrphanProgress(0);
    setOrphanMessage("");
    append("$ apt autoremove -y", "cmd");
    setRunning("Removing orphaned packages…");

    const result = await removeOrphans((percent, message) => {
      setOrphanProgress(percent);
      setOrphanMessage(message);
    });

    if (result.success) {
      append(
        `Removed ${result.removed.length} orphaned packages: ${result.removed.join(", ")}`,
        "ok"
      );
      push("success", `${result.removed.length} orphaned packages removed`);
    } else {
      append("Failed to remove orphaned packages", "err");
      push("error", "Failed to remove orphaned packages");
    }
    setRunning(null);
    setRemovingOrphans(false);
    setConfirmingOrphans(false);
    await loadStats();
  };

  const showEmptyOrphans = !loading && orphans.length === 0;

  return (
    <div>
      <h1 className="page-title">Cleaner</h1>
      <p className="page-subtitle">Clean system junk and orphaned packages</p>

      {loadError && <div className="toast toast-error">{loadError}</div>}

      <div className="cleaner-grid">
        <section className="cleaner-card" data-testid="cache-card">
          <div className="cleaner-card-header">
            <div className="cleaner-card-icon blue">💾</div>
            <div>
              <h2 className="cleaner-card-title">Package cache</h2>
              <p className="cleaner-card-subtitle">
                Downloaded archives that can be safely removed
              </p>
            </div>
          </div>

          <div className="cleaner-card-body">
            {loading ? (
              <>
                <div className="loading-skeleton skeleton-value"></div>
                <div className="loading-skeleton skeleton-text" style={{ width: "70%" }}></div>
              </>
            ) : (
              <>
                <div className="cleaner-value" data-testid="cache-size">
                  {formatSize(cacheSize)}
                </div>
                <div className="cleaner-label">Occupied cache space</div>
              </>
            )}
          </div>

          <div className="cleaner-card-actions">
            <button
              className="btn btn-primary"
              data-testid="clean-cache"
              onClick={handleCleanCache}
              disabled={loading || cleaning || cacheSize === 0}
            >
              {cleaning ? "Cleaning…" : "Clean cache"}
            </button>
            {cleaning && (
              <div className="progress-block" data-testid="clean-progress-block">
                <div
                  className="progress"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={cacheProgress}
                  data-testid="clean-progress"
                >
                  <div
                    className="progress-fill"
                    style={{ width: `${cacheProgress}%` }}
                  ></div>
                </div>
                <span className="progress-label" data-testid="clean-progress-label">
                  {cacheMessage || "Cleaning…"} · {cacheProgress}%
                </span>
              </div>
            )}
          </div>
        </section>

        <section className="cleaner-card" data-testid="orphans-card">
          <div className="cleaner-card-header">
            <div className="cleaner-card-icon red">🗑️</div>
            <div>
              <h2 className="cleaner-card-title">Orphaned packages</h2>
              <p className="cleaner-card-subtitle">
                Dependencies no longer required by any installed package
              </p>
            </div>
          </div>

          <div className="cleaner-card-body">
            {loading ? (
              <>
                <div className="loading-skeleton skeleton-value"></div>
                <div className="loading-skeleton skeleton-text" style={{ width: "80%" }}></div>
              </>
            ) : (
              <>
                <div className="cleaner-value" data-testid="orphans-summary">
                  {orphans.length === 0 ? "0 packages" : `${orphans.length} packages`}
                </div>
                <div className="cleaner-label" data-testid="orphans-size">
                  {orphans.length === 0
                    ? "Nothing to clean"
                    : `${formatSize(totalOrphanSize)} reclaimable`}
                </div>
              </>
            )}
          </div>

          {!loading && orphans.length > 0 && (
            <ul className="orphan-list" data-testid="orphans-list">
              {orphans.map((orphan) => (
                <li className="orphan-row" data-orphan={orphan.name} key={orphan.name}>
                  <div className="orphan-name">{orphan.name}</div>
                  <div className="orphan-version">{orphan.version}</div>
                  <div className="orphan-size">{formatSize(orphan.size)}</div>
                </li>
              ))}
            </ul>
          )}

          {showEmptyOrphans && (
            <div className="orphans-empty" data-testid="orphans-empty">
              <div className="empty-state-icon">🎉</div>
              <p className="empty-state-title">No orphaned packages</p>
              <p className="empty-state-text">
                Your system dependencies are all in use.
              </p>
            </div>
          )}

          <div className="cleaner-card-actions">
            <button
              className="btn btn-danger"
              data-testid="remove-orphans"
              onClick={() => setConfirmingOrphans(true)}
              disabled={loading || removingOrphans || orphans.length === 0}
            >
              {removingOrphans
                ? "Removing…"
                : orphans.length > 0
                ? `Remove orphans (${orphans.length})`
                : "Remove orphans"}
            </button>
            {removingOrphans && (
              <div className="progress-block" data-testid="orphan-progress-block">
                <div
                  className="progress"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={orphanProgress}
                  data-testid="orphan-progress"
                >
                  <div
                    className="progress-fill"
                    style={{ width: `${orphanProgress}%` }}
                  ></div>
                </div>
                <span className="progress-label" data-testid="orphan-progress-label">
                  {orphanMessage || "Removing…"} · {orphanProgress}%
                </span>
              </div>
            )}
          </div>
        </section>
      </div>

      {confirmingOrphans && orphans.length > 0 && (
        <ConfirmOrphansModal
          orphans={orphans}
          totalSize={totalOrphanSize}
          removing={removingOrphans}
          onConfirm={handleConfirmRemoveOrphans}
          onCancel={() => setConfirmingOrphans(false)}
        />
      )}
    </div>
  );
};

export default Cleaner;
