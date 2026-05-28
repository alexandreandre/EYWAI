import type { AbsenceRequest, CalendarDay } from '@/api/absences';

export interface PayslipInfo {
  id: string;
  month: number;
  year: number;
  name: string;
  url: string;
  net_a_payer?: number | null;
}

export type PayslipDisplayLabel = 'm1' | 'latest';

export interface PayslipDisplay {
  payslip: PayslipInfo;
  label: PayslipDisplayLabel;
}

export function pickDisplayPayslip(payslips: PayslipInfo[]): PayslipDisplay | null {
  if (!payslips.length) return null;

  const today = new Date();
  const previousMonth = today.getMonth() === 0 ? 12 : today.getMonth();
  const previousYear =
    today.getMonth() === 0 ? today.getFullYear() - 1 : today.getFullYear();

  const m1 = payslips.find(
    (p) => p.month === previousMonth && p.year === previousYear
  );
  if (m1) return { payslip: m1, label: 'm1' };

  const sorted = [...payslips].sort(
    (a, b) => b.year - a.year || b.month - a.month
  );
  return { payslip: sorted[0], label: 'latest' };
}

export function formatCurrency(amount: number | undefined | null): string {
  if (amount == null || Number.isNaN(amount)) return 'N/A';
  return amount.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
}

export function formatMonthYear(month: number, year: number): string {
  return new Date(year, month - 1).toLocaleString('fr-FR', {
    month: 'long',
    year: 'numeric',
  });
}

export function formatCumulsMonthLabel(monthIndex: number | undefined): string | null {
  if (monthIndex == null || monthIndex < 1 || monthIndex > 12) return null;
  return new Date(2000, monthIndex - 1).toLocaleString('fr-FR', { month: 'long' });
}

/** Parse une date d'absence (YYYY-MM-DD) en minuit local — évite le décalage UTC. */
export function parseAbsenceDayLocal(day: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(day.trim());
  if (match) {
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }
  const date = new Date(day);
  date.setHours(0, 0, 0, 0);
  return date;
}

export function getNextValidatedAbsenceDate(
  history: AbsenceRequest[]
): Date | null {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const futureDates = history
    .filter((a) => a.status === 'validated')
    .flatMap((a) => a.selected_days ?? [])
    .map((d) => parseAbsenceDayLocal(d))
    .filter((d) => d >= today)
    .sort((a, b) => a.getTime() - b.getTime());

  return futureDates[0] ?? null;
}

export const CALENDAR_LEGEND = {
  aujourdhui: { label: "Aujourd'hui", color: 'border-2 border-primary' },
  prochaine_absence: {
    label: 'Prochaine absence',
    color: 'ring-2 ring-primary ring-offset-1',
  },
  conge: { label: 'Congé / RTT', color: 'bg-blue-500' },
  arret_maladie: { label: 'Arrêt maladie', color: 'bg-orange-400' },
  ferie: { label: 'Jour férié', color: 'bg-green-500' },
  weekend: {
    label: 'Weekend',
    color: 'bg-gray-200 dark:bg-gray-700',
  },
} as const;

export type CalendarDayType = keyof typeof CALENDAR_LEGEND;

export const ABSENCE_CALENDAR_MODIFIERS_CLASS_NAMES = {
  aujourdhui: 'border-2 border-primary rounded-md !bg-transparent text-primary',
  prochaine_absence:
    'ring-2 ring-primary ring-offset-1 rounded-md font-semibold',
  conge: 'bg-blue-500 text-white rounded-md',
  arret_maladie: 'bg-orange-400 text-white rounded-md',
  ferie: 'bg-green-500 text-white rounded-md',
  weekend: 'text-muted-foreground opacity-80',
  travail: 'font-semibold',
} as const;

export function buildAbsenceCalendarModifiers(
  calendarDays: CalendarDay[],
  currentMonth: Date,
  today: Date,
  nextAbsenceDate: Date | null
): Record<string, Date[]> {
  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();

  if (calendarDays.length === 0) {
    const weekends: Date[] = [];
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(year, month, day);
      if (date.getDay() === 0 || date.getDay() === 6) {
        weekends.push(date);
      }
    }
    const base: Record<string, Date[]> = {
      weekend: weekends,
      aujourdhui: [today],
    };
    if (nextAbsenceDate) {
      base.prochaine_absence = [nextAbsenceDate];
    }
    return base;
  }

  const modifiersFromApi = calendarDays.reduce(
    (acc, day) => {
      const type = day.type;
      if (!acc[type]) acc[type] = [];
      acc[type].push(new Date(year, month, day.jour));
      return acc;
    },
    {} as Record<string, Date[]>
  );

  modifiersFromApi.aujourdhui = [today];
  if (nextAbsenceDate) {
    modifiersFromApi.prochaine_absence = [nextAbsenceDate];
  }
  return modifiersFromApi;
}
