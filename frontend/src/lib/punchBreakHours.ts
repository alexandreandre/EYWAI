/** Pause repas du portail pointage, appliquée aux heures d'un import. */

export interface PunchBreakRule {
  enabled: boolean;
  breakMinutes: number;
  thresholdMinutes: number;
}

export function parsePunchMinutes(raw: string | number | null | undefined): number | null {
  if (raw == null || raw === '') return null;
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    const n = Math.trunc(raw);
    if (n <= 0) return null;
    if (n < 2400) {
      const h = Math.floor(n / 100);
      const m = n % 100;
      if (h <= 23 && m <= 59) return h * 60 + m;
    }
    return null;
  }
  const s = String(raw).trim().replace(/\s/g, '').toLowerCase().replace('h', ':');
  if (!s || s === '0' || s === '00' || s === '0000') return null;
  if (s.includes(':')) {
    const [hs, ms] = s.split(':');
    const h = Number(hs);
    const m = Number(ms || 0);
    if (!Number.isFinite(h) || !Number.isFinite(m) || h > 23 || m > 59) return null;
    return h * 60 + m;
  }
  if (/^\d{1,4}$/.test(s)) return parsePunchMinutes(Number(s));
  return null;
}

/** Minutes de pause à ôter d'une présence brute. */
export function deductedBreakMinutes(grossMinutes: number, rule: PunchBreakRule): number {
  if (!rule.enabled || rule.breakMinutes <= 0 || grossMinutes <= 0) return 0;
  if (rule.thresholdMinutes > 0 && grossMinutes <= rule.thresholdMinutes) return 0;
  return rule.breakMinutes;
}

export function netHoursFromRange(
  entryRaw: string | number | null | undefined,
  exitRaw: string | number | null | undefined,
  rule: PunchBreakRule,
): number | null {
  const start = parsePunchMinutes(entryRaw);
  const end = parsePunchMinutes(exitRaw);
  if (start == null || end == null || end <= start) return null;
  const gross = end - start;
  const net = gross - deductedBreakMinutes(gross, rule);
  return Math.round(Math.max(0, net) / 60 * 100) / 100;
}

/** Pause déjà comprise dans des heures affichées (nettes) pour un forfait. */
export function deductedForDisplayedHours(netHours: number, rule: PunchBreakRule): number {
  if (!rule.enabled || rule.breakMinutes <= 0 || netHours <= 0) return 0;
  const estimatedGross = netHours * 60 + rule.breakMinutes;
  if (rule.thresholdMinutes > 0 && estimatedGross <= rule.thresholdMinutes) return 0;
  return rule.breakMinutes;
}

export function reapplyPauseOnHours(
  currentHours: number,
  prev: PunchBreakRule,
  next: PunchBreakRule,
): number {
  const oldDeduct = deductedForDisplayedHours(currentHours, prev);
  const gross = currentHours * 60 + oldDeduct;
  const nextDeduct = deductedBreakMinutes(gross, next);
  return Math.round(Math.max(0, gross - nextDeduct) / 60 * 100) / 100;
}

export interface PunchTimedDay {
  heures: number | null;
  type: string;
  punch_entry_raw?: string | null;
  punch_exit_raw?: string | null;
}

export function reapplyPauseOnDay<T extends PunchTimedDay>(
  day: T,
  prev: PunchBreakRule,
  next: PunchBreakRule,
): T {
  if (day.type !== 'travail' && day.type !== 'weekend') return day;
  const fromRange = netHoursFromRange(day.punch_entry_raw, day.punch_exit_raw, next);
  if (fromRange != null) return { ...day, heures: fromRange };
  if (day.heures == null || day.heures <= 0) return day;
  return { ...day, heures: reapplyPauseOnHours(day.heures, prev, next) };
}
