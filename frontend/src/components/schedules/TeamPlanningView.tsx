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
import { CursorHint } from './CursorHint';
import { CalendarPeriodSelect } from './CalendarPeriodSelect';
import { usePaintSelect } from './usePaintSelect';
import { useToast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';
import { isObservedHolidayHeaderDay } from '@/lib/companyCalendarHolidays';
import { useObservedPublicHolidays } from '@/hooks/useObservedPublicHolidays';
import { isEmployeeCadre } from '@/lib/mutuelleUtils';
import { computePlanningWeeks, planningWeekIsoNumber } from '@/lib/planningWeeks';
// Source unique des couleurs/libellés (congé vert, arrêt rouge — partout
// pareil, y compris le calendrier complet du salarié).
import {
  CALENDAR_TYPE_BAR_COLORS as TYPE_BAR,
  CALENDAR_TYPE_BG_COLORS as TYPE_BG,
  CALENDAR_TYPE_LABELS as TYPE_LABEL,
} from '@/lib/calendarTypes';

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
  highlightDays?: number[];
  /** Sélection pour actions en masse — mêmes contrats que la vue Liste. */
  selectedIds: Set<string>;
  onSetSelected: (ids: string[], selected: boolean) => void;
  onToggleSelectAll: (ids: string[]) => void;
  onYearChange: (year: number) => void;
  onMonthChange: (month: number) => void;
  weekIndex: number;
  onWeekIndexChange: (index: number) => void;
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
  highlightDays = [],
  selectedIds,
  onSetSelected,
  onToggleSelectAll,
  onYearChange,
  onMonthChange,
  weekIndex,
  onWeekIndexChange,
}: TeamPlanningViewProps) {
  const { toast } = useToast();
  const { observedHolidayIds } = useObservedPublicHolidays();
  const weeks = useMemo(() => computePlanningWeeks(year, month), [year, month]);
  const rowIds = useMemo(() => rows.map((r) => r.employee.id), [rows]);
  const { onHandlePointerDown, onHandlePointerEnter } = usePaintSelect({
    ids: rowIds,
    selectedIds,
    onSetSelected,
  });
  const [openEditor, setOpenEditor] = useState<{ employeeId: string; day: number } | null>(null);
  const [flashDays, setFlashDays] = useState<number[]>([]);

  useEffect(() => {
    if (weekIndex > weeks.length - 1) {
      onWeekIndexChange(Math.max(0, weeks.length - 1));
    }
  }, [weekIndex, weeks.length, onWeekIndexChange]);

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
        <Tabs value={String(Math.min(weekIndex, weeks.length - 1))} onValueChange={(v) => onWeekIndexChange(Number(v))}>
          <TabsList>
            {weeks.map((week, idx) => {
              const validDays = week.filter((d) => d > 0);
              const first = validDays[0];
              const last = validDays[validDays.length - 1];
              const iso = planningWeekIsoNumber(year, month, week);
              return (
                <TabsTrigger key={idx} value={String(idx)} className="text-xs">
                  {iso ? `S${iso}` : `Sem. ${idx + 1}`}{' '}
                  <span className="ml-1 text-muted-foreground">
                    ({first}–{last})
                  </span>
                </TabsTrigger>
              );
            })}
          </TabsList>
        </Tabs>
        <CalendarPeriodSelect
          year={year}
          month={month}
          onYearChange={onYearChange}
          onMonthChange={onMonthChange}
          compact
        />
      </div>

      <ScrollArea className="w-full rounded-md border">
        <div className="min-w-[760px]">
          <div className="grid grid-cols-[252px_repeat(7,minmax(90px,1fr))]">
            {/* Header */}
            <button
              type="button"
              className={cn(
                'sticky left-0 z-10 flex w-full items-stretch border-b border-r text-left text-xs font-medium cursor-pointer transition-colors duration-150',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
                rows.length > 0 &&
                  rows.every((r) => selectedIds.has(r.employee.id))
                  ? 'bg-[color-mix(in_srgb,hsl(var(--primary))_18%,hsl(var(--background)))]'
                  : 'bg-muted/60',
                'hover:bg-[color-mix(in_srgb,hsl(var(--primary))_28%,hsl(var(--background)))] hover:text-primary',
              )}
              onClick={() => onToggleSelectAll(rows.map((r) => r.employee.id))}
              aria-label="Tout sélectionner - Saisie rapide"
              aria-pressed={
                rows.length > 0 &&
                rows.every((r) => selectedIds.has(r.employee.id))
              }
            >
              <span className="flex w-11 shrink-0 items-center justify-center border-r border-border/60 bg-muted/25">
                <Checkbox
                  className="h-4 w-4 shrink-0 pointer-events-none"
                  aria-hidden
                  tabIndex={-1}
                  checked={
                    rows.length > 0 &&
                    rows.every((r) => selectedIds.has(r.employee.id))
                  }
                />
              </span>
              <span className="flex items-center px-2 py-2 leading-snug">
                Tout sélectionner - Saisie rapide
              </span>
            </button>
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
            {rows.map((row, rowIndex) => (
              <div key={row.employee.id} className="contents">
                <div
                  className="group/open bg-background p-0 text-sm sticky left-0 z-10 border-b border-r flex items-stretch"
                  onPointerEnter={() => onHandlePointerEnter(rowIndex)}
                >
                  <div
                    role="checkbox"
                    aria-checked={selectedIds.has(row.employee.id)}
                    aria-label={`Sélectionner ${row.employee.last_name} ${row.employee.first_name}`}
                    className="flex w-11 shrink-0 items-center justify-center select-none cursor-pointer border-r border-border/60 bg-muted/25 hover:bg-primary/20 transition-colors"
                    tabIndex={0}
                    onPointerDown={(event) => onHandlePointerDown(event, rowIndex)}
                    onKeyDown={(event) => {
                      if (event.key !== ' ' && event.key !== 'Enter') return;
                      event.preventDefault();
                      onSetSelected(
                        [row.employee.id],
                        !selectedIds.has(row.employee.id),
                      );
                    }}
                  >
                    <Checkbox
                      className="h-4 w-4 shrink-0 pointer-events-none"
                      aria-hidden
                      tabIndex={-1}
                      checked={selectedIds.has(row.employee.id)}
                    />
                  </div>
                  <CursorHint
                    label="Ouvrir le calendrier complet"
                    className="flex min-w-0 flex-1"
                  >
                    <button
                      type="button"
                      className="flex min-w-0 flex-1 items-center gap-1 px-1.5 py-1.5 text-left cursor-pointer transition-colors duration-150 hover:bg-[color-mix(in_srgb,hsl(var(--primary))_28%,hsl(var(--background)))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                      onClick={() => onOpenEmployee(row.employee.id)}
                      aria-label="Ouvrir le calendrier complet"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium group-hover/open:text-primary">
                          {row.employee.last_name} {row.employee.first_name}
                        </span>
                        <span className="block truncate text-[10px] text-muted-foreground group-hover/open:text-primary/80">
                          {row.employee.job_title ?? '—'}
                        </span>
                      </span>
                      <ChevronRight className="h-4 w-3.5 shrink-0 text-muted-foreground/50 transition-all duration-150 group-hover/open:text-primary group-hover/open:opacity-100 motion-safe:group-hover/open:translate-x-1" />
                    </button>
                  </CursorHint>
                  {row.absenceConflictDays.length > 0 && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0 self-center mr-1.5" />
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="text-xs">
                            Conflit absences : jours {row.absenceConflictDays.join(', ')}
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
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
