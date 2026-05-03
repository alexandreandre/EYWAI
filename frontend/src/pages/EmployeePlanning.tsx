import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { addDays, addWeeks, format, parseISO, startOfWeek } from 'date-fns';
import { fr } from 'date-fns/locale';
import { ChevronLeft, ChevronRight, Download, Loader2 } from 'lucide-react';
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

function defaultMondayIso(): string {
  return format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd');
}

function maxFutureMondayIso(): string {
  return format(addWeeks(startOfWeek(new Date(), { weekStartsOn: 1 }), 12), 'yyyy-MM-dd');
}

function normDay(d: string): string {
  return d.slice(0, 10);
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

export default function EmployeePlanning() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const [weekStart, setWeekStart] = useState(defaultMondayIso);

  const prevStatusByWeekRef = useRef<Record<string, string | null>>({});

  const query = useQuery({
    queryKey: ['my-planning', weekStart, activeCompany?.company_id],
    queryFn: () => getMyPlanning(weekStart),
    enabled: Boolean(weekStart),
  });

  const planning = query.data;
  const myEmployeeId = user?.id ?? '';

  useEffect(() => {
    if (!planning) return;
    const prev = prevStatusByWeekRef.current[weekStart] ?? null;
    if (prev === 'draft' && planning.status !== 'draft') {
      toast({
        title: 'Planning publié',
        description: 'Votre planning de la semaine a été publié.',
      });
    }
    prevStatusByWeekRef.current[weekStart] = planning.status;
  }, [planning, weekStart, toast]);

  const weekDays = useMemo(() => {
    if (!planning) return [];
    return buildWeekDays(planning.week_start, planning.week_end);
  }, [planning]);

  const shiftsByDay = useMemo(() => {
    const map: Record<string, Shift[]> = {};
    if (!planning?.shifts) return map;
    for (const d of weekDays) {
      map[d] = [];
    }
    for (const s of planning.shifts) {
      const d = normDay(s.shift_date);
      if (!map[d]) map[d] = [];
      map[d].push(s);
    }
    for (const d of weekDays) {
      map[d].sort((a, b) => a.start_time.localeCompare(b.start_time));
    }
    return map;
  }, [planning?.shifts, weekDays]);

  const dayMeta = useMemo(() => {
    const meta: Record<
      string,
      { totalMinutes: number; uniqueStaff: Set<string> }
    > = {};
    for (const d of weekDays) {
      meta[d] = { totalMinutes: 0, uniqueStaff: new Set() };
    }
    if (!planning?.shifts) return meta;
    for (const s of planning.shifts) {
      const d = normDay(s.shift_date);
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
    setWeekStart(format(addWeeks(d, -1), 'yyyy-MM-dd'));
  };

  const goNext = () => {
    if (!canGoNext) return;
    const d = parseISO(weekStart.slice(0, 10));
    setWeekStart(format(addWeeks(d, 1), 'yyyy-MM-dd'));
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

  const rangeLabel = planning
    ? formatWeekRange(planning.week_start, planning.week_end)
    : formatWeekRange(weekStart, format(addDays(parseISO(weekStart.slice(0, 10)), 6), 'yyyy-MM-dd'));

  return (
    <div className="container max-w-5xl space-y-6 py-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Mon planning</h1>
          <p className="text-sm text-muted-foreground">Vue semaine (lecture seule)</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {badge ? <Badge className={badge.className}>{badge.label}</Badge> : null}
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={exportMutation.isPending || query.isLoading || planning?.status === 'draft'}
            onClick={() => exportMutation.mutate()}
          >
            {exportMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Download className="mr-2 h-4 w-4" aria-hidden />
            )}
            Exporter PDF
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" size="icon" onClick={goPrev} aria-label="Semaine précédente">
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={goNext}
          disabled={!canGoNext}
          aria-label="Semaine suivante"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        <span className="text-sm font-medium">{rangeLabel}</span>
      </div>

      {planning?.team_view_enabled ? (
        <Badge variant="secondary" className="w-fit">
          Vision équipe activée
        </Badge>
      ) : null}

      {query.isLoading ? (
        <div className="space-y-3 rounded-md border p-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : query.isError ? (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-6 text-center text-sm text-destructive">
          Impossible de charger votre planning.
        </p>
      ) : planning?.status === 'draft' ? (
        <div className="rounded-lg border border-dashed bg-muted/40 px-6 py-16 text-center text-sm text-muted-foreground">
          Cette semaine n&apos;est pas encore publiée.
        </div>
      ) : planning ? (
        <div className="w-full overflow-x-auto rounded-md border">
          <div className="grid min-w-[720px] grid-cols-7 gap-0 divide-x">
            {weekDays.map((d) => {
              const list = shiftsByDay[d] ?? [];
              const dm = dayMeta[d];
              const totalHours = (dm?.totalMinutes ?? 0) / 60;
              const staffCount = dm?.uniqueStaff.size ?? 0;
              return (
                <div key={d} className="flex min-w-0 flex-col bg-background">
                  <div className="border-b bg-muted/40 px-1 py-2">
                    <WeekHeader
                      date={d}
                      label={dayLabel(d)}
                      isLocked={false}
                      totalHours={totalHours}
                      staffCount={staffCount}
                      onLockDay={noop}
                      isRH={false}
                    />
                  </div>
                  <div className="flex min-h-[200px] flex-col gap-1.5 p-1.5">
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

      <div className="flex flex-col gap-2 border-t pt-6 sm:flex-row sm:justify-center sm:gap-4">
        <Button type="button" variant="default" onClick={() => navigate('/employee/leaves/new')}>
          Demander un congé
        </Button>
        <Button type="button" variant="outline" onClick={() => navigate('/employee/absences/new')}>
          Signaler une absence
        </Button>
      </div>
    </div>
  );
}
