import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import { getMyBadgeuseStatusToday } from '@/api/badgeuse';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { formatCalendarValue, getCalendarTypeLabel } from '@/lib/calendarTypes';
import { formatSecondsToHoursMinutes, formatTimeFr } from '@/lib/badgeuseFormat';
import { Plane } from 'lucide-react';

interface EmployeeCalendarDaySheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  day: number | null;
  year: number;
  month: number;
  planned?: PlannedEventData;
  actual?: ActualHoursData;
  isForfaitJour: boolean;
  isPayrollLoading?: boolean;
}

function DoneSlotsList({
  sequences,
  isLoading,
  isEligible,
}: {
  sequences: { start: string; end: string; duration_seconds: number }[];
  isLoading: boolean;
  isEligible: boolean;
}) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-11 w-full" />
        <Skeleton className="h-11 w-full" />
      </div>
    );
  }

  if (!isEligible) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucun pointage badgeuse pour cette journée.
      </p>
    );
  }

  if (sequences.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucun créneau pointé ce jour.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {sequences.map((seq) => (
        <li
          key={`${seq.start}-${seq.end}`}
          className="flex items-center gap-3 rounded-lg border bg-muted/25 px-3 py-2.5"
        >
          <span
            className="h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-500"
            aria-hidden
          />
          <div className="flex min-w-0 flex-1 items-baseline justify-between gap-3">
            <span className="text-sm font-semibold tabular-nums">
              {formatTimeFr(seq.start)} – {formatTimeFr(seq.end)}
            </span>
            <span className="text-xs text-muted-foreground tabular-nums shrink-0">
              {formatSecondsToHoursMinutes(seq.duration_seconds)}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
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
  isPayrollLoading = false,
}: EmployeeCalendarDaySheetProps) {
  const dayIso =
    day !== null ? format(new Date(year, month - 1, day), 'yyyy-MM-dd') : '';

  const badgeuseQuery = useQuery({
    queryKey: ['badgeuse', 'calendar-day', dayIso],
    queryFn: () => getMyBadgeuseStatusToday(dayIso),
    enabled: open && day !== null,
    staleTime: 30_000,
  });

  if (day === null) return null;

  const date = new Date(year, month - 1, day);
  const dateLabel = date.toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
  const dayType = planned?.type ?? 'weekend';
  const showAbsenceLink = dayType === 'conge' || dayType === 'arret_maladie';
  const sequences = badgeuseQuery.data?.sequences ?? [];
  const isBadgeuseEligible = badgeuseQuery.data?.is_eligible_for_badgeuse ?? false;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="max-h-[85vh] overflow-y-auto sm:max-w-md sm:mx-auto sm:rounded-t-xl"
      >
        <SheetHeader className="text-left">
          <SheetTitle className="capitalize text-xl">{dateLabel}</SheetTitle>
        </SheetHeader>

        <div className="mt-4 space-y-5">
          {isPayrollLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-full" />
            </div>
          ) : (
            <>
              <p className="text-xs text-muted-foreground">
                Type de journée :{' '}
                <span className="text-foreground">{getCalendarTypeLabel(dayType)}</span>
              </p>

              <div className="space-y-1 text-sm">
                <p>
                  <span className="text-muted-foreground">Heures faites : </span>
                  <span className="font-semibold tabular-nums">
                    {formatCalendarValue(actual?.heures_faites, isForfaitJour)}
                  </span>
                </p>
                <p>
                  <span className="text-muted-foreground">Heures prévues : </span>
                  <span className="font-semibold tabular-nums">
                    {formatCalendarValue(planned?.heures_prevues, isForfaitJour)}
                  </span>
                </p>
              </div>
            </>
          )}

          <section aria-labelledby="done-slots-heading">
            <h3 id="done-slots-heading" className="mb-2 text-sm font-medium">
              Créneaux faits
            </h3>
            <DoneSlotsList
              sequences={sequences}
              isLoading={badgeuseQuery.isLoading}
              isEligible={isBadgeuseEligible}
            />
          </section>

          {showAbsenceLink && (
            <div className="border-t pt-3">
              <Button variant="outline" className="w-full justify-start" asChild>
                <Link to="/absences" onClick={() => onOpenChange(false)}>
                  <Plane className="mr-2 h-4 w-4" />
                  Voir mes demandes d&apos;absence
                </Link>
              </Button>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
