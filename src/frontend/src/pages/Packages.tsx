import { useEffect, useMemo, useState } from "react";
import type { InstalledPackage } from "../api/packages";
import {
  getInstalledPackages,
  removePackage,
  runAutoremove,
} from "../api/packages";
import {
  formatDate,
  formatSize,
  daysSince,
  sizeCategory,
} from "../api/format";
import { useJournal } from "../context/JournalContext";
import { useToast } from "../context/ToastContext";
import ConfirmRemoveModal from "../components/ConfirmRemoveModal";

type SizeFilter = "all" | "small" | "medium" | "large";
type DateFilter = "all" | "recent7" | "recent30" | "older30";
type SortBy = "name" | "size" | "date";

const SIZE_FILTERS: { value: SizeFilter; label: string }[] = [
  { value: "all", label: "Any size" },
  { value: "small", label: "< 1 MB" },
  { value: "medium", label: "1 - 50 MB" },
  { value: "large", label: "> 50 MB" },
];

const DATE_FILTERS: { value: DateFilter; label: string }[] = [
  { value: "all", label: "Any date" },
  { value: "recent7", label: "Last 7 days" },
  { value: "recent30", label: "Last 30 days" },
  { value: "older30", label: "Older than 30 days" },
];

const SORT_OPTIONS: { value: SortBy; label: string }[] = [
  { value: "name", label: "Name (A-Z)" },
  { value: "size", label: "Size (largest)" },
  { value: "date", label: "Recently installed" },
];

const Packages = () => {
  const [packages, setPackages] = useState<InstalledPackage[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [sizeFilter, setSizeFilter] = useState<SizeFilter>("all");
  const [dateFilter, setDateFilter] = useState<DateFilter>("all");
  const [sortBy, setSortBy] = useState<SortBy>("name");

  const [expanded, setExpanded] = useState<string | null>(null);
  const [pendingRemove, setPendingRemove] = useState<InstalledPackage | null>(null);
  const [removing, setRemoving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const { append, setRunning } = useJournal();
  const { push } = useToast();

  useEffect(() => {
    loadPackages();
  }, []);

  const loadPackages = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await getInstalledPackages();
      setPackages(data);
    } catch (error) {
      console.error("Failed to load packages:", error);
      setLoadError("Failed to load installed packages.");
      setPackages([]);
    } finally {
      setLoading(false);
    }
  };

  const filtered = useMemo(() => {
    if (!packages) return [];
    const query = search.trim().toLowerCase();

    return packages
      .filter((pkg) => {
        if (query && !`${pkg.name} ${pkg.description}`.toLowerCase().includes(query)) {
          return false;
        }
        if (sizeFilter !== "all" && sizeCategory(pkg.size) !== sizeFilter) {
          return false;
        }
        if (dateFilter !== "all") {
          const days = daysSince(pkg.installed_at);
          if (dateFilter === "recent7" && days > 7) return false;
          if (dateFilter === "recent30" && days > 30) return false;
          if (dateFilter === "older30" && days <= 30) return false;
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === "size") return b.size - a.size;
        if (sortBy === "date") return daysSince(a.installed_at) - daysSince(b.installed_at);
        return a.name.localeCompare(b.name);
      });
  }, [packages, search, sizeFilter, dateFilter, sortBy]);

  const toggleExpand = (name: string) => {
    setExpanded((current) => (current === name ? null : name));
  };

  const requestRemove = (pkg: InstalledPackage) => {
    setActionError(null);
    setPendingRemove(pkg);
  };

  const handleConfirmRemove = async () => {
    const pkg = pendingRemove;
    if (!pkg) return;
    setRemoving(true);
    setActionError(null);
    append(`$ remove_package "${pkg.name}"`, "cmd");
    setRunning(`Removing ${pkg.name}…`);

    const removeResult = await removePackage(pkg.name);
    if (!removeResult.success) {
      setActionError(`Failed to remove ${pkg.name}.`);
      append(`Failed to remove ${pkg.name}`, "err");
      setRemoving(false);
      setRunning(null);
      return;
    }

    append(`Removed ${pkg.name} ${pkg.version}`, "ok");
    push("success", `${pkg.name} ${pkg.version} removed`);
    setPendingRemove(null);
    setRemoving(false);

    setRunning("Running autoremove…");
    append("$ apt autoremove -y", "cmd");
    const autoResult = await runAutoremove();
    if (autoResult.success) {
      if (autoResult.removed.length > 0) {
        append(
          `Autoremove cleaned ${autoResult.removed.length} orphaned packages: ${autoResult.removed.join(", ")}`,
          "ok"
        );
        push("success", `Autoremove removed ${autoResult.removed.length} orphaned packages`);
      } else {
        append("Autoremove finished, no orphaned packages found", "info");
      }
    } else {
      append("Autoremove failed", "err");
      push("error", "Autoremove failed");
    }
    setRunning(null);
    setExpanded(null);

    await loadPackages();
  };

  const showEmptyState = !loading && filtered.length === 0;

  return (
    <div>
      <h1 className="page-title">Packages</h1>
      <p className="page-subtitle">
        Browse, search and manage installed packages
      </p>

      <div className="packages-toolbar">
        <div className="toolbar-search">
          <span className="toolbar-search-icon">🔍</span>
          <input
            className="pkg-search"
            type="search"
            placeholder="Search packages by name or description..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search packages"
          />
        </div>
        <div className="toolbar-filters">
          <select
            className="size-filter"
            value={sizeFilter}
            onChange={(e) => setSizeFilter(e.target.value as SizeFilter)}
            aria-label="Filter by size"
          >
            {SIZE_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="date-filter"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value as DateFilter)}
            aria-label="Filter by install date"
          >
            {DATE_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="sort-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortBy)}
            aria-label="Sort packages"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="result-count" aria-live="polite">
          {loading
            ? "Loading..."
            : packages && filtered.length !== packages.length
            ? `${filtered.length} of ${packages.length}`
            : packages
            ? `${packages.length} packages`
            : ""}
        </div>
      </div>

      {loadError && <div className="toast toast-error">{loadError}</div>}

      <div className="pkg-table-wrap">
        <table className="pkg-table">
          <thead>
            <tr>
              <th className="col-toggle" aria-label="Details"></th>
              <th className="col-name">Package</th>
              <th className="col-size">Size</th>
              <th className="col-date">Installed</th>
              <th className="col-actions" aria-label="Actions"></th>
            </tr>
          </thead>
          <tbody>
            {loading && !packages && <TableSkeleton rows={8} />}
            {!loading &&
              filtered.map((pkg) => (
                <PackageRows
                  key={pkg.name}
                  pkg={pkg}
                  isExpanded={expanded === pkg.name}
                  onToggle={toggleExpand}
                  onRemove={requestRemove}
                />
              ))}
          </tbody>
        </table>
        {showEmptyState && (
          <div className="empty-state">
            <div className="empty-state-icon">📭</div>
            <p className="empty-state-title">No packages found</p>
            <p className="empty-state-text">
              Try adjusting the search query or filters.
            </p>
          </div>
        )}
      </div>

      {pendingRemove && (
        <ConfirmRemoveModal
          pkg={pendingRemove}
          removing={removing}
          error={actionError}
          onConfirm={handleConfirmRemove}
          onCancel={() => setPendingRemove(null)}
        />
      )}
    </div>
  );
};

