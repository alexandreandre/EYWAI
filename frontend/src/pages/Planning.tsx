import { useCallback, useMemo, useState } from 'react';
import axios from 'axios';
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { addDays, addWeeks, format, startOfWeek } from 'date-fns';
import { fr } from 'date-fns/locale';
import { ChevronLeft, ChevronRight, Copy, Lock, Send } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import {
  createShift,
  deleteShift,
  duplicateWeek,
  getShiftTypes,
  getEmployeesForPlanning,
  getWeekPlanning,
  lockDay,
  lockWeek,
  publishWeek,
  type DuplicationResult,
  type Shift,
  type ShiftCreatePayload,
  type ShiftUpdatePayload,
  type WeekDuplicatePayload,
  type WeekPlanning,
  unlockDay,
  unlockWeek,
  updateShift,
} from '@/api/planning';
import { DuplicateWeekModal } from '@/components/planning/DuplicateWeekModal';
import { LockWeekModal } from '@/components/planning/LockWeekModal';
import { PayrollSyncStatus } from '@/components/planning/PayrollSyncStatus';
import { ShiftModal } from '@/components/planning/ShiftModal';
import { WeekGrid } from '@/components/planning/WeekGrid';

type ModalType = 'create' | 'edit' | 'lock' | 'duplicate' | null;

function apiErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as { detail?: unknown } | undefined;
    const d = data?.detail;
    if (typeof d === 'string') {
      return d;
    }
  }
  return err instanceof Error ? err.message : 'Erreur inattendue';
}

function coerceWeekPlanning(raw: unknown): WeekPlanning {
  const r = raw as Record<string, unknown>;
  const ws =
    typeof r.week_start === 'string'
      ? r.week_start.slice(0, 10)
      : String(r.week_start ?? '').slice(0, 10);
  const we =
    typeof r.week_end === 'string'
      ? r.week_end.slice(0, 10)
      : String(r.week_end ?? '').slice(0, 10);
  const rawHours = (r.employee_hours as Array<{
    employee_id: string;
    total_minutes: number;
  }> | null) ?? [];
  const contractMinutes = Math.round(35 * 60);
  const employee_hours = rawHours.map((h) => ({
    employee_id: h.employee_id,
    total_minutes: h.total_minutes,
    contract_minutes: contractMinutes,
    delta: h.total_minutes - contractMinutes,
  }));
  const pta = r.payroll_transmitted_at;
  return {
    week_start: ws,
    week_end: we,
    status: String(r.status ?? 'draft'),
    payroll_transmitted: Boolean(r.payroll_transmitted),
    payroll_transmitted_at:
      typeof pta === 'string' && pta.length > 0 ? pta : undefined,
    team_view_enabled: Boolean(r.team_view_enabled),
    shifts: (r.shifts as Shift[]) ?? [],
    employee_hours,
  };
}

function defaultWeekStartIso(): string {
  return format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd');
}

function formatWeekRangeLabel(weekStart: string, weekEnd: string): string {
  try {
    const a = format(parseISOSafe(weekStart), 'd MMMM yyyy', { locale: fr });
    const b = format(parseISOSafe(weekEnd), 'd MMMM yyyy', { locale: fr });
    return `Semaine du ${a} au ${b}`;
  } catch {
    return `Semaine du ${weekStart} au ${weekEnd}`;
  }
}

function parseISOSafe(s: string): Date {
  return new Date(`${s.slice(0, 10)}T12:00:00`);
}

function isRhLike(role: string | undefined): boolean {
  return (
    role === 'admin' ||
    role === 'rh' ||
    role === 'collaborateur_rh' ||
    role === 'super_admin'
  );
}

function statusBadge(status: string): { label: string; className: string } {
  switch (status) {
    case 'partially_published':
      return {
        label: 'Partiellement publié',
        className: 'bg-orange-100 text-orange-900 hover:bg-orange-100',
      };
    case 'published':
      return {
        label: 'Publié',
        className: 'bg-green-100 text-green-900 hover:bg-green-100',
      };
    case 'locked':
      return {
        label: 'Verrouillé',
        className: 'bg-red-100 text-red-900 hover:bg-red-100',
      };
    default:
      return {
        label: 'Brouillon',
        className: 'bg-slate-100 text-slate-800 hover:bg-slate-100',
      };
  }
}

