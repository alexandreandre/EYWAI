import type { AbsenceRequest } from '@/api/absences';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  formatAbsenceDateRange,
  getAbsenceTypeLabel,
} from '@/lib/employeeAbsencesUtils';
import { EmployeeAbsenceStatusBadge } from './EmployeeAbsenceStatusBadge';

interface EmployeeAbsenceDaySheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  day: Date | null;
  absences: AbsenceRequest[];
}

export function EmployeeAbsenceDaySheet({
  open,
  onOpenChange,
  day,
  absences,
}: EmployeeAbsenceDaySheetProps) {
  const title = day
    ? day.toLocaleDateString('fr-FR', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      })
    : '';

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>
            {absences.length === 0
              ? 'Aucune demande sur cette date.'
              : `${absences.length} demande${absences.length > 1 ? 's' : ''}`}
          </SheetDescription>
        </SheetHeader>
        {absences.length > 0 && (
          <ul className="mt-4 space-y-3">
            {absences.map((a) => (
              <li key={a.id} className="rounded-md border p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="font-medium text-sm">{getAbsenceTypeLabel(a)}</p>
                  <EmployeeAbsenceStatusBadge status={a.status} />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatAbsenceDateRange(a.selected_days)}
                </p>
                {a.comment && (
                  <p className="mt-2 text-xs italic text-muted-foreground">
                    {a.comment}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </SheetContent>
    </Sheet>
  );
}
