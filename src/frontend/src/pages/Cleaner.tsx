import { useEffect, useMemo, useRef, useState } from "react";
import type { CleanerStats } from "../api/cleaner";
import { cleanCache, getCleanerStats, removeOrphans } from "../api/cleaner";
import { formatSize } from "../api/format";
import type { PrivilegeStatus, RecoveryToolStatus } from "../api/safety";
import {
  checkRecoveryTool,
  createRecoveryPoint,
  getPrivilegeStatus,
  requestElevation,
} from "../api/safety";
import { useJournal } from "../context/JournalContext";
import { useToast } from "../context/ToastContext";
import ConfirmOrphansModal from "../components/ConfirmOrphansModal";
import PrivilegeBanner from "../components/PrivilegeBanner";

const RECOVERY_COMMENT = "MCleaner: before removing packages";

const Cleaner = () => {
  const [stats, setStats] = useState<CleanerStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [cleaning, setCleaning] = useState(false);
  const [cacheProgress, setCacheProgress] = useState(0);
  const [cacheMessage, setCacheMessage] = useState("");
  const cacheAbortRef = useRef<AbortController | null>(null);

  const [confirmingOrphans, setConfirmingOrphans] = useState(false);
  const [removingOrphans, setRemovingOrphans] = useState(false);
  const [orphanProgress, setOrphanProgress] = useState(0);
  const [orphanMessage, setOrphanMessage] = useState("");
  const orphansAbortRef = useRef<AbortController | null>(null);

  const [privilege, setPrivilege] = useState<PrivilegeStatus | null>(null);
  const [requestingElevation, setRequestingElevation] = useState(false);
  const [recovery, setRecovery] = useState<RecoveryToolStatus | null>(null);

  const { append, setRunning } = useJournal();
  const { push } = useToast();

  const orphans = stats?.orphans ?? [];
  const totalOrphanSize = useMemo(
    () => orphans.reduce((sum, orphan) => sum + orphan.size, 0),
    [orphans]
  );
  const cacheSize = stats?.cache_size ?? 0;
  const showSkeleton = loading && stats === null;

  useEffect(() => {
    loadStats();
    loadSafety();
  }, []);

  const loadSafety = async () => {
    try {
      const [privilegeStatus, recoveryStatus] = await Promise.all([
        getPrivilegeStatus(),
        checkRecoveryTool(),
      ]);
      setPrivilege(privilegeStatus);
      setRecovery(recoveryStatus);
    } catch (error) {
      console.error("Failed to load safety information:", error);
    }
  };

  const ensureElevated = async (): Promise<boolean> => {
    if (privilege?.elevated) return true;
    setRequestingElevation(true);
    try {
      const next = await requestElevation();
      setPrivilege(next);
      return next.elevated;
    } finally {
      setRequestingElevation(false);
    }
  };

  const requestElevationNow = () => {
    void ensureElevated().then((elevated) => {
      if (!elevated) {
        push("error", "Administrator rights are required to clean the system");
      }
    });
  };

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
    if (!(await ensureElevated())) {
      push("error", "Administrator rights are required to clean the cache");
      return;
    }

    const freed = stats.cache_size;
    const controller = new AbortController();
    cacheAbortRef.current = controller;

    setCleaning(true);
    setCacheProgress(0);
    setCacheMessage("");
    append("$ apt clean", "cmd");
    setRunning("Cleaning cache…");

    const result = await cleanCache(
      (percent, message) => {
        setCacheProgress(percent);
        setCacheMessage(message);
      },
      { signal: controller.signal }
    );

    if (result.aborted) {
      append("Cache clean aborted", "info");
      push("info", "Cache clean aborted");
    } else if (result.success) {
      append(`Cache cleaned · freed ${formatSize(freed)}`, "ok");
      push("success", `Cache cleaned · ${formatSize(freed)} freed`);
    } else {
      append("Cache clean failed", "err");
      push("error", "Cache clean failed");
    }
    setRunning(null);
    setCleaning(false);
    cacheAbortRef.current = null;
    await loadStats();
  };

  const handleAbortClean = () => {
    cacheAbortRef.current?.abort();
  };

  const handleConfirmRemoveOrphans = async () => {
    if (!(await ensureElevated())) {
      push("error", "Administrator rights are required to remove packages");
      return;
    }

    if (recovery?.available) {
      append(`$ ${recovery.command ?? recovery.tool}`, "cmd");
      const point = await createRecoveryPoint(RECOVERY_COMMENT);
      if (point.success) {
        append(`Recovery point created (${point.tool ?? recovery.tool})`, "ok");
      } else {
        append(`Failed to create recovery point: ${point.message}`, "err");
      }
    }

    const controller = new AbortController();
    orphansAbortRef.current = controller;

    setRemovingOrphans(true);
    setOrphanProgress(0);
    setOrphanMessage("");
    append("$ apt autoremove -y", "cmd");
    setRunning("Removing orphaned packages…");

    const result = await removeOrphans(
      (percent, message) => {
        setOrphanProgress(percent);
        setOrphanMessage(message);
      },
      { signal: controller.signal }
    );

    if (result.aborted) {
      append("Orphan removal aborted", "info");
      push("info", "Operation aborted");
    } else if (result.success) {
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
    orphansAbortRef.current = null;
    await loadStats();
  };

  const handleAbortOrphans = () => {
    orphansAbortRef.current?.abort();
  };

  const showEmptyOrphans = !loading && orphans.length === 0;

  return (
    <div>
      <h1 className="page-title">Cleaner</h1>
      <p className="page-subtitle">Clean system junk and orphaned packages</p>

      <PrivilegeBanner
        elevated={privilege?.elevated ?? true}
        requesting={requestingElevation}
        onRequest={requestElevationNow}
      />

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
            {showSkeleton ? (
              <>
                <div className="loading-skeleton skeleton-value" data-testid="cleaner-skeleton" style={{ width: "45%" }}></div>
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
                <div className="progress-row">
                  <span className="progress-label" data-testid="clean-progress-label">
                    {cacheMessage || "Cleaning…"} · {cacheProgress}%
                  </span>
                  <button
                    className="btn btn-secondary btn-sm progress-abort"
                    data-testid="abort-cache-clean"
                    onClick={handleAbortClean}
                  >
                    Abort
                  </button>
                </div>
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
            {showSkeleton ? (
              <>
                <div className="loading-skeleton skeleton-value" data-testid="cleaner-skeleton" style={{ width: "55%" }}></div>
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

          {showSkeleton && (
            <ul className="orphan-list" data-testid="orphans-list-skeleton" aria-hidden="true">
              {[0, 1, 2].map((row) => (
                <li className="orphan-skeleton-row" key={row}>
                  <div className="loading-skeleton skeleton-text" style={{ marginBottom: 0 }}></div>
                  <div className="loading-skeleton skeleton-text" style={{ width: 48, height: 12, marginBottom: 0 }}></div>
                  <div className="loading-skeleton skeleton-text" style={{ width: 56, marginBottom: 0 }}></div>
                </li>
              ))}
            </ul>
          )}

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
                <div className="progress-row">
                  <span className="progress-label" data-testid="orphan-progress-label">
                    {orphanMessage || "Removing…"} · {orphanProgress}%
                  </span>
                </div>
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
          recovery={recovery}
          onConfirm={handleConfirmRemoveOrphans}
          onCancel={() => setConfirmingOrphans(false)}
          onAbort={handleAbortOrphans}
        />
      )}
    </div>
  );
};

export default Cleaner;
