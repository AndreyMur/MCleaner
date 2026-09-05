import { invoke } from "@tauri-apps/api/core";
import { inTauri } from "./env";

export interface InstalledPackage {
  name: string;
  version: string;
  size: number;
  description: string;
  dependencies: string[];
  installed_at: string;
  is_dependency?: boolean;
}

export interface RemoveResult {
  success: boolean;
  removed: string[];
}

export interface AutoremoveResult {
  success: boolean;
  removed: string[];
}

interface MockSeed {
  name: string;
  version: string;
  size: number;
  description: string;
  dependencies: string[];
  daysAgo: number;
  isDependency?: boolean;
}

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const isoDaysAgo = (days: number): string => {
  const date = new Date(Date.now() - days * 86_400_000);
  return date.toISOString();
};

const SEEDS: MockSeed[] = [
  { name: "bash", version: "5.2.15-2", size: 1_240_000, description: "GNU Bourne Again SHell", dependencies: [], daysAgo: 350 },
  { name: "curl", version: "8.5.0-2", size: 480_000, description: "Command line tool for transferring data with URL syntax", dependencies: ["libcurl4"], daysAgo: 120 },
  { name: "libcurl4", version: "8.5.0-2", size: 890_000, description: "Easy-to-use client-side URL transfer library", dependencies: [], daysAgo: 120, isDependency: true },
  { name: "git", version: "2.43.0-1", size: 28_000_000, description: "Fast, scalable, distributed revision control system", dependencies: [], daysAgo: 60 },
  { name: "google-chrome-stable", version: "126.0.6478.126-1", size: 214_000_000, description: "The popular web browser from Google", dependencies: [], daysAgo: 15 },
  { name: "grep", version: "3.11-4", size: 210_000, description: "GNU grep, egrep and fgrep", dependencies: [], daysAgo: 350 },
  { name: "openssh-client", version: "1:9.6p1-3", size: 3_100_000, description: "Secure shell (SSH) client for secure access to remote machines", dependencies: [], daysAgo: 200 },
  { name: "python3", version: "3.12.3-1", size: 36_000_000, description: "Interactive high-level object-oriented language", dependencies: ["libpython3.12", "python3-minimal"], daysAgo: 90 },
  { name: "libpython3.12", version: "3.12.3-1", size: 5_400_000, description: "Python 3.12 runtime library", dependencies: [], daysAgo: 90, isDependency: true },
  { name: "python3-minimal", version: "3.12.3-1", size: 1_900_000, description: "Minimal subset of the Python language", dependencies: [], daysAgo: 90, isDependency: true },
  { name: "visual-studio-code", version: "1.92.0-1", size: 135_000_000, description: "Code editing. Redefined", dependencies: [], daysAgo: 5 },
  { name: "vlc", version: "3.0.20-3", size: 118_000_000, description: "Multimedia player and streamer", dependencies: ["libvlc5", "vlc-plugin-video"], daysAgo: 40 },
  { name: "libvlc5", version: "3.0.20-3", size: 4_200_000, description: "VLC media player library", dependencies: [], daysAgo: 40, isDependency: true },
  { name: "vlc-plugin-video", version: "3.0.20-3", size: 9_100_000, description: "Video plugins for VLC", dependencies: [], daysAgo: 40, isDependency: true },
];

let mockPackages: InstalledPackage[] = seedMock();

function seedMock(): InstalledPackage[] {
  return SEEDS.map((seed) => ({
    name: seed.name,
    version: seed.version,
    size: seed.size,
    description: seed.description,
    dependencies: [...seed.dependencies],
    installed_at: isoDaysAgo(seed.daysAgo),
    is_dependency: seed.isDependency,
  }));
}

function sortByName(packages: InstalledPackage[]): InstalledPackage[] {
  return [...packages].sort((a, b) => a.name.localeCompare(b.name));
}

export async function getInstalledPackages(): Promise<InstalledPackage[]> {
  if (!inTauri()) {
    await delay(400);
    return sortByName(mockPackages);
  }
  try {
    const raw = await invoke<Partial<InstalledPackage>[]>("get_installed_packages");
    return (raw ?? []).map(normalizePackage);
  } catch (error) {
    console.error("Failed to load installed packages:", error);
    return [];
  }
}

function normalizePackage(raw: Partial<InstalledPackage>): InstalledPackage {
  return {
    name: raw.name ?? "unknown",
    version: raw.version ?? "",
    size: raw.size ?? 0,
    description: raw.description ?? "",
    dependencies: raw.dependencies ?? [],
    installed_at: raw.installed_at ?? "",
    is_dependency: raw.is_dependency ?? false,
  };
}

export async function removePackage(name: string): Promise<RemoveResult> {
  if (!inTauri()) {
    await delay(500);
    const target = mockPackages.find((p) => p.name === name);
    const removed = [name];
    mockPackages = mockPackages.filter((p) => p.name !== name);
    if (!target) {
      return { success: false, removed };
    }
    return { success: true, removed };
  }
  try {
    const ok = await invoke<boolean>("remove_package", { name });
    return { success: ok, removed: ok ? [name] : [] };
  } catch (error) {
    console.error("Failed to remove package:", error);
    return { success: false, removed: [] };
  }
}

export async function runAutoremove(): Promise<AutoremoveResult> {
  if (!inTauri()) {
    await delay(600);
    const dependencyNames = new Set(mockPackages.flatMap((p) => p.dependencies));
    const orphans = mockPackages.filter(
      (p) => p.is_dependency && !dependencyNames.has(p.name)
    );
    const orphanNames = orphans.map((p) => p.name);
    mockPackages = mockPackages.filter((p) => !orphanNames.includes(p.name));
    return { success: true, removed: orphanNames };
  }
  try {
    const ok = await invoke<boolean>("run_autoremove");
    return { success: ok, removed: [] };
  } catch (error) {
    console.error("Failed to run autoremove:", error);
    return { success: false, removed: [] };
  }
}