function shiftDurationMinutes(s: Shift): number {
  const toSec = (t: string) => {
    const parts = t.split(':').map((x) => Number(x));
    return (parts[0] || 0) * 3600 + (parts[1] || 0) * 60 + (parts[2] || 0);
  };
  const a = toSec(s.start_time);
  let b = toSec(s.end_time);
  if (b <= a) {
    b += 24 * 3600;
  }
  return Math.round((b - a) / 60);
}

export default function Planning() {
  const { toast } = useToast();
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const queryClient = useQueryClient();

  const [weekStart, setWeekStart] = useState(defaultWeekStartIso);
  const [viewMode, setViewMode] = useState<'jour' | 'semaine' | 'mois'>('semaine');
  const [modalType, setModalType] = useState<ModalType>(null);
  const [selectedCell, setSelectedCell] = useState<{
    employee_id: string;
    shift_date: string;
  } | null>(null);
  const [selectedShift, setSelectedShift] = useState<Shift | null>(null);
  const [dayLocks, setDayLocks] = useState<Record<string, boolean>>({});
  const [conflictWarnings, setConflictWarnings] = useState<string[]>([]);
  const [duplicationResult, setDuplicationResult] = useState<
    DuplicationResult | undefined
  >();

  const role = user?.role ?? activeCompany?.role;
  const isRH = isRhLike(role);

  const weekQuery = useQuery({
    queryKey: ['planning-week', weekStart, activeCompany?.company_id],
    queryFn: () => getWeekPlanning(weekStart),
    select: (data) => coerceWeekPlanning(data),
    enabled: Boolean(weekStart),
  });

  const { data: employees, isSuccess: employeesPlanningSuccess } = useQuery({
    queryKey: ['employees-planning', activeCompany?.company_id],
    queryFn: () => getEmployeesForPlanning(),
    enabled: Boolean(activeCompany?.company_id),
  });

  const shiftTypesQuery = useQuery({
    queryKey: ['planning-shift-types', activeCompany?.company_id],
    queryFn: getShiftTypes,
    enabled: isRH,
  });

  const invalidateWeek = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['planning-week', weekStart] });
  }, [queryClient, weekStart]);

  const createMutation = useMutation({
    mutationFn: (payload: ShiftCreatePayload) => createShift(payload),
    onSuccess: (data) => {
      invalidateWeek();
      const warnings = data.conflict_warnings?.map((w) => w.message) ?? [];
      setConflictWarnings(warnings);
      if (warnings.length === 0) {
        setModalType(null);
        setSelectedCell(null);
        setSelectedShift(null);
        toast({ title: 'Shift créé', description: 'Le planning a été mis à jour.' });
      } else {
        toast({
          title: 'Shift créé avec avertissements',
          description: 'Vérifiez les alertes dans la fenêtre.',
        });
      }
    },
    onError: (e) => {
      toast({
        title: 'Erreur',
        description: apiErrorMessage(e),
        variant: 'destructive',
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: ShiftUpdatePayload;
    }) => updateShift(id, payload),
    onSuccess: (data) => {
      invalidateWeek();
      const warnings = data.conflict_warnings?.map((w) => w.message) ?? [];
      setConflictWarnings(warnings);
      if (warnings.length === 0) {
        setModalType(null);
        setSelectedShift(null);
        toast({ title: 'Shift mis à jour' });
      } else {
        toast({
          title: 'Shift mis à jour avec avertissements',
          description: 'Vérifiez les alertes dans la fenêtre.',
        });
      }
    },
    onError: (e) => {
      toast({
        title: 'Erreur',
        description: apiErrorMessage(e),
        variant: 'destructive',
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteShift(id),
    onSuccess: () => {
      invalidateWeek();
      setModalType(null);
      setSelectedShift(null);
      setConflictWarnings([]);
      toast({ title: 'Shift supprimé' });
    },
    onError: (e) => {
      toast({
        title: 'Erreur',
        description: apiErrorMessage(e),
        variant: 'destructive',
      });
    },
  });

  const lockWeekMutation = useMutation({
    mutationFn: (reason?: string) => lockWeek(weekStart, reason),
    onSuccess: () => {
      invalidateWeek();
      setModalType(null);
      setConflictWarnings([]);
      toast({ title: 'Semaine verrouillée' });
    },
    onError: (e) => {
      toast({
        title: 'Erreur',
        description: apiErrorMessage(e),
        variant: 'destructive',
      });
    },
  });

  const unlockWeekMutation = useMutation({
    mutationFn: () => unlockWeek(weekStart),
    onSuccess: () => {
      invalidateWeek();
      toast({ title: 'Semaine déverrouillée' });
    },
    onError: (e) => {
      toast({
        title: 'Erreur',
        description: apiErrorMessage(e),
        variant: 'destructive',
      });
    },
  });

  const publishMutation = useMutation({
    mutationFn: () => publishWeek(weekStart),
    onSuccess: () => {
      invalidateWeek();
      toast({ title: 'Semaine publiée' });
    },
    onError: (e) => {
      toast({
        title: 'Erreur',
        description: apiErrorMessage(e),
        variant: 'destructive',
      });
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: (payload: WeekDuplicatePayload) => duplicateWeek(payload),
    onSuccess: (res) => {
      setDuplicationResult(res);
      invalidateWeek();
    },
    onError: (e) => {
      toast({
        title: 'Erreur',
        description: apiErrorMessage(e),
        variant: 'destructive',
      });
    },
  });

  const lockDayMutation = useMutation({
    mutationFn: ({ day, unlock }: { day: string; unlock: boolean }) =>
      unlock ? unlockDay(day) : lockDay(day),
    onSuccess: (_d, v) => {
      invalidateWeek();
      setDayLocks((prev) => ({ ...prev, [v.day]: !v.unlock }));
      toast({
        title: v.unlock ? 'Jour déverrouillé' : 'Jour verrouillé',
      });
    },
    onError: (e) => {
      toast({
        title: 'Erreur',
        description: apiErrorMessage(e),
        variant: 'destructive',
      });
    },
  });

  const planning = weekQuery.data;
  const badge = useMemo(
    () => statusBadge(planning?.status ?? 'draft'),
    [planning?.status]
  );

  const weekRangeLabel = useMemo(() => {
    if (planning) {
      return formatWeekRangeLabel(planning.week_start, planning.week_end);
    }
    const mon = parseISOSafe(weekStart);
    const sun = format(addDays(mon, 6), 'yyyy-MM-dd');
    return formatWeekRangeLabel(weekStart, sun);
  }, [planning, weekStart]);

  const totalHoursForWeek = useMemo(() => {
    if (!planning?.shifts?.length) return 0;
    let minutes = 0;
    for (const s of planning.shifts) {
      minutes += shiftDurationMinutes(s);
    }
    return minutes / 60;
  }, [planning?.shifts]);

  const uniqueEmployeesCount = useMemo(() => {
    if (!planning?.shifts?.length) return 0;
    return new Set(planning.shifts.map((s) => s.employee_id)).size;
  }, [planning?.shifts]);

  const goPrevWeek = () => {
    const d = parseISOSafe(weekStart);
    setWeekStart(format(addWeeks(d, -1), 'yyyy-MM-dd'));
  };

  const goNextWeek = () => {
    const d = parseISOSafe(weekStart);
    setWeekStart(format(addWeeks(d, 1), 'yyyy-MM-dd'));
  };

  const onViewModeChange = (v: string) => {
    if (v === 'semaine') {
      setViewMode('semaine');
      return;
    }
    toast({
      title: 'Bientôt disponible',
      description: 'Disponible prochainement',
    });
  };

  const handleCloseShiftModal = () => {
    if (createMutation.isPending || updateMutation.isPending) return;
    setModalType(null);
    setSelectedCell(null);
    setSelectedShift(null);
    setConflictWarnings([]);
  };

  const handleCreateShift = (data: ShiftCreatePayload | ShiftUpdatePayload) => {
    createMutation.mutate(data as ShiftCreatePayload);
  };

  const handleUpdateShift = (data: ShiftCreatePayload | ShiftUpdatePayload) => {
    if (!selectedShift) return;
    updateMutation.mutate({
      id: selectedShift.id,
      payload: data as ShiftUpdatePayload,
    });
  };

  const handleDeleteShift = () => {
    if (selectedShift) {
      deleteMutation.mutate(selectedShift.id);
    }
  };

  const handleDuplicateWeek = (payload: WeekDuplicatePayload) => {
    duplicateMutation.mutate(payload);
  };

  const handleLockWeek = (reason?: string) => {
    lockWeekMutation.mutate(reason);
  };

  const openCreate = (employee_id: string, shift_date: string) => {
    setSelectedShift(null);
    setConflictWarnings([]);
    setSelectedCell({ employee_id, shift_date });
    setModalType('create');
  };

  const openEdit = (shift: Shift) => {
    setSelectedCell(null);
    setConflictWarnings([]);
    setSelectedShift(shift);
    setModalType('edit');
  };

  const handleLockDay = (day: string) => {
    const locked = Boolean(dayLocks[day]);
    lockDayMutation.mutate({ day, unlock: locked });
  };

  const handlePayrollRetry = () => {
    void weekQuery.refetch();
    toast({
      title: 'Actualisation',
      description: 'État de transmission rechargé.',
    });
  };

  const openDuplicateModal = () => {
    setDuplicationResult(undefined);
    setModalType('duplicate');
  };

  const handleCloseDuplicateModal = () => {
    setModalType(null);
    setDuplicationResult(undefined);
  };

  const handleCloseLockModal = () => {
    if (lockWeekMutation.isPending) return;
    setModalType(null);
  };

  return (
    <div className="container max-w-[1600px] space-y-4 py-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Planning</h1>
          <p className="text-sm text-muted-foreground">
            Vue semaine — gestion des équipes
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 sm:flex-row sm:items-center sm:gap-3">
          <Badge className={badge.className}>{badge.label}</Badge>
          {planning ? (
            <PayrollSyncStatus
              transmitted={planning.payroll_transmitted}
              transmittedAt={planning.payroll_transmitted_at}
              weekStatus={planning.status}
              onRetry={handlePayrollRetry}
            />
          ) : null}
        </div>
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" size="icon" onClick={goPrevWeek}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button type="button" variant="outline" size="icon" onClick={goNextWeek}>
            <ChevronRight className="h-4 w-4" />
          </Button>
          <span className="min-w-[200px] text-sm font-medium">{weekRangeLabel}</span>
        </div>

        <ToggleGroup
          type="single"
          value={viewMode}
          onValueChange={(v) => {
            if (!v) return;
            onViewModeChange(v);
          }}
          className="justify-start"
        >
          <ToggleGroupItem value="jour">Jour</ToggleGroupItem>
          <ToggleGroupItem value="semaine">Semaine</ToggleGroupItem>
          <ToggleGroupItem value="mois">Mois</ToggleGroupItem>
        </ToggleGroup>

        {isRH ? (
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={openDuplicateModal}
            >
              <Copy className="mr-1 h-4 w-4" />
              Dupliquer
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => publishMutation.mutate()}
              disabled={publishMutation.isPending}
            >
              <Send className="mr-1 h-4 w-4" />
              Publier
            </Button>
            <Button
              type="button"
              variant="default"
              size="sm"
              onClick={() => setModalType('lock')}
              disabled={lockWeekMutation.isPending}
            >
              <Lock className="mr-1 h-4 w-4" />
              Verrouiller
            </Button>
            {planning?.status === 'locked' ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => unlockWeekMutation.mutate()}
                disabled={unlockWeekMutation.isPending}
              >
                Déverrouiller
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>

      {weekQuery.isLoading ? (
        <div className="space-y-2 rounded-md border p-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : weekQuery.isError ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          {apiErrorMessage(weekQuery.error)}
        </div>
      ) : planning ? (
        <WeekGrid
          planning={planning}
          employees={employeesPlanningSuccess ? employees : undefined}
          onCellClick={openCreate}
          onShiftClick={openEdit}
          onLockDay={handleLockDay}
          isRH={isRH}
          dayLocks={dayLocks}
        />
      ) : null}

      <ShiftModal
        mode={selectedShift ? 'edit' : 'create'}
        open={modalType === 'create' || modalType === 'edit'}
        onClose={handleCloseShiftModal}
        onSubmit={selectedShift ? handleUpdateShift : handleCreateShift}
        onDelete={selectedShift ? handleDeleteShift : undefined}
        shiftTypes={shiftTypesQuery.data ?? []}
        prefillEmployeeId={selectedCell?.employee_id}
        prefillDate={selectedCell?.shift_date}
        initialData={selectedShift ?? undefined}
        employees={employees ?? []}
        isLoading={
          createMutation.isPending ||
          updateMutation.isPending ||
          deleteMutation.isPending
        }
        conflictWarnings={conflictWarnings}
      />

      <DuplicateWeekModal
        open={modalType === 'duplicate'}
        onClose={handleCloseDuplicateModal}
        onSubmit={handleDuplicateWeek}
        sourceWeekStart={weekStart}
        isLoading={duplicateMutation.isPending}
        result={duplicationResult}
      />

      <LockWeekModal
        open={modalType === 'lock'}
        onClose={handleCloseLockModal}
        onConfirm={handleLockWeek}
        weekStart={weekStart}
        shiftsCount={planning?.shifts.length ?? 0}
        totalHours={totalHoursForWeek}
        employeesCount={uniqueEmployeesCount}
        isLoading={lockWeekMutation.isPending}
      />
    </div>
  );
}
