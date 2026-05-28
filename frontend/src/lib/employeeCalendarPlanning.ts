import { format, parseISO, startOfWeek } from 'date-fns';
import type { Shift } from '@/api/planning';

export type CalendarHubView = 'week' | 'month' | 'year';

const VALID_VIEWS: CalendarHubView[] = ['week', 'month', 'year'];

export function parseCalendarHubView(raw: string | null): CalendarHubView {
  if (raw && VALID_VIEWS.includes(raw as CalendarHubView)) {
    return raw as CalendarHubView;
  }
  return 'week';
}

export function defaultWeekStartIso(): string {
  return format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd');
}

export function weekStartFromYearMonth(year: number, month: number): string {
  const anchor = new Date(year, month - 1, 1);
  return format(startOfWeek(anchor, { weekStartsOn: 1 }), 'yyyy-MM-dd');
}

export function yearMonthFromWeekStart(weekStart: string): { year: number; month: number } {
  const d = parseISO(weekStart.slice(0, 10));
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

export function normShiftDay(iso: string): string {
  return iso.slice(0, 10);
}

export function dayNumberFromIso(iso: string): number {
  return parseInt(iso.slice(8, 10), 10);
}

/** Regroupe les shifts par numéro de jour (1–31) pour un mois donné. */
export function groupShiftsByDayNumber(shifts: Shift[]): Record<number, Shift[]> {
  const map: Record<number, Shift[]> = {};
  for (const s of shifts) {
    const day = dayNumberFromIso(normShiftDay(s.shift_date));
    if (!map[day]) map[day] = [];
    map[day].push(s);
  }
  for (const day of Object.keys(map)) {
    map[Number(day)].sort((a, b) => a.start_time.localeCompare(b.start_time));
  }
  return map;
}

export function formatShiftPastille(shifts: Shift[]): string | null {
  if (shifts.length === 0) return null;
  if (shifts.length > 1) return `${shifts.length} crén.`;
  const s = shifts[0];
  return `${s.start_time.slice(0, 5)}–${s.end_time.slice(0, 5)}`;
}

export function isPayrollRestDay(type: string | null | undefined): boolean {
  return type === 'weekend' || type === 'conge' || type === 'ferie' || type === 'arret_maladie';
}

export function planningStatusLabel(status: string): string | null {
  if (status === 'draft') return null;
  if (status === 'locked') return 'Semaine verrouillée';
  if (status === 'partially_published') return 'Semaine partiellement publiée';
  if (status === 'published') return 'Semaine publiée';
  return null;
}
