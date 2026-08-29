import { useEffect, useMemo, useState } from 'react';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertTriangle, ChevronRight, RefreshCw } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { EmployeeCalendarOverviewRow, DayPatch } from '@/lib/schedulesOverview';
import { PlanningDayEditor } from './PlanningDayEditor';
import { useToast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';
import { isObservedHolidayHeaderDay } from '@/lib/companyCalendarHolidays';
import { useObservedPublicHolidays } from '@/hooks/useObservedPublicHolidays';
import { isEmployeeCadre } from '@/lib/mutuelleUtils';

const TYPE_BG: Record<string, string> = {
  travail: 'bg-sky-50 hover:bg-sky-100 border-sky-200/60',
  conge: 'bg-amber-50 hover:bg-amber-100 border-amber-200/60',
  ferie: 'bg-purple-50 hover:bg-purple-100 border-purple-200/60',
  arret_maladie: 'bg-red-50 hover:bg-red-100 border-red-200/60',
  weekend: 'bg-slate-50 hover:bg-slate-100 border-slate-200/60',
};

const TYPE_BAR: Record<string, string> = {
  travail: 'bg-sky-500',
  conge: 'bg-amber-500',
  ferie: 'bg-purple-500',
  arret_maladie: 'bg-red-500',
  weekend: 'bg-slate-400',
};

const TYPE_LABEL: Record<string, string> = {
  travail: 'Travail',
  conge: 'Congé',
  ferie: 'Férié',
  arret_maladie: 'Arrêt',
  weekend: 'Week-end',
};

const WEEKDAY_LABELS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

interface TeamPlanningViewProps {
  rows: EmployeeCalendarOverviewRow[];
  year: number;
  month: number;
  isLoading?: boolean;
  employeesLoadError?: boolean;
  employeesLoadErrorMessage?: string;
  onRetryEmployees?: () => void;
  unfilteredRowCount?: number;
  onApplyDayPatch: (
    employeeId: string,
    day: number,
    patch: DayPatch
  ) => Promise<boolean>;
  onOpenEmployee: (employeeId: string) => void;
  initialWeekIndex?: number | null;
  highlightDays?: number[];
  /** Sélection pour actions en masse — mêmes contrats que la vue Liste. */
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onToggleSelectAll: (ids: string[]) => void;
}

/** Calcule les semaines du mois sous forme de chunks de 7 jours, alignés sur le lundi. */
function computeWeeks(year: number, month: number): number[][] {
  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDow = (new Date(year, month - 1, 1).getDay() + 6) % 7; // 0 = lundi
  const weeks: number[][] = [];
  let current: number[] = Array(firstDow).fill(0);

  for (let d = 1; d <= daysInMonth; d++) {
    current.push(d);
    if (current.length === 7) {
      weeks.push(current);
      current = [];
    }
  }
  if (current.length > 0) {
    while (current.length < 7) current.push(0);
    weeks.push(current);
  }
  return weeks;
}

export function TeamPlanningView({
  rows,
  year,
  month,
  isLoading = false,
  employeesLoadError = false,
  employeesLoadErrorMessage,
  onRetryEmployees,
  unfilteredRowCount = 0,
  onApplyDayPatch,
  onOpenEmployee,
  initialWeekIndex = null,
  highlightDays = [],
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
}: TeamPlanningViewProps) {
  const { toast } = useToast();
  const { observedHolidayIds } = useObservedPublicHolidays();
  const weeks = useMemo(() => computeWeeks(year, month), [year, month]);
  const [weekIndex, setWeekIndex] = useState(0);
  const [openEditor, setOpenEditor] = useState<{ employeeId: string; day: number } | null>(null);
  const [flashDays, setFlashDays] = useState<number[]>([]);

  useEffect(() => {
    if (initialWeekIndex != null && initialWeekIndex >= 0) {
      setWeekIndex(Math.min(initialWeekIndex, weeks.length - 1));
    }
  }, [initialWeekIndex, year, month, weeks.length]);

  useEffect(() => {
    if (highlightDays.length === 0) return;
    setFlashDays(highlightDays);
    const t = window.setTimeout(() => setFlashDays([]), 5000);
    return () => window.clearTimeout(t);
  }, [highlightDays]);

  const todayIso = new Date().toDateString();

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    if (employeesLoadError) {
      return (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 py-12 text-center px-4">
          <AlertTriangle className="mx-auto h-8 w-8 text-destructive/70 mb-3" />
          <p className="text-sm text-destructive">
            {employeesLoadErrorMessage ?? 'Impossible de charger la liste des employés.'}
          </p>
          {onRetryEmployees && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-4 gap-2"
              onClick={onRetryEmployees}
            >
              <RefreshCw className="h-4 w-4" />
              Réessayer
            </Button>
          )}
        </div>
      );
    }

    if (unfilteredRowCount === 0) {
      return (
        <p className="text-sm text-muted-foreground text-center py-12">
          Aucun employé à piloter pour ce mois.
        </p>
      );
    }

    return (
      <p className="text-sm text-muted-foreground text-center py-12">
        Aucun employé ne correspond à vos filtres dans le planning.
      </p>
    );
  }

  const weekDays = weeks[Math.min(weekIndex, weeks.length - 1)] ?? [];

  const handleApply = async (
    employeeId: string,
    day: number,
    patch: DayPatch
  ): Promise<boolean> => {
    try {
      await onApplyDayPatch(employeeId, day, patch);
      toast({
        title: 'Jour mis à jour',
        description: `${new Date(year, month - 1, day).toLocaleDateString('fr-FR', {
          weekday: 'short',
          day: 'numeric',
          month: 'short',
        })} enregistré.`,
      });
      return true;
    } catch {
      toast({
        title: 'Erreur',
        description: 'La sauvegarde du jour a échoué.',
        variant: 'destructive',
      });
      return false;
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={String(weekIndex)} onValueChange={(v) => setWeekIndex(Number(v))}>
          <TabsList>
            {weeks.map((week, idx) => {
              const validDays = week.filter((d) => d > 0);
              const first = validDays[0];
              const last = validDays[validDays.length - 1];
              return (
                <TabsTrigger key={idx} value={String(idx)} className="text-xs">
                  Sem. {idx + 1}{' '}
                  <span className="ml-1 text-muted-foreground">
                    ({first}–{last})
                  </span>
                </TabsTrigger>
              );
            })}
          </TabsList>
        </Tabs>
        <p className="text-xs text-muted-foreground">
          Cliquez sur une cellule pour éditer · sur le nom pour ouvrir le calendrier complet
        </p>
      </div>

      <ScrollArea className="w-full rounded-md border">
        <div className="min-w-[760px]">
          <div className="grid grid-cols-[220px_repeat(7,minmax(90px,1fr))]">
            {/* Header */}
            <div className="bg-muted/60 border-b border-r p-2 text-xs font-medium sticky left-0 z-10 flex items-center gap-2">
              <Checkbox
                className="h-3.5 w-3.5"
                aria-label="Tout sélectionner"
                checked={
                  rows.length > 0 &&
                  rows.every((r) => selectedIds.has(r.employee.id))
                }
                onCheckedChange={() =>
                  onToggleSelectAll(rows.map((r) => r.employee.id))
                }
              />
              Collaborateur
            </div>
            {weekDays.map((day, i) => {
              if (day === 0) {
                return (
                  <div
                    key={`pad-${i}`}
                    className="bg-muted/30 border-b border-r last:border-r-0"
                  />
                );
              }
              const date = new Date(year, month - 1, day);
              const isToday = date.toDateString() === todayIso;
              const isHoliday = isObservedHolidayHeaderDay(
                year,
                month,
                day,
                observedHolidayIds
              );
              return (
                <div
                  key={day}
                  className={cn(
                    'border-b border-r last:border-r-0 p-2 text-center',
                    'bg-muted/60 text-xs font-medium',
                    isToday && 'bg-primary/10'
                  )}
                >
                  <div className={cn('uppercase', isToday && 'text-primary')}>
                    {WEEKDAY_LABELS[i]}
                  </div>
                  <div
                    className={cn(
                      'tabular-nums text-base font-semibold mt-0.5',
                      isToday && 'text-primary',
                      isHoliday && 'text-purple-600'
                    )}
                  >
                    {day}
                  </div>
                </div>
              );
            })}

            {/* Rows */}
            {rows.map((row) => (
              <div key={row.employee.id} className="contents">
                <div className="bg-background hover:bg-muted/40 transition-colors p-2 text-sm sticky left-0 z-10 border-b border-r flex items-center gap-2 group">
                  <Checkbox
                    className="h-3.5 w-3.5 shrink-0"
                    aria-label={`Sélectionner ${row.employee.last_name} ${row.employee.first_name}`}
                    checked={selectedIds.has(row.employee.id)}
                    onCheckedChange={() => onToggleSelect(row.employee.id)}
                  />
                  <button
                    type="button"
                    className="flex-1 min-w-0 text-left"
                    onClick={() => onOpenEmployee(row.employee.id)}
                    title="Ouvrir le calendrier complet"
                  >
                    <div className="truncate font-medium">
                      {row.employee.last_name} {row.employee.first_name}
                    </div>
                    <div className="text-[10px] text-muted-foreground truncate">
                      {row.employee.job_title ?? '—'}
                    </div>
                  </button>
                  {row.absenceConflictDays.length > 0 && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="text-xs">
                            Conflit absences : jours {row.absenceConflictDays.join(', ')}
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/0 group-hover:text-muted-foreground transition-colors" />
                </div>

                {weekDays.map((day, i) => {
                  if (day === 0) {
                    return (
                      <div
                        key={`pad-${row.employee.id}-${i}`}
                        className="bg-muted/30 border-b border-r last:border-r-0"
                      />
                    );
                  }
                  const planned = row.planned.find((p) => p.jour === day);
                  const actual = row.actual.find((a) => a.jour === day);
                  const type = planned?.type ?? 'travail';
                  const date = new Date(year, month - 1, day);
                  const isToday = date.toDateString() === todayIso;
                  const isOpen =
                    openEditor?.employeeId === row.employee.id &&
                    openEditor?.day === day;
                  const hasConflict = row.absenceConflictDays.includes(day);

                  const plannedDisplay =
                    !row.isForfaitJour && planned?.heures_prevues != null
                      ? `${planned.heures_prevues}h`
                      : null;
                  const actualDisplay =
                    !row.isForfaitJour && actual?.heures_faites != null
                      ? `${actual.heures_faites}h`
                      : null;
                  const forfaitDayDisplay = row.isForfaitJour
                    ? actual?.heures_faites === 1
                      ? 'Travaillé'
                      : planned?.heures_prevues === 1
                        ? 'Prévu'
                        : null
                    : null;
                  const hasDisplayedHours = plannedDisplay != null || actualDisplay != null;
                  const showCadreWithoutHours =
                    !hasDisplayedHours &&
                    !row.isForfaitJour &&
                    isEmployeeCadre(row.employee.statut);

                  return (
                    <Popover
                      key={`${row.employee.id}-${day}`}
                      open={isOpen}
                      onOpenChange={(open) =>
                        setOpenEditor(open ? { employeeId: row.employee.id, day } : null)
                      }
                    >
                      <PopoverTrigger asChild>
                        <button
                          type="button"
                          className={cn(
                            'group relative border-b border-r last:border-r-0 min-h-[3.25rem] px-1 py-1 text-left transition-all',
                            TYPE_BG[type] ?? 'bg-gray-50 hover:bg-gray-100',
                            isToday && 'ring-1 ring-primary/40',
                            flashDays.includes(day) &&
                              'ring-2 ring-emerald-400/80 bg-emerald-50/80',
                            isOpen && 'ring-2 ring-primary z-10',
                            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary'
                          )}
                          aria-label={`Éditer le ${day} pour ${row.employee.first_name} ${row.employee.last_name}`}
                        >
                          <div
                            className={cn(
                              'absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r',
                              TYPE_BAR[type] ?? 'bg-gray-300'
                            )}
                          />
                          <div className="pl-1.5 flex flex-col gap-0.5">
                            <span className="text-[9px] uppercase tracking-wide text-muted-foreground">
                              {TYPE_LABEL[type] ?? type}
                            </span>
                            {row.isForfaitJour ? (
                              forfaitDayDisplay ? (
                                <span
                                  className={cn(
                                    'text-xs font-medium',
                                    actual?.heures_faites === 1 ? 'text-teal-700' : 'text-sky-700'
                                  )}
                                >
                                  {forfaitDayDisplay}
                                </span>
                              ) : null
                            ) : showCadreWithoutHours ? (
                              <span className="text-xs font-medium text-slate-700">
                                Cadre
                              </span>
                            ) : (
                              <div className="flex items-baseline gap-1.5 text-xs tabular-nums">
                                <span
                                  className={cn(
                                    'font-medium',
                                    actualDisplay ? 'text-teal-700' : 'text-muted-foreground/40'
                                  )}
                                >
                                  {actualDisplay ?? '–'}
                                </span>
                                <span className="text-muted-foreground/60">/</span>
                                <span className="font-medium text-sky-700">
                                  {plannedDisplay ?? '–'}
                                </span>
                              </div>
                            )}
                          </div>
                          {hasConflict && (
                            <span
                              className="absolute top-1 right-1 h-1.5 w-1.5 rounded-full bg-amber-500"
                              aria-label="Conflit absence"
                            />
                          )}
                        </button>
                      </PopoverTrigger>
                      <PopoverContent
                        className="w-auto p-3"
                        align="center"
                        side="bottom"
                        sideOffset={4}
                      >
                        <PlanningDayEditor
                          employeeName={`${row.employee.first_name} ${row.employee.last_name}`}
                          employeeId={row.employee.id}
                          day={day}
                          year={year}
                          month={month}
                          isForfaitJour={row.isForfaitJour}
                          planned={planned}
                          actual={actual}
                          hasAbsenceConflict={hasConflict}
                          onApply={(patch) =>
                            handleApply(row.employee.id, day, patch)
                          }
                          onClose={() => setOpenEditor(null)}
                          onOpenFullCalendar={() => {
                            setOpenEditor(null);
                            onOpenEmployee(row.employee.id);
                          }}
                        />
                      </PopoverContent>
                    </Popover>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
        <ScrollBar orientation="horizontal" />
      </ScrollArea>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">Légende</span>
        {Object.entries(TYPE_LABEL).map(([type, label]) => (
          <span key={type} className="flex items-center gap-1.5">
            <span className={cn('w-3 h-3 rounded-sm border', TYPE_BG[type])} />
            {label}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="text-teal-700 font-medium">Réel</span>
          <span>/</span>
          <span className="text-sky-700 font-medium">Prévu</span>
        </span>
      </div>
    </div>
  );
}
