import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import { computeEmployeeCalendarSummary } from '@/lib/calendarStats';
import { cn } from '@/lib/utils';

interface EmployeeCalendarMonthSummaryProps {
  plannedCalendar: PlannedEventData[];
  actualHours: ActualHoursData[];
  isForfaitJour: boolean;
  className?: string;
}

const AIDE_HEURES_AU_DELA =
  'Excédent des heures faites sur l\'horaire prévu, jour par jour. Les heures supplémentaires du bulletin se comptent à la semaine : cette tuile ne les annonce pas.';

function formatHours(value: number): string {
  return `${value.toFixed(1)} h`;
}

export function EmployeeCalendarMonthSummary({
  plannedCalendar,
  actualHours,
  isForfaitJour,
  className,
}: EmployeeCalendarMonthSummaryProps) {
  const stats = computeEmployeeCalendarSummary(
    plannedCalendar,
    actualHours,
    isForfaitJour
  );

  const items = isForfaitJour
    ? [
        { label: 'Jours travaillés', value: String(stats.heuresFaites) },
        {
          label: 'Heures au-delà du prévu',
          aide: AIDE_HEURES_AU_DELA,
          value: formatHours(stats.heuresSupplementaires),
        },
        { label: 'Congés pris', value: `${stats.congesPris} j` },
        { label: 'Jours d\'absence', value: `${stats.heuresAbsence} j` },
      ]
    : [
        { label: 'Heures faites', value: formatHours(stats.heuresFaites) },
        {
          label: 'Heures au-delà du prévu',
          aide: AIDE_HEURES_AU_DELA,
          value: formatHours(stats.heuresSupplementaires),
        },
        { label: 'Congés pris', value: `${stats.congesPris} j` },
        { label: 'Heures d\'absence', value: formatHours(stats.heuresAbsence) },
      ];

  return (
    <div
      className={cn(
        'flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground',
        className
      )}
    >
      {items.map(({ label, value, aide }: { label: string; value: string; aide?: string }) => (
        <span key={label} title={aide} className={aide ? 'cursor-help' : undefined}>
          {label} :{' '}
          <strong className="font-medium text-foreground tabular-nums">{value}</strong>
        </span>
      ))}
    </div>
  );
}
