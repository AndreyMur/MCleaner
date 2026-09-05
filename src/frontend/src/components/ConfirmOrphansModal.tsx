import { useEffect } from "react";
import type { OrphanedPackage } from "../api/cleaner";
import type { RecoveryToolStatus } from "../api/safety";
import { formatSize } from "../api/format";
import { useHoldConfirm } from "../hooks/useHoldConfirm";

interface ConfirmOrphansModalProps {
  orphans: OrphanedPackage[];
  totalSize: number;
  removing: boolean;
  recovery?: RecoveryToolStatus | null;
  onConfirm: () => void;
  onCancel: () => void;
  onAbort?: () => void;
}

const HOLD_SECONDS = 5;

const ConfirmOrphansModal = ({
  orphans,
  totalSize,
  removing,
  recovery,
  onConfirm,
  onCancel,
  onAbort,
}: ConfirmOrphansModalProps) => {
  const { held, remaining } = useHoldConfirm(HOLD_SECONDS);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !removing) onCancel();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [removing, onCancel]);

  return (
    <div className="modal-overlay" onClick={removing ? undefined : onCancel}>
      <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="modal-icon danger">🧹</div>
        <h2 className="modal-title">Remove orphaned packages</h2>
        <p className="modal-text">
          These packages were installed automatically as dependencies but are no longer
          required by any installed package. They will be removed with{" "}
          <strong>apt autoremove</strong>.
        </p>

        <ul className="orphan-list modal-orphan-list" data-testid="modal-orphan-list">
          {orphans.map((orphan) => (
            <li className="orphan-row" data-orphan={orphan.name} key={orphan.name}>
              <div className="orphan-name">{orphan.name}</div>
              <div className="orphan-version">{orphan.version}</div>
              <div className="orphan-size">{formatSize(orphan.size)}</div>
            </li>
          ))}
        </ul>

        <div className="modal-facts">
          <div className="modal-fact">
            <span className="modal-fact-label">Packages</span>
            <span className="modal-fact-value">{orphans.length}</span>
          </div>
          <div className="modal-fact">
            <span className="modal-fact-label">Total size</span>
            <span className="modal-fact-value">{formatSize(totalSize)}</span>
          </div>
        </div>

        <div className="modal-hold" data-testid="confirm-hold">
          {removing ? (
            <span>Removing orphaned packages…</span>
          ) : !held ? (
            <span>
              ⏳ Safety hold — confirm in <strong>{remaining}s</strong>. You can still
              cancel.
            </span>
          ) : (
            <span>Confirmation window passed — removal can proceed.</span>
          )}
        </div>

        {recovery && (
          recovery.available ? (
            <div className="modal-recovery available" data-testid="modal-recovery">
              <span className="modal-recovery-icon">🛡️</span>
              <p>
                <strong>{recovery.tool}</strong> is available — a snapshot will be
                recorded before the packages are removed.
              </p>
            </div>
          ) : (
            <div className="modal-recovery missing" data-testid="modal-recovery">
              <span className="modal-recovery-icon">⚠️</span>
              <p>
                No recovery tool detected — consider creating a manual backup before
                continuing.
              </p>
            </div>
          )
        )}

        <div className="modal-actions">
          {removing && onAbort ? (
            <button
              className="btn btn-secondary"
              onClick={onAbort}
              data-testid="abort-orphan-removal"
            >
              Abort
            </button>
          ) : (
            <button className="btn btn-secondary" onClick={onCancel} disabled={removing}>
              Cancel
            </button>
          )}
          <button
            className="btn btn-danger"
            onClick={onConfirm}
            disabled={removing || !held}
            data-testid="confirm-orphans-removal"
          >
            {removing ? "Removing…" : "Remove orphans"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmOrphansModal;
