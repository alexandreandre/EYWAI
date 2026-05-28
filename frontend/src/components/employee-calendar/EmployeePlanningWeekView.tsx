import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { addDays, addWeeks, format, parseISO, startOfWeek } from 'date-fns';
import { fr } from 'date-fns/locale';
import {
  ChevronLeft,
  ChevronRight,
  Download,
  Info,
  Loader2,
  Plane,
  Stethoscope,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { Shift } from '@/api/planning';
import { exportPlanningPDF, getMyPlanning } from '@/api/planning-employee';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/use-toast';
import { ShiftBlock } from '@/components/planning/ShiftBlock';
import { WeekHeader } from '@/components/planning/WeekHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import {
  dayNumberFromIso,
  normShiftDay,
  yearMonthFromWeekStart,
} from '@/lib/employeeCalendarPlanning';
import { apiErrorDetail } from '@/lib/badgeuseApiUtils';
import { cn } from '@/lib/utils';
import { isAxiosError } from 'axios';

function maxFutureMondayIso(): string {
  return format(addWeeks(startOfWeek(new Date(), { weekStartsOn: 1 }), 12), 'yyyy-MM-dd');
}

function buildWeekDays(weekStart: string, weekEnd: string): string[] {
  try {
    const start = parseISO(weekStart.slice(0, 10));
    const end = parseISO(weekEnd.slice(0, 10));
    const out: string[] = [];
    for (let d = start; d <= end; d = addDays(d, 1)) {
      out.push(format(d, 'yyyy-MM-dd'));
    }
    if (out.length === 7) return out;
  } catch {
    /* fallback */
  }
  const monday = startOfWeek(parseISO(weekStart.slice(0, 10)), { weekStartsOn: 1 });
  return Array.from({ length: 7 }, (_, i) => format(addDays(monday, i), 'yyyy-MM-dd'));
}

function dayLabel(iso: string): string {
  const d = parseISO(iso);
  return format(d, 'EEE dd/MM', { locale: fr }).replace(/^\w/, (c) => c.toUpperCase());
}

function shiftDurationMinutes(s: Shift): number {
  const toSec = (t: string) => {
    const parts = t.split(':').map((x) => Number(x));
    return (parts[0] || 0) * 3600 + (parts[1] || 0) * 60 + (parts[2] || 0);
  };
  const a = toSec(s.start_time);
  let b = toSec(s.end_time);
  if (b <= a) b += 24 * 3600;
  return Math.round((b - a) / 60);
}

function statusBadge(status: string): { label: string; className: string } | null {
  if (status === 'draft') return null;
  if (status === 'locked') {
    return {
      label: 'Verrouillé',
      className: 'bg-slate-200 text-slate-800 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-100',
    };
  }
  if (status === 'published' || status === 'partially_published') {
    return {
      label: status === 'partially_published' ? 'Partiellement publié' : 'Publié',
      className: 'bg-green-100 text-green-900 hover:bg-green-100 dark:bg-green-950 dark:text-green-100',
    };
  }
  return {
    label: status,
    className: 'bg-muted text-muted-foreground',
  };
}

function formatWeekRange(weekStart: string, weekEnd: string): string {
  try {
    const a = format(parseISO(weekStart.slice(0, 10)), 'd/MM', { locale: fr });
    const b = format(parseISO(weekEnd.slice(0, 10)), 'd/MM', { locale: fr });
    return `Semaine du ${a} au ${b}`;
  } catch {
    return `Semaine du ${weekStart} au ${weekEnd}`;
  }
}

export interface EmployeePlanningWeekViewProps {
  weekStart: string;
  onWeekStartChange: (iso: string) => void;
  onDayClick?: (payload: {
    iso: string;
    day: number;
    year: number;
    month: number;
    shifts: Shift[];
  }) => void;
  onPlanningStatusChange?: (status: string | null) => void;
  showToolbar?: boolean;
}

