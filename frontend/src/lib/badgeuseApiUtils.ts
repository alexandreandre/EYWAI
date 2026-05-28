import { isAxiosError } from "axios";

export function apiErrorDetail(error: unknown, fallback: string): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (error.response?.status === 503) {
      return "Service temporairement indisponible. Réessayez dans quelques secondes.";
    }
  }
  return fallback;
}

export function isBadgeuseSchemaMissing(error: unknown, message: string): boolean {
  return (
    isAxiosError(error) &&
    error.response?.status === 503 &&
    message.toLowerCase().includes("tables badgeuse")
  );
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function periodRangeLastDays(dayCount: 7 | 30): { from: string; to: string } {
  const to = todayIso();
  const fromDate = new Date();
  fromDate.setDate(fromDate.getDate() - (dayCount - 1));
  return { from: fromDate.toISOString().slice(0, 10), to };
}

export function formatBadgeuseDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-");
  if (!y || !m || !d) return isoDate;
  return `${d}/${m}/${y}`;
}

export function dayStatusLabel(status: string): string {
  switch (status) {
    case "Complet":
      return "Complet";
    case "Anomalie":
      return "Anomalie";
    case "Absent":
      return "Absent";
    default:
      return status;
  }
}

export const BADGEUSE_MIGRATION_FILE = "supabase/migrations/20260525120000_badgeuse_qr.sql";
