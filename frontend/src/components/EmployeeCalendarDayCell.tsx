import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import type { Shift } from '@/api/planning';
import { cn } from '@/lib/utils';
import {
  CALENDAR_TYPE_BAR_COLORS,
  formatCalendarValue,
  getCalendarTypeLabel,
} from '@/lib/calendarTypes';
import { formatShiftPastille, isPayrollRestDay } from '@/lib/employeeCalendarPlanning';

export interface EmployeeCalendarDayCellProps {
  day: number;
  isToday: boolean;
  plannedCalendar: PlannedEventData[];
  actualHours: ActualHoursData[];
  isForfaitJour: boolean;
  dayShifts?: Shift[];
  onDayClick?: (day: number) => void;
}

const DEFAULT_SCALE_HOURS = 10;

function CompactGauges({
  planned,
  actual,
  isForfaitJour,
}: {
  planned: number | null | undefined;
  actual: number | null | undefined;
  isForfaitJour: boolean;
}) {
  const hasPlanned = planned !== null && planned !== undefined;
  const hasActual = actual !== null && actual !== undefined;

  if (!hasPlanned && !hasActual) {
    return (
      <p className="text-[9px] text-muted-foreground/80 italic px-1.5 pb-1.5">—</p>
    );
  }

  if (isForfaitJour) {
    const pVal = hasPlanned ? (planned === 1 ? 1 : 0) : null;
    const aVal = hasActual ? (actual === 1 ? 1 : 0) : null;
    return (
      <div className="flex flex-col gap-1 px-1.5 pb-1.5">
        <GaugeMini label="P" filled={pVal === 1} barClass="bg-sky-500" />
        <GaugeMini label="R" filled={aVal === 1} barClass="bg-teal-500" />
      </div>
    );
  }

  const p = hasPlanned ? planned! : 0;
  const a = hasActual ? actual! : 0;
  const max = Math.max(DEFAULT_SCALE_HOURS, p, a, 1);
  const pPct = hasPlanned ? Math.min(100, (p / max) * 100) : 0;
  const aPct = hasActual ? Math.min(100, (a / max) * 100) : 0;

  return (
    <div className="flex flex-col gap-1 px-1.5 pb-1.5">
      <GaugeMini label="P" percent={pPct} barClass="bg-sky-500" />
      <GaugeMini label="R" percent={aPct} barClass="bg-teal-500" />
    </div>
  );
}

function GaugeMini({
  label,
  percent = 0,
  filled,
  barClass,
}: {
  label: string;
  percent?: number;
  filled?: boolean;
  barClass: string;
}) {
  const width = filled !== undefined ? (filled ? 100 : 0) : percent;
  return (
    <div className="flex items-center gap-1">
      <span className="text-[8px] font-semibold text-muted-foreground w-2">{label}</span>
      <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden">
        <div className={cn('h-full rounded-full', barClass)} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

export function EmployeeCalendarDayCell({
  day,
  isToday,
  plannedCalendar,
  actualHours,
  isForfaitJour,
  dayShifts = [],
  onDayClick,
}: EmployeeCalendarDayCellProps) {
  const dayData = plannedCalendar.find((d) => d.jour === day);
  const actualData = actualHours.find((d) => d.jour === day);
  const dayType = dayData?.type ?? 'weekend';
  const barColor = CALENDAR_TYPE_BAR_COLORS[dayType] ?? CALENDAR_TYPE_BAR_COLORS.weekend;
  const shiftPastille = formatShiftPastille(dayShifts);
  const shiftMismatch =
    shiftPastille != null && isPayrollRestDay(dayType) && dayShifts.length > 0;

  const content = (
    <>
      <div className="flex items-start justify-between gap-0.5 px-1.5 pt-1.5">
        <span className="text-xs font-semibold tabular-nums">{day}</span>
        {isToday && (
          <span className="text-[8px] font-medium text-primary leading-none">Auj.</span>
        )}
      </div>
      <p className="truncate px-1.5 text-[9px] font-medium text-muted-foreground leading-tight">
        {getCalendarTypeLabel(dayType)}
      </p>
      {dayType === 'travail' && (
        <CompactGauges
          planned={dayData?.heures_prevues}
          actual={actualData?.heures_faites}
          isForfaitJour={isForfaitJour}
        />
      )}
      {dayType !== 'travail' && dayData && (
        <p className="px-1.5 pb-1 text-[9px] text-muted-foreground tabular-nums">
          {formatCalendarValue(dayData.heures_prevues, isForfaitJour)}
        </p>
      )}
      {shiftPastille && (
        <p
          className={cn(
            'mx-1.5 mb-1.5 truncate rounded px-1 py-0.5 text-[8px] font-medium tabular-nums',
            shiftMismatch
              ? 'border border-amber-400/80 bg-amber-50/90 text-amber-950 dark:bg-amber-950/40 dark:text-amber-100'
              : 'bg-violet-100/90 text-violet-900 dark:bg-violet-950/50 dark:text-violet-100'
          )}
        >
          {shiftPastille}
        </p>
      )}
    </>
  );

  const className = cn(
    'relative flex h-full min-h-[5.5rem] w-full flex-col rounded-xl border bg-card text-left transition-colors',
    'hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
    isToday && 'ring-2 ring-primary'
  );

  if (onDayClick) {
    return (
      <button
        type="button"
        onClick={() => onDayClick(day)}
        className={className}
        aria-label={`${getCalendarTypeLabel(dayType)}, jour ${day}`}
      >
        <span className={cn('absolute left-0 top-2 bottom-2 w-1 rounded-r', barColor)} aria-hidden />
        {content}
      </button>
    );
  }

  return (
    <div className={className}>
      <span className={cn('absolute left-0 top-2 bottom-2 w-1 rounded-r', barColor)} aria-hidden />
      {content}
    </div>
  );
}
