import { invoke } from "@tauri-apps/api/core";
import { inTauri } from "./env";

export interface OrphanedPackage {
  name: string;
  version: string;
  size: number;
}

export interface CleanerStats {
  cache_size: number;
  orphans: OrphanedPackage[];
}

export interface CleanResult {
  success: boolean;
  freed: number;
}

export interface OrphansRemovalResult {
  success: boolean;
  removed: string[];
}

export type ProgressHandler = (percent: number, message: string) => void;

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const ORPHAN_SEEDS: OrphanedPackage[] = [
  { name: "libvlc5", version: "3.0.20-3", size: 4_200_000 },
  { name: "vlc-plugin-video", version: "3.0.20-3", size: 9_100_000 },
  { name: "libpython3.12", version: "3.12.3-1", size: 5_400_000 },
  { name: "python3-minimal", version: "3.12.3-1", size: 1_900_000 },
];

let mockCacheSize = 2_147_483_648;
let mockOrphans: OrphanedPackage[] = ORPHAN_SEEDS.map((orphan) => ({ ...orphan }));

function normalizeOrphan(raw: Partial<OrphanedPackage>): OrphanedPackage {
  return {
    name: raw.name ?? "unknown",
    version: raw.version ?? "",
    size: raw.size ?? 0,
  };
}

export async function getCleanerStats(): Promise<CleanerStats> {
  if (!inTauri()) {
    await delay(700);
    return {
      cache_size: mockCacheSize,
      orphans: mockOrphans.map((orphan) => ({ ...orphan })),
    };
  }
  try {
    const [stats, rawOrphans] = await Promise.all([
      invoke<{ cache_size?: number }>("get_dashboard_stats"),
      invoke<Partial<OrphanedPackage>[]>("get_orphaned_packages"),
    ]);
    return {
      cache_size: stats?.cache_size ?? 0,
      orphans: (rawOrphans ?? []).map(normalizeOrphan),
    };
  } catch (error) {
    console.error("Failed to load cleaner stats:", error);
    return { cache_size: 0, orphans: [] };
  }
}

export async function cleanCache(onProgress?: ProgressHandler): Promise<CleanResult> {
  if (!inTauri()) {
    const freed = mockCacheSize;
    const steps = [
      { pct: 15, label: "Scanning package cache…" },
      { pct: 40, label: "Removing .deb archives…" },
      { pct: 70, label: "Cleaning partial downloads…" },
      { pct: 90, label: "Finalizing…" },
    ];
    for (const step of steps) {
      await delay(150);
      onProgress?.(step.pct, step.label);
    }
    mockCacheSize = 0;
    onProgress?.(100, "Cache cleaned");
    return { success: true, freed };
  }
  try {
    onProgress?.(10, "Reading cache size…");
    const before = (await invoke<{ cache_size?: number }>("get_dashboard_stats"))?.cache_size ?? 0;
    onProgress?.(50, "Running apt clean…");
    const ok = await invoke<boolean>("clean_cache");
    onProgress?.(100, ok ? "Cache cleaned" : "Clean failed");
    return { success: ok, freed: ok ? before : 0 };
  } catch (error) {
    console.error("Failed to clean cache:", error);
    onProgress?.(100, "Cache clean failed");
    return { success: false, freed: 0 };
  }
}

export async function removeOrphans(
  onProgress?: ProgressHandler
): Promise<OrphansRemovalResult> {
  if (!inTauri()) {
    const removed = mockOrphans.map((orphan) => orphan.name);
    const steps = [
      { pct: 20, label: "Preparing removal plan…" },
      { pct: 55, label: "Removing orphaned packages…" },
      { pct: 90, label: "Finalizing…" },
    ];
    for (const step of steps) {
      await delay(180);
      onProgress?.(step.pct, step.label);
    }
    mockOrphans = [];
    onProgress?.(100, "Done");
    return { success: true, removed };
  }
  try {
    onProgress?.(20, "Running apt autoremove…");
    const ok = await invoke<boolean>("run_autoremove");
    onProgress?.(100, ok ? "Orphaned packages removed" : "Autoremove failed");
    return { success: ok, removed: [] };
  } catch (error) {
    console.error("Failed to remove orphaned packages:", error);
    onProgress?.(100, "Autoremove failed");
    return { success: false, removed: [] };
  }
}
