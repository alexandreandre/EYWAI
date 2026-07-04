export type BreakKind = 'short' | 'meal' | 'other';

export interface DayBreak {
  minutes: number;
  paid: boolean;
  kind: BreakKind;
}

export const INDUSTRIAL_2X10_MEAL_30: DayBreak[] = [
  { minutes: 10, paid: true, kind: 'short' },
  { minutes: 10, paid: true, kind: 'short' },
  { minutes: 30, paid: false, kind: 'meal' },
];

export function computeBreakTotals(breaks: DayBreak[]): {
  total: number;
  paid: number;
  unpaid: number;
} {
  let paid = 0;
  let unpaid = 0;
  for (const b of breaks) {
    if (b.paid) paid += b.minutes;
    else unpaid += b.minutes;
  }
  return { total: paid + unpaid, paid, unpaid };
}

export function breaksFromLegacy(breakMinutes: number, breakPaid: boolean): DayBreak[] {
  if (breakMinutes <= 0) return [];
  return [
    {
      minutes: breakMinutes,
      paid: breakPaid,
      kind: breakPaid ? 'other' : 'meal',
    },
  ];
}

export function resolveBreaks(raw: {
  breaks?: DayBreak[];
  break_minutes?: number;
  break_paid?: boolean;
}): DayBreak[] {
  if (raw.breaks && raw.breaks.length > 0) {
    return raw.breaks.map((b) => ({
      minutes: Number(b.minutes) || 0,
      paid: Boolean(b.paid),
      kind: (b.kind as BreakKind) || 'other',
    }));
  }
  return breaksFromLegacy(Number(raw.break_minutes) || 0, Boolean(raw.break_paid));
}

export function syncLegacyBreakFields(breaks: DayBreak[]): {
  break_minutes: number;
  break_paid: boolean;
} {
  const { total, paid, unpaid } = computeBreakTotals(breaks);
  return {
    break_minutes: total,
    break_paid: total > 0 && unpaid === 0,
  };
}

export function grossPresenceHours(
  start: string,
  end: string,
  unpaidMinutes: number,
): number | null {
  if (!start || !end) return null;
  const [sh, sm] = start.split(':').map(Number);
  const [eh, em] = end.split(':').map(Number);
  if ([sh, sm, eh, em].some((n) => Number.isNaN(n))) return null;
  const gross = eh * 60 + em - (sh * 60 + sm);
  if (gross <= 0) return null;
  return Math.round(((gross - unpaidMinutes) / 60) * 100) / 100;
}

export function formatBreakSummary(breaks: DayBreak[]): string {
  const { paid, unpaid } = computeBreakTotals(breaks);
  const parts: string[] = [];
  if (paid > 0) parts.push(`${paid} min payées`);
  if (unpaid > 0) parts.push(`${unpaid} min repas`);
  return parts.length ? parts.join(' · ') : 'Aucune pause';
}
