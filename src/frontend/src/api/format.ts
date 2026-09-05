export function formatSize(bytes: number): string {
  if (!bytes || bytes <= 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function daysSince(iso: string): number {
  const date = new Date(iso);
  if (isNaN(date.getTime())) return Number.POSITIVE_INFINITY;
  return Math.floor((Date.now() - date.getTime()) / 86_400_000);
}

export const SIZE_LIMITS = {
  small: 1024 * 1024,
  medium: 50 * 1024 * 1024,
};

export function sizeCategory(size: number): "small" | "medium" | "large" {
  if (size < SIZE_LIMITS.small) return "small";
  if (size <= SIZE_LIMITS.medium) return "medium";
  return "large";
}
