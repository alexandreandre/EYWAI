import { useCallback, useEffect, useState, type CSSProperties } from 'react';
import { displayNamePrenomNom } from '@/lib/employeeName';
import { Link } from 'react-router-dom';
import {
  Sheet,
  SheetContent,
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
  /** Début de la première paie Martine (bascule) : avant, rien n'est compté. */
  debutMartine?: string | null;
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
  debutMartine = null,
}: CalendarEmployeeDrawerProps) {
  const currentIndex = employee
    ? orderedEmployees.findIndex((e) => e.id === employee.id)
    : -1;
  const hasPrev = currentIndex > 0;
  // Hauteur de l'en-tête collant du tiroir : l'en-tête des jours du mois se
  // colle juste dessous quand on descend dans le calendrier.
  const [entete, setEntete] = useState<HTMLDivElement | null>(null);
  const [hauteurEntete, setHauteurEntete] = useState(0);
  useEffect(() => {
    if (!entete) return;
    setHauteurEntete(entete.offsetHeight);
    if (typeof ResizeObserver === 'undefined') return;
    const observateur = new ResizeObserver(() => setHauteurEntete(entete.offsetHeight));
    observateur.observe(entete);
    return () => observateur.disconnect();
  }, [entete]);
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

  const employeeName = displayNamePrenomNom(employee);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[min(92vw,900px)] overflow-y-auto p-0"
        style={{ '--entete-tiroir': `${hauteurEntete}px` } as CSSProperties}
      >
        <div
          ref={setEntete}
          className="flex flex-col space-y-2 text-center sm:text-left sticky top-0 z-30 bg-background border-b px-6 py-4"
        >
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
        </div>

        <div className="px-4 py-4">
          <EmployeeCalendarPanel
            key={employee.id}
            employeeId={employee.id}
            employeeName={employeeName}
            employeeStatut={employee.statut ?? undefined}
            employeeIsForfaitJour={employee.is_forfait_jour}
            employeeSortie={{
              exit_last_working_day: employee.exit_last_working_day,
              hire_date: employee.hire_date,
            }}
            initialYear={year}
            initialMonth={month}
            onSaved={onSaved}
            debutMartine={debutMartine}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
