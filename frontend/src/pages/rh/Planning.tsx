import { pageTitleClassName } from '@/components/layout';
import { useCallback, useMemo, useState } from 'react';
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  addDays,
  addMonths,
  addWeeks,
  format,
  startOfMonth,
} from 'date-fns';
import { fr } from 'date-fns/locale';
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  Lock,
  Send,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { queryKeys } from '@/lib/queryKeys';
import {
  createOnCallShift,
  createReplacement,
  createShift,
  deleteShift,
  duplicateWeek,
  getEmployeesForPlanning,
  getMonthPlanning,
  getMyMonthPlanning,
  getOnCallSchedule,
  getReplacements,
  getShiftTypes,
  getWeekPlanning,
  lockDay,
  lockWeek,
  publishWeek,
  type DuplicationResult,
  type Shift,
  type ShiftCreatePayload,
  type ShiftUpdatePayload,
  type WeekDuplicatePayload,
  unlockDay,
  unlockWeek,
  updateShift,
} from '@/api/planning';
import { DuplicateWeekModal } from '@/components/planning/DuplicateWeekModal';
import { LockWeekModal } from '@/components/planning/LockWeekModal';
import { PayrollSyncStatus } from '@/components/planning/PayrollSyncStatus';
import { ShiftModal } from '@/components/planning/ShiftModal';
import { WeekGrid } from '@/components/planning/WeekGrid';
import { OnCallDialog } from '@/features/planning/components/OnCallDialog';
import { PlanningMonthView } from '@/features/planning/components/PlanningMonthView';
import { PlanningOnCallView } from '@/features/planning/components/PlanningOnCallView';
import { PlanningQueryError } from '@/features/planning/components/PlanningQueryError';
import { PlanningReplacementsView } from '@/features/planning/components/PlanningReplacementsView';
import { ReplacementDialog } from '@/features/planning/components/ReplacementDialog';
import {
  apiErrorMessage,
  buildMonthCalendarDays,
  chunk,
  coerceWeekPlanning,
  defaultWeekStartIso,
  formatWeekRangeLabel,
  groupShiftsByDay,
  isRhLike,
  parseISOSafe,
  shiftDurationMinutes,
  statusBadge,
  toHmsFromInput,
} from '@/features/planning/utils/planningUtils';

type ModalType = 'create' | 'edit' | 'lock' | 'duplicate' | null;