export function EmployeePlanningWeekView({
  weekStart,
  onWeekStartChange,
  onDayClick,
  onPlanningStatusChange,
  showToolbar = true,
}: EmployeePlanningWeekViewProps) {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const prevStatusByWeekRef = useRef<Record<string, string | null>>({});

  const query = useQuery({
    queryKey: ['my-planning', weekStart, activeCompany?.company_id],
    queryFn: () => getMyPlanning(weekStart),
    enabled: Boolean(weekStart),
  });

  const planning = query.data;
  const myEmployeeId = planning?.employee_id ?? user?.id ?? '';

  const planningLoadError = query.isError
    ? (() => {
        const detail = apiErrorDetail(
          query.error,
          'Impossible de charger votre planning.',
        );
        if (
          isAxiosError(query.error) &&
          query.error.response?.status === 404 &&
          /profil|collaborateur|salarié/i.test(detail)
        ) {
          return (
            <>
              Votre compte n&apos;est pas relié à une fiche salarié dans cette
              entreprise. Demandez au service RH de lier votre compte, ou
              connectez-vous avec l&apos;e-mail de votre fiche collaborateur.
            </>
          );
        }
        return detail;
      })()
    : null;

  useEffect(() => {
    if (!planning) {
      onPlanningStatusChange?.(null);
      return;
    }
    const prev = prevStatusByWeekRef.current[weekStart] ?? null;
    if (prev === 'draft' && planning.status !== 'draft') {
      toast({
        title: 'Planning publié',
        description: 'Votre planning de la semaine a été publié.',
      });
    }
    prevStatusByWeekRef.current[weekStart] = planning.status;
    onPlanningStatusChange?.(planning.status);
  }, [planning, weekStart, toast, onPlanningStatusChange]);

  const weekDays = useMemo(() => {
    if (!planning) return buildWeekDays(weekStart, format(addDays(parseISO(weekStart), 6), 'yyyy-MM-dd'));
    return buildWeekDays(planning.week_start, planning.week_end);
  }, [planning, weekStart]);

  const shiftsByDay = useMemo(() => {
    const map: Record<string, Shift[]> = {};
    for (const d of weekDays) {
      map[d] = [];
    }
    if (!planning?.shifts) return map;
    for (const s of planning.shifts) {
      const d = normShiftDay(s.shift_date);
      if (!map[d]) map[d] = [];
      map[d].push(s);
    }
    for (const d of weekDays) {
      map[d].sort((a, b) => a.start_time.localeCompare(b.start_time));
    }
    return map;
  }, [planning?.shifts, weekDays]);

  const dayMeta = useMemo(() => {
    const meta: Record<string, { totalMinutes: number; uniqueStaff: Set<string> }> = {};
    for (const d of weekDays) {
      meta[d] = { totalMinutes: 0, uniqueStaff: new Set() };
    }
    if (!planning?.shifts) return meta;
    for (const s of planning.shifts) {
      const d = normShiftDay(s.shift_date);
      if (!meta[d]) continue;
      meta[d].totalMinutes += shiftDurationMinutes(s);
      meta[d].uniqueStaff.add(s.employee_id);
    }
    return meta;
  }, [planning?.shifts, weekDays]);

  const maxWeek = maxFutureMondayIso();
  const canGoNext = weekStart < maxWeek;

  const goPrev = () => {
    const d = parseISO(weekStart.slice(0, 10));
    onWeekStartChange(format(addWeeks(d, -1), 'yyyy-MM-dd'));
  };

  const goNext = () => {
    if (!canGoNext) return;
    const d = parseISO(weekStart.slice(0, 10));
    onWeekStartChange(format(addWeeks(d, 1), 'yyyy-MM-dd'));
  };

  const exportMutation = useMutation({
    mutationFn: () => exportPlanningPDF(weekStart),
    onError: () => {
      toast({
        title: 'Export impossible',
        description: 'Le PDF n’a pas pu être généré. Réessayez plus tard.',
        variant: 'destructive',
      });
    },
  });

  const noop = useCallback(() => {}, []);

  const badge = planning ? statusBadge(planning.status) : null;
  const isDraft = planning?.status === 'draft';
  const canExportPdf =
    Boolean(planning) && !isDraft && !query.isLoading && !query.isError;

  const rangeLabel = planning
    ? formatWeekRange(planning.week_start, planning.week_end)
    : formatWeekRange(weekStart, format(addDays(parseISO(weekStart.slice(0, 10)), 6), 'yyyy-MM-dd'));

  const handleDayOpen = (iso: string) => {
    if (!onDayClick) return;
    const { year, month } = yearMonthFromWeekStart(iso);
    onDayClick({
      iso,
      day: dayNumberFromIso(iso),
      year,
      month,
      shifts: shiftsByDay[iso] ?? [],
    });
  };

  return (
    <div className="flex flex-col">
      <div className="border-b bg-muted/25 px-4 py-4 md:px-6">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex flex-1 items-center justify-center gap-1 sm:justify-start">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={goPrev}
                aria-label="Semaine précédente"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="min-w-[12rem] text-center text-lg font-semibold sm:min-w-[16rem]">
                {rangeLabel}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={goNext}
                disabled={!canGoNext}
                aria-label="Semaine suivante"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>

            {showToolbar ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 shrink-0 text-xs sm:ml-auto"
                disabled={exportMutation.isPending || !canExportPdf}
                onClick={() => exportMutation.mutate()}
              >
                {exportMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                ) : (
                  <Download className="mr-2 h-4 w-4" aria-hidden />
                )}
                Exporter PDF
              </Button>
            ) : null}
          </div>

          {(isDraft || badge || planning?.team_view_enabled) && (
            <div className="flex flex-wrap items-center justify-center gap-1.5 sm:justify-start">
              {isDraft ? (
                <Badge variant="outline" className="text-xs font-normal">
                  Non publiée
                </Badge>
              ) : badge ? (
                <Badge className={cn('text-xs font-normal', badge.className)}>{badge.label}</Badge>
              ) : null}
              {planning?.team_view_enabled ? (
                <Badge variant="secondary" className="text-xs font-normal">
                  Vision équipe
                </Badge>
              ) : null}
            </div>
          )}

          <div className="flex gap-2 rounded-md border border-border/60 bg-background/80 px-3 py-2.5 text-xs text-muted-foreground">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/80" aria-hidden />
            <p>
              Calendrier paie : consultez l&apos;onglet{' '}
              <span className="font-medium text-foreground">Mois</span> pour le prévu / réalisé
              mensuel.
            </p>
          </div>
        </div>
      </div>

      <div className="px-4 py-4 md:px-6 md:py-5">
        {query.isLoading ? (
          <div className="space-y-3 rounded-lg border p-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        ) : query.isError ? (
          <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-10 text-center text-sm text-destructive">
            {planningLoadError}
          </p>
        ) : isDraft ? (
          <div className="flex min-h-[200px] flex-col items-center justify-center rounded-lg border border-dashed bg-muted/30 px-6 py-12 text-center">
            <p className="text-sm font-medium text-foreground">
              Cette semaine n&apos;est pas encore publiée
            </p>
            <p className="mt-1 max-w-sm text-xs text-muted-foreground">
              Vos créneaux apparaîtront ici dès publication par votre service RH.
            </p>
          </div>
        ) : planning ? (
        <div className="w-full overflow-x-auto rounded-lg border">
          <div className="grid min-w-[720px] grid-cols-7 gap-0 divide-x">
            {weekDays.map((d) => {
              const list = shiftsByDay[d] ?? [];
              const dm = dayMeta[d];
              const totalHours = (dm?.totalMinutes ?? 0) / 60;
              const staffCount = dm?.uniqueStaff.size ?? 0;
              return (
                <div key={d} className="flex min-w-0 flex-col bg-background">
                  <button
                    type="button"
                    className="border-b bg-muted/40 px-1 py-2 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    onClick={() => handleDayOpen(d)}
                    disabled={!onDayClick}
                  >
                    <WeekHeader
                      date={d}
                      label={dayLabel(d)}
                      isLocked={false}
                      totalHours={totalHours}
                      staffCount={staffCount}
                      onLockDay={noop}
                      isRH={false}
                    />
                  </button>
                  <div
                    className={cn(
                      'flex min-h-[200px] flex-col gap-1.5 p-1.5',
                      onDayClick && 'cursor-pointer'
                    )}
                    role={onDayClick ? 'button' : undefined}
                    tabIndex={onDayClick ? 0 : undefined}
                    onClick={onDayClick ? () => handleDayOpen(d) : undefined}
                    onKeyDown={
                      onDayClick
                        ? (e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              handleDayOpen(d);
                            }
                          }
                        : undefined
                    }
                  >
                    {list.length === 0 ? (
                      <div className="min-h-[120px] flex-1 rounded-md bg-muted/30" aria-label="Aucun shift" />
                    ) : (
                      list.map((shift) => {
                        const colleague =
                          planning.team_view_enabled &&
                          Boolean(myEmployeeId) &&
                          shift.employee_id !== myEmployeeId;
                        return (
                          <div
                            key={shift.id}
                            className={colleague ? 'opacity-50' : undefined}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ShiftBlock shift={shift} onClick={noop} isLocked />
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        ) : null}
      </div>

      <div className="flex flex-col gap-2 border-t bg-muted/20 px-4 py-4 sm:flex-row md:px-6">
        <Button
          type="button"
          variant="default"
          className="flex-1"
          onClick={() => navigate('/absences')}
        >
          <Plane className="mr-2 h-4 w-4" aria-hidden />
          Demander un congé
        </Button>
        <Button
          type="button"
          variant="outline"
          className="flex-1"
          onClick={() => navigate('/absences')}
        >
          <Stethoscope className="mr-2 h-4 w-4" aria-hidden />
          Signaler une absence
        </Button>
      </div>
    </div>
  );
}
