import axios from 'axios';
import {
  addDays,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  startOfMonth,
  startOfWeek,
} from 'date-fns';
import { fr } from 'date-fns/locale';
import type { Shift, WeekPlanning } from '@/api/planning';

export function apiErrorMessage(err: unknown, fallback = 'Erreur inattendue'): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as { detail?: unknown } | undefined;
    const d = data?.detail;
    if (typeof d === 'string' && d.trim()) {
      return d;
    }
    if (err.response?.status === 503) {
      return 'Service temporairement indisponible. Réessayez dans quelques secondes.';
    }
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return fallback;
}

export function coerceWeekPlanning(raw: unknown): WeekPlanning {
  const r = raw as Record<string, unknown>;
  const ws =
    typeof r.week_start === 'string'
      ? r.week_start.slice(0, 10)
      : String(r.week_start ?? '').slice(0, 10);
  const we =
    typeof r.week_end === 'string'
      ? r.week_end.slice(0, 10)
      : String(r.week_end ?? '').slice(0, 10);
  const rawHours = (r.employee_hours as Array<{
    employee_id: string;
    total_minutes: number;
  }> | null) ?? [];
  const contractMinutes = Math.round(35 * 60);
  const employee_hours = rawHours.map((h) => ({
    employee_id: h.employee_id,
    total_minutes: h.total_minutes,
    contract_minutes: contractMinutes,
    delta: h.total_minutes - contractMinutes,
  }));
  const pta = r.payroll_transmitted_at;
  return {
    week_start: ws,
    week_end: we,
    status: String(r.status ?? 'draft'),
    payroll_transmitted: Boolean(r.payroll_transmitted),
    payroll_transmitted_at:
      typeof pta === 'string' && pta.length > 0 ? pta : undefined,
    team_view_enabled: Boolean(r.team_view_enabled),
    shifts: (r.shifts as Shift[]) ?? [],
    employee_hours,
  };
}

export function defaultWeekStartIso(): string {
  return format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd');
}

export function formatWeekRangeLabel(weekStart: string, weekEnd: string): string {
  try {
    const a = format(parseISOSafe(weekStart), 'd MMMM yyyy', { locale: fr });
    const b = format(parseISOSafe(weekEnd), 'd MMMM yyyy', { locale: fr });
    return `Semaine du ${a} au ${b}`;
  } catch {
    return `Semaine du ${weekStart} au ${weekEnd}`;
  }
}

export function parseISOSafe(s: string): Date {
  return new Date(`${s.slice(0, 10)}T12:00:00`);
}

/** Aligné sur ShiftBlock pour les pastilles mois / astreintes */
export const TRANSVERSE_BADGE_COLORS: Record<string, string> = {
  CP: '#4CAF50',
  RTT: '#8BC34A',
  MAL: '#FF5722',
  ABS_INJ: '#F44336',
  FORM: '#2196F3',
  REP_HEB: '#9E9E9E',
  astreinte: '#5C6BC0',
  on_call: '#3949AB',
};

export function normShiftDay(iso: string): string {
  return iso.slice(0, 10);
}

export function groupShiftsByDay(shifts: Shift[]): Record<string, Shift[]> {
  const map: Record<string, Shift[]> = {};
  for (const s of shifts) {
    const d = normShiftDay(s.shift_date);
    if (!map[d]) map[d] = [];
    map[d].push(s);
  }
  for (const k of Object.keys(map)) {
    map[k].sort((a, b) => a.start_time.localeCompare(b.start_time));
  }
  return map;
}

export function shiftBadgeBackground(s: Shift): string {
  if (s.shift_type?.color) return s.shift_type.color;
  const cat = s.transverse_category;
  if (cat && TRANSVERSE_BADGE_COLORS[cat]) return TRANSVERSE_BADGE_COLORS[cat];
  return '#607D8B';
}

export function employeeShort(s: Shift): string {
  const ln = (s.employee_last_name ?? '').trim();
  const fn = (s.employee_first_name ?? '').trim();
  if (ln || fn) return `${ln.toUpperCase()} ${fn}`.trim();
  return 'Salarié';
}

export function shiftTypeShortLabel(s: Shift): string {
  if (s.shift_type?.label) return s.shift_type.label;
  if (s.transverse_category === 'astreinte' || s.transverse_category === 'on_call') {
    return 'Astreinte';
  }
  return s.transverse_category ?? 'Shift';
}

export function replacerDisplayName(s: Shift): string {
  if (s.replacing_employee_name) return s.replacing_employee_name;
  return employeeShort(s);
}

export function formatDateFrCell(iso: string): string {
  try {
    return format(parseISOSafe(iso), 'EEE d MMM yyyy', { locale: fr });
  } catch {
    return iso.slice(0, 10);
  }
}

export function formatHourRange(s: Shift): string {
  return `${s.start_time.slice(0, 5)} → ${s.end_time.slice(0, 5)}`;
}

export function buildMonthCalendarDays(anchor: Date): Date[] {
  const start = startOfMonth(anchor);
  const end = endOfMonth(anchor);
  const gridStart = startOfWeek(start, { weekStartsOn: 1 });
  const gridEnd = endOfWeek(end, { weekStartsOn: 1 });
  return eachDayOfInterval({ start: gridStart, end: gridEnd });
}

export function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) {
    out.push(arr.slice(i, i + size));
  }
  return out;
}

export function toHmsFromInput(hm: string): string {
  const t = hm.trim();
  return t.length <= 5 ? `${t}:00` : t.slice(0, 8);
}

export function isRhLike(role: string | undefined): boolean {
  return (
    role === 'admin' ||
    role === 'rh' ||
    role === 'collaborateur_rh' ||
    role === 'admin'
  );
}

export function statusBadge(status: string): { label: string; className: string } {
  switch (status) {
    case 'partially_published':
      return {
        label: 'Partiellement publié',
        className: 'bg-orange-100 text-orange-900 hover:bg-orange-100',
      };
    case 'published':
      return {
        label: 'Publié',
        className: 'bg-green-100 text-green-900 hover:bg-green-100',
      };
    case 'locked':
      return {
        label: 'Verrouillé',
        className: 'bg-red-100 text-red-900 hover:bg-red-100',
      };
    default:
      return {
        label: 'Brouillon',
        className: 'bg-slate-100 text-slate-800 hover:bg-slate-100',
      };
  }
}

export function shiftDurationMinutes(s: Shift): number {
  const toSec = (t: string) => {
    const parts = t.split(':').map((x) => Number(x));
    return (parts[0] || 0) * 3600 + (parts[1] || 0) * 60 + (parts[2] || 0);
  };
  const a = toSec(s.start_time);
  let b = toSec(s.end_time);
  if (b <= a) {
    b += 24 * 3600;
  }
  return Math.round((b - a) / 60);
}