export default function Planning() {
  const { toast } = useToast();
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const queryClient = useQueryClient();

  const [weekStart, setWeekStart] = useState(defaultWeekStartIso);
  const [viewMode, setViewMode] = useState<
    'semaine' | 'mois' | 'astreintes' | 'remplacements'
  >('semaine');
  const [monthAnchor, setMonthAnchor] = useState(() => startOfMonth(new Date()));
  const [onCallDialogOpen, setOnCallDialogOpen] = useState(false);
  const [onCallEmployeeId, setOnCallEmployeeId] = useState('');
  const [onCallDate, setOnCallDate] = useState(() => format(new Date(), 'yyyy-MM-dd'));
  const [onCallStart, setOnCallStart] = useState('18:00');
  const [onCallEnd, setOnCallEnd] = useState('08:00');
  const [replacementDialogOpen, setReplacementDialogOpen] = useState(false);
  const [repOriginalId, setRepOriginalId] = useState('');
  const [repReplacingId, setRepReplacingId] = useState('');
  const [repDate, setRepDate] = useState(() => format(new Date(), 'yyyy-MM-dd'));
  const [repStart, setRepStart] = useState('09:00');
  const [repEnd, setRepEnd] = useState('17:00');
  const [repReason, setRepReason] = useState('');
  const [repShiftTypeId, setRepShiftTypeId] = useState('');
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
    queryKey: queryKeys.planningWeek(activeCompany?.company_id, weekStart),
    queryFn: () => getWeekPlanning(weekStart),
    select: (data) => coerceWeekPlanning(data),
    enabled:
      viewMode === 'semaine' &&
      Boolean(weekStart) &&
      Boolean(activeCompany?.company_id),
  });

  const monthYear = monthAnchor.getFullYear();
  const monthIndex1 = monthAnchor.getMonth() + 1;

  const monthShiftsQuery = useQuery({
    queryKey: [
      'planning-month',
      activeCompany?.company_id,
      monthYear,
      monthIndex1,
      isRH ? 'company' : 'me',
    ],
    queryFn: () =>
      isRH
        ? getMonthPlanning(String(activeCompany!.company_id), monthYear, monthIndex1)
        : getMyMonthPlanning(
            String(activeCompany!.company_id),
            monthYear,
            monthIndex1
          ),
    enabled: viewMode === 'mois' && Boolean(activeCompany?.company_id),
  });

  const onCallQuery = useQuery({
    queryKey: ['planning-on-call', activeCompany?.company_id, monthYear, monthIndex1],
    queryFn: () =>
      getOnCallSchedule(String(activeCompany!.company_id), monthYear, monthIndex1),
    enabled: viewMode === 'astreintes' && isRH && Boolean(activeCompany?.company_id),
  });

  const replacementsQuery = useQuery({
    queryKey: ['planning-replacements', activeCompany?.company_id, monthYear, monthIndex1],
    queryFn: () =>
      getReplacements(String(activeCompany!.company_id), monthYear, monthIndex1),
    enabled: viewMode === 'remplacements' && isRH && Boolean(activeCompany?.company_id),
  });

  const {
    data: employees,
    isSuccess: employeesPlanningSuccess,
    isError: employeesLoadError,
    error: employeesQueryError,
    refetch: refetchEmployees,
  } = useQuery({
    queryKey: queryKeys.employeesPlanning(activeCompany?.company_id),
    queryFn: () => getEmployeesForPlanning(),
    enabled: Boolean(activeCompany?.company_id),
  });

  const employeesLoadErrorMessage = apiErrorMessage(
    employeesQueryError,
    'Impossible de charger la liste des employés.',
  );

  const shiftTypesQuery = useQuery({
    queryKey: queryKeys.planningShiftTypes(activeCompany?.company_id),
    queryFn: getShiftTypes,
    enabled: isRH,
  });

  const invalidatePlanningCaches = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['planning-week', weekStart] });
    void queryClient.invalidateQueries({ queryKey: ['planning-month'] });
    void queryClient.invalidateQueries({ queryKey: ['planning-on-call'] });
    void queryClient.invalidateQueries({ queryKey: ['planning-replacements'] });
  }, [queryClient, weekStart]);

  const createMutation = useMutation({
    mutationFn: (payload: ShiftCreatePayload) => createShift(payload),
    onSuccess: (data) => {
      invalidatePlanningCaches();
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
      toast({ title: 'Erreur', description: apiErrorMessage(e), variant: 'destructive' });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ShiftUpdatePayload }) =>
      updateShift(id, payload),
    onSuccess: (data) => {
      invalidatePlanningCaches();
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
      toast({ title: 'Erreur', description: apiErrorMessage(e), variant: 'destructive' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteShift(id),
    onSuccess: () => {
      invalidatePlanningCaches();
      setModalType(null);
      setSelectedShift(null);
      setConflictWarnings([]);
      toast({ title: 'Shift supprimé' });
    },
    onError: (e) => {
      toast({ title: 'Erreur', description: apiErrorMessage(e), variant: 'destructive' });
    },
  });

  const lockWeekMutation = useMutation({
    mutationFn: (reason?: string) => lockWeek(weekStart, reason),
    onSuccess: () => {
      invalidatePlanningCaches();
      setModalType(null);
      setConflictWarnings([]);
      toast({ title: 'Semaine verrouillée' });
    },
    onError: (e) => {
      toast({ title: 'Erreur', description: apiErrorMessage(e), variant: 'destructive' });
    },
  });

  const unlockWeekMutation = useMutation({
    mutationFn: () => unlockWeek(weekStart),
    onSuccess: () => {
      invalidatePlanningCaches();
      toast({ title: 'Semaine déverrouillée' });
    },
    onError: (e) => {
      toast({ title: 'Erreur', description: apiErrorMessage(e), variant: 'destructive' });
    },
  });

  const publishMutation = useMutation({
    mutationFn: () => publishWeek(weekStart),
    onSuccess: () => {
      invalidatePlanningCaches();
      toast({ title: 'Semaine publiée' });
    },
    onError: (e) => {
      toast({ title: 'Erreur', description: apiErrorMessage(e), variant: 'destructive' });
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: (payload: WeekDuplicatePayload) => duplicateWeek(payload),
    onSuccess: (res) => {
      setDuplicationResult(res);
      invalidatePlanningCaches();
    },
    onError: (e) => {
      toast({ title: 'Erreur', description: apiErrorMessage(e), variant: 'destructive' });
    },
  });

  const lockDayMutation = useMutation({
    mutationFn: ({ day, unlock }: { day: string; unlock: boolean }) =>
      unlock ? unlockDay(day) : lockDay(day),
    onSuccess: (_d, v) => {
      invalidatePlanningCaches();
      setDayLocks((prev) => ({ ...prev, [v.day]: !v.unlock }));
      toast({ title: v.unlock ? 'Jour déverrouillé' : 'Jour verrouillé' });
    },
    onError: (e) => {
      toast({ title: 'Erreur', description: apiErrorMessage(e), variant: 'destructive' });
    },
  });

  const createOnCallMutation = useMutation({
    mutationFn: (payload: ShiftCreatePayload) =>
      createOnCallShift(String(activeCompany!.company_id), payload),
    onSuccess: () => {
      invalidatePlanningCaches();
      setOnCallDialogOpen(false);
      setOnCallEmployeeId('');
      toast({ title: 'Astreinte créée', description: 'Le calendrier a été mis à jour.' });
    },
    onError: (e) => {
      toast({ title: 'Erreur', description: apiErrorMessage(e), variant: 'destructive' });
    },
  });

  const createReplacementMutation = useMutation({
    mutationFn: (payload: ShiftCreatePayload) =>
      createReplacement(String(activeCompany!.company_id), payload),
    onSuccess: () => {
      invalidatePlanningCaches();
      setReplacementDialogOpen(false);
      setRepOriginalId('');
      setRepReplacingId('');
      toast({ title: 'Remplacement planifié', description: 'Le planning a été mis à jour.' });
    },
    onError: (e) => {
      toast({ title: 'Erreur', description: apiErrorMessage(e), variant: 'destructive' });
    },
  });

  const planning = weekQuery.data;
  const badge = useMemo(() => statusBadge(planning?.status ?? 'draft'), [planning?.status]);

  const weekRangeLabel = useMemo(() => {
    if (planning) return formatWeekRangeLabel(planning.week_start, planning.week_end);
    const mon = parseISOSafe(weekStart);
    const sun = format(addDays(mon, 6), 'yyyy-MM-dd');
    return formatWeekRangeLabel(weekStart, sun);
  }, [planning, weekStart]);

  const totalHoursForWeek = useMemo(() => {
    if (!planning?.shifts?.length) return 0;
    let minutes = 0;
    for (const s of planning.shifts) minutes += shiftDurationMinutes(s);
    return minutes / 60;
  }, [planning?.shifts]);

  const uniqueEmployeesCount = useMemo(() => {
    if (!planning?.shifts?.length) return 0;
    return new Set(planning.shifts.map((s) => s.employee_id)).size;
  }, [planning?.shifts]);

  const monthNavLabel = useMemo(
    () => format(monthAnchor, 'MMMM yyyy', { locale: fr }),
    [monthAnchor],
  );

  const monthCalendarDays = useMemo(() => buildMonthCalendarDays(monthAnchor), [monthAnchor]);
  const monthCalendarRows = useMemo(() => chunk(monthCalendarDays, 7), [monthCalendarDays]);
  const monthShiftsByDay = useMemo(
    () => groupShiftsByDay(monthShiftsQuery.data ?? []),
    [monthShiftsQuery.data],
  );
  const onCallByDay = useMemo(
    () => groupShiftsByDay(onCallQuery.data ?? []),
    [onCallQuery.data],
  );

  const openOnCallDialog = () => {
    setOnCallEmployeeId('');
    setOnCallDate(format(new Date(), 'yyyy-MM-dd'));
    setOnCallStart('18:00');
    setOnCallEnd('08:00');
    setOnCallDialogOpen(true);
  };

  const submitOnCall = () => {
    if (!activeCompany?.company_id) return;
    if (!onCallEmployeeId) {
      toast({ title: 'Salarié requis', description: 'Sélectionnez un employé.', variant: 'destructive' });
      return;
    }
    createOnCallMutation.mutate({
      employee_id: onCallEmployeeId,
      shift_date: onCallDate.slice(0, 10),
      start_time: toHmsFromInput(onCallStart),
      end_time: toHmsFromInput(onCallEnd),
      transverse_category: 'astreinte',
      shift_type_id: null,
    });
  };

  const openReplacementDialog = () => {
    setRepOriginalId('');
    setRepReplacingId('');
    setRepDate(format(new Date(), 'yyyy-MM-dd'));
    setRepStart('09:00');
    setRepEnd('17:00');
    setRepReason('');
    setRepShiftTypeId(shiftTypesQuery.data?.[0]?.id ?? '');
    setReplacementDialogOpen(true);
  };

  const submitReplacement = () => {
    if (!activeCompany?.company_id) return;
    if (!repOriginalId || !repReplacingId) {
      toast({
        title: 'Champs requis',
        description: 'Sélectionnez le salarié remplacé et le remplaçant.',
        variant: 'destructive',
      });
      return;
    }
    if (repOriginalId === repReplacingId) {
      toast({
        title: 'Incohérence',
        description: 'Le remplaçant doit être différent du salarié remplacé.',
        variant: 'destructive',
      });
      return;
    }
    if (!repShiftTypeId) {
      toast({ title: 'Type requis', description: 'Choisissez un type de shift.', variant: 'destructive' });
      return;
    }
    createReplacementMutation.mutate({
      employee_id: repReplacingId,
      shift_type_id: repShiftTypeId,
      transverse_category: null,
      shift_date: repDate.slice(0, 10),
      start_time: toHmsFromInput(repStart),
      end_time: toHmsFromInput(repEnd),
      is_replacement: true,
      original_employee_id: repOriginalId,
      replacing_employee_id: repReplacingId,
      replacement_reason: repReason.trim() || undefined,
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
    updateMutation.mutate({ id: selectedShift.id, payload: data as ShiftUpdatePayload });
  };

  const handleDeleteShift = () => {
    if (selectedShift) deleteMutation.mutate(selectedShift.id);
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
    toast({ title: 'Actualisation', description: 'État de transmission rechargé.' });
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
    <div className="container max-w-[1600px] space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className={pageTitleClassName}>Planning</h1>
          <p className="text-sm text-muted-foreground">
            {viewMode === 'semaine'
              ? 'Vue semaine — gestion des équipes'
              : viewMode === 'mois'
                ? isRH
                  ? 'Vue mois — tous les shifts de l’entreprise'
                  : 'Vue mois — vos shifts publiés'
                : viewMode === 'astreintes'
                  ? 'Calendrier des astreintes'
                  : 'Gestion des remplacements'}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 sm:flex-row sm:items-center sm:gap-3">
          {viewMode === 'semaine' ? <Badge className={badge.className}>{badge.label}</Badge> : null}
          {viewMode === 'semaine' && planning ? (
            <PayrollSyncStatus
              transmitted={planning.payroll_transmitted}
              transmittedAt={planning.payroll_transmitted_at}
              weekStatus={planning.status}
              onRetry={handlePayrollRetry}
            />
          ) : null}
        </div>
      </div>

      {employeesLoadError ? (
        <PlanningQueryError message={employeesLoadErrorMessage} onRetry={() => void refetchEmployees()} />
      ) : null}

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {viewMode === 'semaine' ? (
            <>
              <Button type="button" variant="outline" size="icon" onClick={() => setWeekStart(format(addWeeks(parseISOSafe(weekStart), -1), 'yyyy-MM-dd'))}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button type="button" variant="outline" size="icon" onClick={() => setWeekStart(format(addWeeks(parseISOSafe(weekStart), 1), 'yyyy-MM-dd'))}>
                <ChevronRight className="h-4 w-4" />
              </Button>
              <span className="min-w-0 truncate text-sm font-medium capitalize">{weekRangeLabel}</span>
            </>
          ) : (
            <>
              <Button type="button" variant="outline" size="icon" onClick={() => setMonthAnchor((prev) => addMonths(prev, -1))}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button type="button" variant="outline" size="icon" onClick={() => setMonthAnchor((prev) => addMonths(prev, 1))}>
                <ChevronRight className="h-4 w-4" />
              </Button>
              <span className="min-w-0 truncate text-sm font-medium capitalize">{monthNavLabel}</span>
            </>
          )}
        </div>

        <ToggleGroup
          type="single"
          value={viewMode}
          onValueChange={(v) => {
            if (!v) return;
            setViewMode(v as 'semaine' | 'mois' | 'astreintes' | 'remplacements');
          }}
          className="justify-start"
        >
          <ToggleGroupItem value="semaine">Semaine</ToggleGroupItem>
          <ToggleGroupItem value="mois">Mois</ToggleGroupItem>
          <ToggleGroupItem value="astreintes">Astreintes</ToggleGroupItem>
          <ToggleGroupItem value="remplacements">Remplacements</ToggleGroupItem>
        </ToggleGroup>

        {isRH && viewMode === 'semaine' ? (
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" size="sm" onClick={openDuplicateModal}>
              <Copy className="mr-1 h-4 w-4" />
              Dupliquer
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={() => publishMutation.mutate()} disabled={publishMutation.isPending}>
              <Send className="mr-1 h-4 w-4" />
              Publier
            </Button>
            <Button type="button" variant="default" size="sm" onClick={() => setModalType('lock')} disabled={lockWeekMutation.isPending}>
              <Lock className="mr-1 h-4 w-4" />
              Verrouiller
            </Button>
            {planning?.status === 'locked' ? (
              <Button type="button" variant="secondary" size="sm" onClick={() => unlockWeekMutation.mutate()} disabled={unlockWeekMutation.isPending}>
                Déverrouiller
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>

      {viewMode === 'semaine' && weekQuery.isLoading ? (
        <div className="space-y-2 rounded-md border p-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : viewMode === 'semaine' && weekQuery.isError ? (
        <PlanningQueryError
          message={apiErrorMessage(weekQuery.error, 'Impossible de charger le planning de la semaine.')}
          onRetry={() => void weekQuery.refetch()}
        />
      ) : viewMode === 'semaine' && planning ? (
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

      {viewMode === 'mois' ? (
        <PlanningMonthView
          monthAnchor={monthAnchor}
          monthCalendarRows={monthCalendarRows}
          monthShiftsByDay={monthShiftsByDay}
          isLoading={monthShiftsQuery.isLoading}
          isError={monthShiftsQuery.isError}
          error={monthShiftsQuery.error}
          onEditShift={openEdit}
        />
      ) : null}

      {viewMode === 'astreintes' ? (
        <PlanningOnCallView
          isRH={isRH}
          monthAnchor={monthAnchor}
          monthCalendarRows={monthCalendarRows}
          onCallByDay={onCallByDay}
          isLoading={onCallQuery.isLoading}
          isError={onCallQuery.isError}
          error={onCallQuery.error}
          onAdd={openOnCallDialog}
          onEditShift={openEdit}
        />
      ) : null}

      {viewMode === 'remplacements' ? (
        <PlanningReplacementsView
          isRH={isRH}
          isLoading={replacementsQuery.isLoading}
          isError={replacementsQuery.isError}
          error={replacementsQuery.error}
          replacements={replacementsQuery.data ?? []}
          deletePending={deleteMutation.isPending}
          onAdd={openReplacementDialog}
          onDelete={(id) => deleteMutation.mutate(id)}
        />
      ) : null}

      <OnCallDialog
        open={onCallDialogOpen}
        onOpenChange={setOnCallDialogOpen}
        employees={employees ?? []}
        employeeId={onCallEmployeeId}
        onEmployeeIdChange={setOnCallEmployeeId}
        date={onCallDate}
        onDateChange={setOnCallDate}
        start={onCallStart}
        onStartChange={setOnCallStart}
        end={onCallEnd}
        onEndChange={setOnCallEnd}
        onSubmit={submitOnCall}
        isPending={createOnCallMutation.isPending}
      />

      <ReplacementDialog
        open={replacementDialogOpen}
        onOpenChange={setReplacementDialogOpen}
        employees={employees ?? []}
        shiftTypes={shiftTypesQuery.data ?? []}
        originalId={repOriginalId}
        onOriginalIdChange={setRepOriginalId}
        replacingId={repReplacingId}
        onReplacingIdChange={setRepReplacingId}
        date={repDate}
        onDateChange={setRepDate}
        start={repStart}
        onStartChange={setRepStart}
        end={repEnd}
        onEndChange={setRepEnd}
        reason={repReason}
        onReasonChange={setRepReason}
        shiftTypeId={repShiftTypeId}
        onShiftTypeIdChange={setRepShiftTypeId}
        onSubmit={submitReplacement}
        isPending={createReplacementMutation.isPending}
      />

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
        isLoading={createMutation.isPending || updateMutation.isPending || deleteMutation.isPending}
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