interface PackageRowsProps {
  pkg: InstalledPackage;
  isExpanded: boolean;
  onToggle: (name: string) => void;
  onRemove: (pkg: InstalledPackage) => void;
}

const TableSkeleton = ({ rows }: { rows: number }) => (
  <>
    {Array.from({ length: rows }, (_, index) => (
      <tr className="pkg-skeleton-row" aria-hidden="true" key={index} data-testid="packages-skeleton">
        <td className="col-toggle">
          <span
            className="loading-skeleton"
            style={{ display: "block", width: 18, height: 18, borderRadius: 6 }}
          ></span>
        </td>
        <td className="col-name">
          <div className="loading-skeleton skeleton-text" style={{ width: "45%", minWidth: 120 }}></div>
          <div className="loading-skeleton skeleton-text" style={{ width: "65%" }}></div>
        </td>
        <td className="col-size">
          <div className="loading-skeleton skeleton-text" style={{ width: 56 }}></div>
        </td>
        <td className="col-date">
          <div className="loading-skeleton skeleton-text" style={{ width: 96 }}></div>
          <div className="loading-skeleton skeleton-text" style={{ width: 48, height: 12 }}></div>
        </td>
        <td className="col-actions">
          <span
            className="loading-skeleton"
            style={{ display: "inline-block", width: 68, height: 26, borderRadius: 6 }}
          ></span>
        </td>
      </tr>
    ))}
  </>
);

const PackageRows = ({ pkg, isExpanded, onToggle, onRemove }: PackageRowsProps) => {
  const days = daysSince(pkg.installed_at);

  return (
    <>
      <tr className={isExpanded ? "pkg-row expanded" : "pkg-row"} data-package={pkg.name}>
        <td className="col-toggle">
          {pkg.dependencies.length > 0 && (
            <button
              className="row-toggle"
              onClick={() => onToggle(pkg.name)}
              aria-label={`Show dependencies of ${pkg.name}`}
            >
              {isExpanded ? "▾" : "▸"}
            </button>
          )}
        </td>
        <td className="col-name">
          <div className="pkg-name">{pkg.name}</div>
          <div className="pkg-description">
            {pkg.description || "—"}
            {pkg.is_dependency && <span className="dep-badge">auto</span>}
          </div>
        </td>
        <td className="col-size">
          <span className="pkg-size">{formatSize(pkg.size)}</span>
        </td>
        <td className="col-date">
          <span className="pkg-date">
            {formatDate(pkg.installed_at)}
            {Number.isFinite(days) && (
              <span className="pkg-date-relative">
                {days === 0 ? "today" : days === 1 ? "yesterday" : `${days} days ago`}
              </span>
            )}
          </span>
        </td>
        <td className="col-actions">
          {!pkg.is_dependency && (
            <button
              className="btn btn-danger btn-sm btn-remove"
              onClick={() => onRemove(pkg)}
            >
              Remove
            </button>
          )}
        </td>
      </tr>
      {isExpanded && (
        <tr className="pkg-details-row" data-testid={`details-${pkg.name}`}>
          <td></td>
          <td colSpan={4}>
            <div className="pkg-details">
              <div className="pkg-details-section">
                <div className="pkg-details-label">Dependencies</div>
                {pkg.dependencies.length === 0 ? (
                  <p className="pkg-details-muted">No dependencies</p>
                ) : (
                  <div className="dep-chips">
                    {pkg.dependencies.map((dep) => (
                      <span className="dep-chip" key={dep}>
                        {dep}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="pkg-details-section">
                <div className="pkg-details-label">Installed size</div>
                <p className="pkg-details-value">{formatSize(pkg.size)}</p>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
};

export default Packages;
