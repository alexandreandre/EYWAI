import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import type { Shift } from '@/api/planning';
import { cn } from '@/lib/utils';
import {
  CALENDAR_TYPE_BAR_COLORS,
  formatCalendarValue,
  getCalendarTypeLabel,
} from '@/lib/calendarTypes';
import { dayHasSignificantEcart } from '@/lib/employeeCalendarUtils';
import { formatShiftPastille, isPayrollRestDay } from '@/lib/employeeCalendarPlanning';

interface EmployeeCalendarMonthListProps {
  year: number;
  month: number;
  daysInMonth: number;
  plannedCalendar: PlannedEventData[];
  actualHours: ActualHoursData[];
  isForfaitJour: boolean;
  shiftsByDay?: Record<number, Shift[]>;
  onDayClick: (day: number) => void;
}

export function EmployeeCalendarMonthList({
  year,
  month,
  daysInMonth,
  plannedCalendar,
  actualHours,
  isForfaitJour,
  shiftsByDay = {},
  onDayClick,
}: EmployeeCalendarMonthListProps) {
  const today = new Date();

  return (
    <ul className="flex flex-col gap-2 md:hidden" aria-label="Liste des jours du mois">
      {Array.from({ length: daysInMonth }, (_, i) => {
        const day = i + 1;
        const date = new Date(year, month, day);
        const isToday = date.toDateString() === today.toDateString();
        const planned = plannedCalendar.find((d) => d.jour === day);
        const actual = actualHours.find((d) => d.jour === day);
        const dayType = planned?.type ?? 'weekend';
        const barColor = CALENDAR_TYPE_BAR_COLORS[dayType] ?? CALENDAR_TYPE_BAR_COLORS.weekend;
        const hasEcart = dayHasSignificantEcart(
          planned?.heures_prevues,
          actual?.heures_faites,
          isForfaitJour
        );
        const weekday = date.toLocaleDateString('fr-FR', { weekday: 'short' });
        const dayShifts = shiftsByDay[day] ?? [];
        const shiftPastille = formatShiftPastille(dayShifts);
        const shiftMismatch =
          shiftPastille != null && isPayrollRestDay(dayType) && dayShifts.length > 0;

        return (
          <li key={day}>
            <button
              type="button"
              onClick={() => onDayClick(day)}
              className={cn(
                'flex w-full items-stretch gap-3 rounded-lg border bg-card p-3 text-left transition-colors',
                'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                isToday && 'ring-2 ring-primary',
                hasEcart && 'ring-2 ring-amber-400'
              )}
            >
              <span className={cn('w-1 shrink-0 rounded-full', barColor)} aria-hidden />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-semibold capitalize">
                    {weekday} {day}
                    {isToday && (
                      <span className="ml-2 text-xs font-normal text-primary">Aujourd&apos;hui</span>
                    )}
                  </span>
                  <span className="text-xs text-muted-foreground">{getCalendarTypeLabel(dayType)}</span>
                </div>
                {(dayType === 'travail' || planned?.heures_prevues != null) && (
                  <p className="text-xs text-muted-foreground tabular-nums">
                    Prévu {formatCalendarValue(planned?.heures_prevues, isForfaitJour)}
                    {' · '}
                    Réalisé {formatCalendarValue(actual?.heures_faites, isForfaitJour)}
                  </p>
                )}
                {shiftPastille && (
                  <p
                    className={cn(
                      'text-xs font-medium tabular-nums',
                      shiftMismatch ? 'text-amber-700 dark:text-amber-300' : 'text-violet-700 dark:text-violet-300'
                    )}
                  >
                    Planning : {shiftPastille}
                  </p>
                )}
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
