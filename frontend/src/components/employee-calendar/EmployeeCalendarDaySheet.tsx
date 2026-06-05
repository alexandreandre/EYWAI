import { Link } from 'react-router-dom';
import { format, startOfWeek } from 'date-fns';
import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import type { Shift } from '@/api/planning';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import {
  formatCalendarValue,
  getCalendarTypeLabel,
  CALENDAR_TYPE_BAR_COLORS,
} from '@/lib/calendarTypes';
import { dayHasSignificantEcart } from '@/lib/employeeCalendarUtils';
import { cn } from '@/lib/utils';
import { Plane } from 'lucide-react';
import { CompactShiftRow } from '@/components/employee-calendar/employeeShiftDisplay';

interface EmployeeCalendarDaySheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  day: number | null;
  year: number;
  month: number;
  planned?: PlannedEventData;
  actual?: ActualHoursData;
  isForfaitJour: boolean;
  dayShifts?: Shift[];
  isPayrollLoading?: boolean;
  isShiftsLoading?: boolean;
  onViewWeek?: (weekStartIso: string) => void;
}

export function EmployeeCalendarDaySheet({
  open,
  onOpenChange,
  day,
  year,
  month,
  planned,
  actual,
  isForfaitJour,
  dayShifts = [],
  isPayrollLoading = false,
  isShiftsLoading = false,
  onViewWeek,
}: EmployeeCalendarDaySheetProps) {
  if (day === null) return null;

  const date = new Date(year, month - 1, day);
  const dateLabel = date.toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
  const dayType = planned?.type ?? 'weekend';
  const barColor = CALENDAR_TYPE_BAR_COLORS[dayType] ?? CALENDAR_TYPE_BAR_COLORS.weekend;
  const hasEcart = dayHasSignificantEcart(
    planned?.heures_prevues,
    actual?.heures_faites,
    isForfaitJour
  );
  const showAbsenceLink = dayType === 'conge' || dayType === 'arret_maladie';

  const weekStartForDay = format(
    startOfWeek(date, { weekStartsOn: 1 }),
    'yyyy-MM-dd'
  );

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="max-h-[85vh] overflow-y-auto sm:max-w-md sm:mx-auto sm:rounded-t-xl">
        <SheetHeader>
          <SheetTitle className="capitalize">{dateLabel}</SheetTitle>
          <SheetDescription>
            Calendrier paie et créneaux publiés (lecture seule).
          </SheetDescription>
        </SheetHeader>

        <div className="mt-4 space-y-4">
          <section aria-labelledby="payroll-day-heading">
            <h3 id="payroll-day-heading" className="text-sm font-medium text-muted-foreground mb-2">
              Calendrier paie
            </h3>
            {isPayrollLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : (
              <>
                <div className="flex items-center gap-3">
                  <span className={cn('h-10 w-1 rounded-full shrink-0', barColor)} aria-hidden />
                  <div>
                    <p className="text-sm text-muted-foreground">Type de journée</p>
                    <p className="text-lg font-semibold">{getCalendarTypeLabel(dayType)}</p>
                  </div>
                </div>

                <dl className="mt-3 grid grid-cols-2 gap-3 rounded-lg border bg-muted/30 p-3 text-sm">
                  <div>
                    <dt className="text-muted-foreground">{isForfaitJour ? 'Prévu' : 'Heures prévues'}</dt>
                    <dd className="font-semibold tabular-nums">
                      {formatCalendarValue(planned?.heures_prevues, isForfaitJour)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">{isForfaitJour ? 'Réalisé' : 'Heures réalisées'}</dt>
                    <dd className="font-semibold tabular-nums">
                      {formatCalendarValue(actual?.heures_faites, isForfaitJour)}
                    </dd>
                  </div>
                </dl>

                {hasEcart && (
                  <p className="mt-3 rounded-md border border-amber-200/80 bg-amber-50/90 px-3 py-2 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
                    Écart notable entre le prévu et le réalisé sur cette journée.
                  </p>
                )}
              </>
            )}
          </section>

          <section aria-labelledby="shifts-day-heading" className="border-t pt-4">
            <h3 id="shifts-day-heading" className="text-sm font-medium mb-2">
              Créneaux publiés
            </h3>
            {isShiftsLoading ? (
              <div className="space-y-1.5">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
              </div>
            ) : dayShifts.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun créneau publié ce jour.</p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {dayShifts.map((shift) => (
                  <li key={shift.id}>
                    <CompactShiftRow shift={shift} />
                  </li>
                ))}
              </ul>
            )}
            {onViewWeek && (
              <Button
                type="button"
                variant="link"
                size="sm"
                className="mt-2 h-auto p-0"
                onClick={() => {
                  onOpenChange(false);
                  onViewWeek(weekStartForDay);
                }}
              >
                Voir la semaine
              </Button>
            )}
          </section>

          <div className="flex flex-col gap-2 border-t pt-2">
            {showAbsenceLink && (
              <Button variant="outline" className="justify-start" asChild>
                <Link to="/absences" onClick={() => onOpenChange(false)}>
                  <Plane className="mr-2 h-4 w-4" />
                  Voir mes demandes d&apos;absence
                </Link>
              </Button>
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
