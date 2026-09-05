import { useEffect } from "react";
import type { OrphanedPackage } from "../api/cleaner";
import { formatSize } from "../api/format";

interface ConfirmOrphansModalProps {
  orphans: OrphanedPackage[];
  totalSize: number;
  removing: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmOrphansModal = ({
  orphans,
  totalSize,
  removing,
  onConfirm,
  onCancel,
}: ConfirmOrphansModalProps) => {
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

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onCancel} disabled={removing}>
            Cancel
          </button>
          <button
            className="btn btn-danger"
            onClick={onConfirm}
            disabled={removing}
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
