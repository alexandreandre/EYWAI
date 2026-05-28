/**
 * Préférences et planification de la mise à jour automatique du 1er du mois.
 */

export const RATES_AUTO_SYNC_MONTH_KEY = 'rates_auto_sync_month';
export const RATES_MONTHLY_AUTO_ENABLED_KEY = 'rates_monthly_auto_enabled';

export type MonthlyAutoSyncState = {
  enabled: boolean;
  isFirstDayOfMonth: boolean;
  completedThisMonth: boolean;
  /** Peut lancer (auto ou manuel) la mise à jour « du mois » aujourd'hui */
  canRunMonthlyToday: boolean;
  nextRunLabel: string;
  statusLabel: string;
};

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

export function currentMonthKey(date = new Date()): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

export function isFirstDayOfMonth(date = new Date()): boolean {
  return date.getDate() === 1;
}

export function isMonthlyAutoSyncEnabled(): boolean {
  const raw = readStorage(RATES_MONTHLY_AUTO_ENABLED_KEY);
  if (raw === null) return true;
  return raw === 'true';
}

export function setMonthlyAutoSyncEnabled(enabled: boolean): void {
  writeStorage(RATES_MONTHLY_AUTO_ENABLED_KEY, enabled ? 'true' : 'false');
}

export function isMonthlySyncCompletedForCurrentMonth(): boolean {
  return readStorage(RATES_AUTO_SYNC_MONTH_KEY) === currentMonthKey();
}

export function markMonthlyAutoSyncDone(): void {
  writeStorage(RATES_AUTO_SYNC_MONTH_KEY, currentMonthKey());
}

export function clearMonthlyAutoSyncDone(): void {
  writeStorage(RATES_AUTO_SYNC_MONTH_KEY, '');
}

function formatNextFirstOfMonth(date = new Date()): string {
  const next = new Date(date.getFullYear(), date.getMonth() + 1, 1);
  return next.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
}

export function getMonthlyAutoSyncState(date = new Date()): MonthlyAutoSyncState {
  const enabled = isMonthlyAutoSyncEnabled();
  const isFirstDay = isFirstDayOfMonth(date);
  const completedThisMonth = isMonthlySyncCompletedForCurrentMonth();
  const canRunMonthlyToday = enabled && isFirstDay && !completedThisMonth;

  let statusLabel: string;
  if (!enabled) {
    statusLabel = 'Mise à jour automatique désactivée';
  } else if (!isFirstDay) {
    statusLabel = `Prochaine exécution automatique : ${formatNextFirstOfMonth(date)}`;
  } else if (completedThisMonth) {
    statusLabel = 'Mise à jour du mois effectuée ce 1er';
  } else {
    statusLabel = "Mise à jour du mois à effectuer aujourd'hui";
  }

  return {
    enabled,
    isFirstDayOfMonth: isFirstDay,
    completedThisMonth,
    canRunMonthlyToday,
    nextRunLabel: formatNextFirstOfMonth(date),
    statusLabel,
  };
}

/** Auto au chargement : uniquement le 1er du mois, si activé et pas encore fait. */
export function shouldAutoStartMonthlySync(date = new Date()): boolean {
  return getMonthlyAutoSyncState(date).canRunMonthlyToday;
}
