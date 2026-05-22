import { useCallback, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react';
import { EmployeeCalendarPanel } from '@/components/schedules/EmployeeCalendarPanel';
import type { SchedulesEmployeeInput } from '@/lib/schedulesOverview';

interface CalendarEmployeeDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employee: SchedulesEmployeeInput | null;
  orderedEmployees: SchedulesEmployeeInput[];
  year: number;
  month: number;
  onNavigate: (employeeId: string) => void;
  onSaved?: () => void;
}

export function CalendarEmployeeDrawer({
  open,
  onOpenChange,
  employee,
  orderedEmployees,
  year,
  month,
  onNavigate,
  onSaved,
}: CalendarEmployeeDrawerProps) {
  const currentIndex = employee
    ? orderedEmployees.findIndex((e) => e.id === employee.id)
    : -1;
  const hasPrev = currentIndex > 0;
  const hasNext =
    currentIndex >= 0 && currentIndex < orderedEmployees.length - 1;

  const goPrev = useCallback(() => {
    if (hasPrev) onNavigate(orderedEmployees[currentIndex - 1].id);
  }, [hasPrev, currentIndex, orderedEmployees, onNavigate]);

  const goNext = useCallback(() => {
    if (hasNext) onNavigate(orderedEmployees[currentIndex + 1].id);
  }, [hasNext, currentIndex, orderedEmployees, onNavigate]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') goPrev();
      if (e.key === 'ArrowRight') goNext();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, goPrev, goNext]);

  if (!employee) {
    return (
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="sm:max-w-md" />
      </Sheet>
    );
  }

  const employeeName = `${employee.first_name} ${employee.last_name}`;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[min(92vw,900px)] overflow-y-auto p-0"
      >
        <SheetHeader className="sticky top-0 z-10 bg-background border-b px-6 py-4">
          <div className="flex items-center justify-between gap-2">
            <SheetTitle className="text-left text-base font-semibold">
              Calendrier — {employeeName}
            </SheetTitle>
            <div className="flex items-center gap-1 shrink-0">
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                disabled={!hasPrev}
                onClick={goPrev}
                aria-label="Employé précédent"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                disabled={!hasNext}
                onClick={goNext}
                aria-label="Employé suivant"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="sm" className="h-8 gap-1.5" asChild>
                <Link to={`/employees/${employee.id}?tab=calendrier`}>
                  <ExternalLink className="h-3.5 w-3.5" />
                  Fiche
                </Link>
              </Button>
            </div>
          </div>
          {orderedEmployees.length > 1 && (
            <p className="text-xs text-muted-foreground text-left">
              {currentIndex + 1} / {orderedEmployees.length} — flèches ← → pour naviguer
            </p>
          )}
        </SheetHeader>

        <div className="px-4 py-4">
          <EmployeeCalendarPanel
            key={employee.id}
            employeeId={employee.id}
            employeeName={employeeName}
            employeeStatut={employee.statut ?? undefined}
            initialYear={year}
            initialMonth={month}
            onSaved={onSaved}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
