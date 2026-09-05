import { useEffect } from "react";
import type { InstalledPackage } from "../api/packages";
import { formatSize } from "../api/format";

interface ConfirmRemoveModalProps {
  pkg: InstalledPackage;
  removing: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmRemoveModal = ({
  pkg,
  removing,
  error,
  onConfirm,
  onCancel,
}: ConfirmRemoveModalProps) => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !removing) onCancel();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [removing, onCancel]);

  const dependencyCount = pkg.dependencies.length;

  return (
    <div className="modal-overlay" onClick={removing ? undefined : onCancel}>
      <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="modal-icon danger">🗑️</div>
        <h2 className="modal-title">Remove package</h2>
        <p className="modal-text">
          You are about to remove{" "}
          <strong className="pkg-name">{pkg.name}</strong>{" "}
          <span className="pkg-version">{pkg.version}</span>.
        </p>

        <div className="modal-facts">
          <div className="modal-fact">
            <span className="modal-fact-label">Size</span>
            <span className="modal-fact-value">{formatSize(pkg.size)}</span>
          </div>
          <div className="modal-fact">
            <span className="modal-fact-label">Dependencies</span>
            <span className="modal-fact-value">
              {dependencyCount > 0 ? `${dependencyCount} will be cleaned by autoremove` : "None"}
            </span>
          </div>
        </div>

        {error && <div className="toast toast-error">{error}</div>}

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onCancel} disabled={removing}>
            Cancel
          </button>
          <button
            className="btn btn-danger"
            onClick={onConfirm}
            disabled={removing}
            data-testid="confirm-remove"
          >
            {removing ? "Removing..." : "Remove package"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmRemoveModal;
