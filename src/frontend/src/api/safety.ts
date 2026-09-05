import { invoke } from "@tauri-apps/api/core";
import { inTauri } from "./env";

export interface PrivilegeStatus {
  elevated: boolean;
  os: string;
  method: string;
  user: string;
}

export interface RecoveryToolStatus {
  available: boolean;
  tool: string | null;
  command: string | null;
}

export interface RecoveryPointResult {
  success: boolean;
  tool: string | null;
  message: string;
}

export interface OperationOptions {
  signal?: AbortSignal;
}

/**
 * Mock configuration is stored in localStorage so the Playwright suite can
 * exercise elevation, abort and recovery flows without a privileged backend.
 */
const MOCK_KEYS = {
  elevated: "mcleaner.mock.elevated",
  os: "mcleaner.mock.os",
  recovery: "mcleaner.mock.recovery",
  slow: "mcleaner.mock.slow",
} as const;

function readMock(key: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const value = window.localStorage.getItem(key);
  return value === null ? fallback : value;
}

export function mockOs(): string {
  const os = readMock(MOCK_KEYS.os, "linux");
  return os === "windows" || os === "darwin" || os === "linux" ? os : "linux";
}

export function isMockElevated(): boolean {
  return readMock(MOCK_KEYS.elevated, "1") !== "0";
}

export function isMockRecoveryAvailable(): boolean {
  return readMock(MOCK_KEYS.recovery, "1") !== "0";
}

export function mockDelayMultiplier(): number {
  const raw = Number(readMock(MOCK_KEYS.slow, "1"));
  return Number.isFinite(raw) && raw > 0 ? raw : 1;
}

function mockToolLabel(os: string): string {
  if (os === "windows") return "System Restore";
  if (os === "darwin") return "Time Machine";
  return "Timeshift";
}

function mockRecoveryCommand(): string | null {
  if (!isMockRecoveryAvailable()) return null;
  const os = mockOs();
  if (os === "windows") {
    return "Checkpoint-Computer -Description 'MCleaner: before removing packages' -RestorePointType MODIFY_SETTINGS";
  }
  if (os === "darwin") {
    return "tmutil localsnapshot 'MCleaner: before removing packages'";
  }
  return 'timeshift --create --comments "MCleaner: before removing packages" --yes';
}

export function delay(
  ms: number,
  signal?: AbortSignal,
  multiplier: number = mockDelayMultiplier()
): Promise<void> {
  const effective = Math.max(0, ms * multiplier);
  return new Promise<void>((resolve) => {
    if (signal?.aborted) {
      resolve();
      return;
    }
    let timer: number | undefined;
    const onAbort = () => {
      if (timer !== undefined) window.clearTimeout(timer);
      resolve();
    };
    timer = window.setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, effective);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export async function getPrivilegeStatus(): Promise<PrivilegeStatus> {
  if (!inTauri()) {
    const elevated = isMockElevated();
    const os = mockOs();
    return {
      elevated,
      os,
      method: elevated ? (os === "windows" ? "admin" : "root") : "user",
      user: "mock",
    };
  }
  try {
    return await invoke<PrivilegeStatus>("get_privilege_status");
  } catch (error) {
    console.error("Failed to read privilege status:", error);
    return { elevated: true, os: "unknown", method: "unknown", user: "" };
  }
}

export async function isElevated(): Promise<boolean> {
  const status = await getPrivilegeStatus();
  return status.elevated;
}

export async function requestElevation(): Promise<PrivilegeStatus> {
  if (!inTauri()) {
    window.localStorage.setItem(MOCK_KEYS.elevated, "1");
    return getPrivilegeStatus();
  }
  try {
    return await invoke<PrivilegeStatus>("request_elevation");
  } catch (error) {
    console.error("Failed to request elevation:", error);
    return getPrivilegeStatus();
  }
}

/**
 * Ask the backend to stop the currently running operation (real mode). In the
 * browser the operation functions observe the AbortSignal directly.
 */
export async function cancelOperationOnAbort(signal?: AbortSignal): Promise<void> {
  if (!signal) return;
  signal.addEventListener(
    "abort",
    () => {
      if (inTauri()) {
        void invoke<boolean>("abort_operation").catch(() => false);
      }
    },
    { once: true }
  );
}

export async function checkRecoveryTool(): Promise<RecoveryToolStatus> {
  if (!inTauri()) {
    const os = mockOs();
    return {
      available: isMockRecoveryAvailable(),
      tool: isMockRecoveryAvailable() ? mockToolLabel(os) : null,
      command: mockRecoveryCommand(),
    };
  }
  try {
    const info = await invoke<{
      available?: boolean;
      tool?: string | null;
      command?: string | null;
    }>("check_recovery_tool");
    return {
      available: Boolean(info?.available),
      tool: info?.tool ?? null,
      command: info?.command ?? null,
    };
  } catch (error) {
    console.error("Failed to check recovery tool:", error);
    return { available: false, tool: null, command: null };
  }
}

export async function createRecoveryPoint(
  comment?: string
): Promise<RecoveryPointResult> {
  if (!inTauri()) {
    await delay(500);
    if (!isMockRecoveryAvailable()) {
      return {
        success: false,
        tool: null,
        message: "No recovery tool detected",
      };
    }
    return {
      success: true,
      tool: mockToolLabel(mockOs()),
      message: "Recovery point created",
    };
  }
  try {
    const payload = comment ?? "MCleaner: before removing packages";
    const result = await invoke<{
      success?: boolean;
      tool?: string | null;
      message?: string;
    }>("create_recovery_point", { comment: payload });
    return {
      success: Boolean(result?.success),
      tool: result?.tool ?? null,
      message: result?.message ?? "",
    };
  } catch (error) {
    console.error("Failed to create recovery point:", error);
    return { success: false, tool: null, message: String(error) };
  }
}
