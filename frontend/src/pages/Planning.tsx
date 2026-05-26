import { useCallback, useMemo, useState } from 'react';
import axios from 'axios';
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  addDays,
  addMonths,
  addWeeks,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameMonth,
  startOfMonth,
  startOfWeek,
} from 'date-fns';
import { fr } from 'date-fns/locale';
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  Lock,
  Plus,
  RefreshCw,
  Send,
  Trash2,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
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

function apiErrorMessage(err: unknown, fallback = 'Erreur inattendue'): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as { detail?: unknown } | undefined;
    const d = data?.detail;
    if (typeof d === 'string' && d.trim()) {
      return d;
    }
    if (err.response?.status === 503) {
      return 'Service temporairement indisponible. Réessayez dans quelques secondes.';
    }
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return fallback;
}

function PlanningQueryError({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry: () => void;
  className?: string;
}) {
  return (
    <div
      className={`rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-center ${className ?? ''}`}
    >
      <p className="text-sm text-destructive">{message}</p>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="mt-3 gap-2"
        onClick={onRetry}
      >
        <RefreshCw className="h-4 w-4" />
        Réessayer
      </Button>
    </div>
  );
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

/** Aligné sur ShiftBlock pour les pastilles mois / astreintes */
const TRANSVERSE_BADGE_COLORS: Record<string, string> = {
  CP: '#4CAF50',
  RTT: '#8BC34A',
  MAL: '#FF5722',
  ABS_INJ: '#F44336',
  FORM: '#2196F3',
  REP_HEB: '#9E9E9E',
  astreinte: '#5C6BC0',
  on_call: '#3949AB',
};

function normShiftDay(iso: string): string {
  return iso.slice(0, 10);
}

function groupShiftsByDay(shifts: Shift[]): Record<string, Shift[]> {
  const map: Record<string, Shift[]> = {};
  for (const s of shifts) {
    const d = normShiftDay(s.shift_date);
    if (!map[d]) map[d] = [];
    map[d].push(s);
  }
  for (const k of Object.keys(map)) {
    map[k].sort((a, b) => a.start_time.localeCompare(b.start_time));
  }
  return map;
}

function shiftBadgeBackground(s: Shift): string {
  if (s.shift_type?.color) return s.shift_type.color;
  const cat = s.transverse_category;
  if (cat && TRANSVERSE_BADGE_COLORS[cat]) return TRANSVERSE_BADGE_COLORS[cat];
  return '#607D8B';
}

function employeeShort(s: Shift): string {
  const ln = (s.employee_last_name ?? '').trim();
  const fn = (s.employee_first_name ?? '').trim();
  if (ln || fn) return `${ln.toUpperCase()} ${fn}`.trim();
  return 'Salarié';
}

function shiftTypeShortLabel(s: Shift): string {
  if (s.shift_type?.label) return s.shift_type.label;
  if (s.transverse_category === 'astreinte' || s.transverse_category === 'on_call') {
    return 'Astreinte';
  }
  return s.transverse_category ?? 'Shift';
}

function replacerDisplayName(s: Shift): string {
  if (s.replacing_employee_name) return s.replacing_employee_name;
  return employeeShort(s);
}

function formatDateFrCell(iso: string): string {
  try {
    return format(parseISOSafe(iso), 'EEE d MMM yyyy', { locale: fr });
  } catch {
    return iso.slice(0, 10);
  }
}

function formatHourRange(s: Shift): string {
  return `${s.start_time.slice(0, 5)} → ${s.end_time.slice(0, 5)}`;
}

function buildMonthCalendarDays(anchor: Date): Date[] {
  const start = startOfMonth(anchor);
  const end = endOfMonth(anchor);
  const gridStart = startOfWeek(start, { weekStartsOn: 1 });
  const gridEnd = endOfWeek(end, { weekStartsOn: 1 });
  return eachDayOfInterval({ start: gridStart, end: gridEnd });
}

function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) {
    out.push(arr.slice(i, i + size));
  }
  return out;
}

function toHmsFromInput(hm: string): string {
  const t = hm.trim();
  return t.length <= 5 ? `${t}:00` : t.slice(0, 8);
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
    queryKey: ['planning-week', weekStart, activeCompany?.company_id],
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
    enabled:
      viewMode === 'mois' && Boolean(activeCompany?.company_id),
  });

  const onCallQuery = useQuery({
    queryKey: [
      'planning-on-call',
      activeCompany?.company_id,
      monthYear,
      monthIndex1,
    ],
    queryFn: () =>
      getOnCallSchedule(String(activeCompany!.company_id), monthYear, monthIndex1),
    enabled:
      viewMode === 'astreintes' &&
      isRH &&
      Boolean(activeCompany?.company_id),
  });

  const replacementsQuery = useQuery({
    queryKey: [
      'planning-replacements',
      activeCompany?.company_id,
      monthYear,
      monthIndex1,
    ],
    queryFn: () =>
      getReplacements(String(activeCompany!.company_id), monthYear, monthIndex1),
    enabled:
      viewMode === 'remplacements' &&
      isRH &&
      Boolean(activeCompany?.company_id),
  });

  const {
    data: employees,
    isSuccess: employeesPlanningSuccess,
    isError: employeesLoadError,
    error: employeesQueryError,
    refetch: refetchEmployees,
  } = useQuery({
    queryKey: ['employees-planning', activeCompany?.company_id],
    queryFn: () => getEmployeesForPlanning(),
    enabled: Boolean(activeCompany?.company_id),
  });

  const employeesLoadErrorMessage = apiErrorMessage(
    employeesQueryError,
    'Impossible de charger la liste des employés.'
  );

  const shiftTypesQuery = useQuery({
    queryKey: ['planning-shift-types', activeCompany?.company_id],
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
      invalidatePlanningCaches();
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
      invalidatePlanningCaches();
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
      invalidatePlanningCaches();
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
      invalidatePlanningCaches();
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
      invalidatePlanningCaches();
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
      invalidatePlanningCaches();
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
      toast({
        title: 'Erreur',
        description: apiErrorMessage(e),
        variant: 'destructive',
      });
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

  const goPrevMonth = () => {
    setMonthAnchor((prev) => addMonths(prev, -1));
  };

  const goNextMonth = () => {
    setMonthAnchor((prev) => addMonths(prev, 1));
  };

  const monthNavLabel = useMemo(
    () => format(monthAnchor, 'MMMM yyyy', { locale: fr }),
    [monthAnchor]
  );

  const monthCalendarDays = useMemo(
    () => buildMonthCalendarDays(monthAnchor),
    [monthAnchor]
  );

  const monthCalendarRows = useMemo(
    () => chunk(monthCalendarDays, 7),
    [monthCalendarDays]
  );

  const monthShiftsByDay = useMemo(
    () => groupShiftsByDay(monthShiftsQuery.data ?? []),
    [monthShiftsQuery.data]
  );

  const onCallByDay = useMemo(
    () => groupShiftsByDay(onCallQuery.data ?? []),
    [onCallQuery.data]
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
      toast({
        title: 'Salarié requis',
        description: 'Sélectionnez un employé.',
        variant: 'destructive',
      });
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
    const firstId = shiftTypesQuery.data?.[0]?.id ?? '';
    setRepShiftTypeId(firstId);
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
      toast({
        title: 'Type requis',
        description: 'Choisissez un type de shift.',
        variant: 'destructive',
      });
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
          {viewMode === 'semaine' ? (
            <Badge className={badge.className}>{badge.label}</Badge>
          ) : null}
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
        <PlanningQueryError
          message={employeesLoadErrorMessage}
          onRetry={() => void refetchEmployees()}
        />
      ) : null}

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {viewMode === 'semaine' ? (
            <>
              <Button type="button" variant="outline" size="icon" onClick={goPrevWeek}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button type="button" variant="outline" size="icon" onClick={goNextWeek}>
                <ChevronRight className="h-4 w-4" />
              </Button>
              <span className="min-w-0 truncate text-sm font-medium capitalize">
                {weekRangeLabel}
              </span>
            </>
          ) : (
            <>
              <Button type="button" variant="outline" size="icon" onClick={goPrevMonth}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button type="button" variant="outline" size="icon" onClick={goNextMonth}>
                <ChevronRight className="h-4 w-4" />
              </Button>
              <span className="min-w-0 truncate text-sm font-medium capitalize">
                {monthNavLabel}
              </span>
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

      {viewMode === 'semaine' && weekQuery.isLoading ? (
        <div className="space-y-2 rounded-md border p-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : viewMode === 'semaine' && weekQuery.isError ? (
        <PlanningQueryError
          message={apiErrorMessage(
            weekQuery.error,
            'Impossible de charger le planning de la semaine.'
          )}
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
        <div className="space-y-3">
          {monthShiftsQuery.isLoading ? (
            <div className="space-y-2 rounded-md border p-4">
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-72 w-full" />
            </div>
          ) : monthShiftsQuery.isError ? (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
              {apiErrorMessage(monthShiftsQuery.error)}
            </div>
          ) : (
            <div className="w-full overflow-x-auto rounded-md border">
              <div className="w-full min-w-[720px] text-sm">
                <div className="grid grid-cols-7 border-b bg-muted/40">
                  {['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'].map((d, i) => (
                    <div
                      key={d}
                      className={`min-w-0 overflow-hidden px-2 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground ${
                        i < 6 ? 'border-r border-border' : ''
                      }`}
                    >
                      {d}
                    </div>
                  ))}
                </div>
                {monthCalendarRows.map((row, ri) => (
                  <div
                    key={ri}
                    className="grid grid-cols-7 border-b border-border last:border-b-0"
                  >
                    {row.map((cell, ci) => {
                      const iso = format(cell, 'yyyy-MM-dd');
                      const inMonth = isSameMonth(cell, monthAnchor);
                      const dayShifts = monthShiftsByDay[iso] ?? [];
                      const visible = dayShifts.slice(0, 3);
                      const more = dayShifts.length - visible.length;
                      return (
                        <div
                          key={iso}
                          className={`min-h-28 min-w-0 overflow-hidden px-1.5 py-2 align-top ${
                            ci < 6 ? 'border-r border-border' : ''
                          }`}
                        >
                          <div
                            className={`mb-1 text-xs font-semibold ${
                              inMonth ? 'text-foreground' : 'text-muted-foreground/60'
                            }`}
                          >
                            {format(cell, 'd')}
                          </div>
                          <div className="flex min-h-24 w-full min-w-0 flex-col gap-1 overflow-hidden">
                            {visible.map((s) => (
                              <button
                                key={s.id}
                                type="button"
                                className={`flex w-full min-w-0 max-w-full flex-col gap-0.5 rounded px-1.5 py-0.5 text-left text-xs font-medium text-white ring-1 ring-black/10 transition hover:opacity-95 ${
                                  s.is_locked ? 'cursor-not-allowed opacity-80' : ''
                                }`}
                                style={{ backgroundColor: shiftBadgeBackground(s) }}
                                disabled={s.is_locked}
                                onClick={() => {
                                  if (!s.is_locked) openEdit(s);
                                }}
                                title={`${employeeShort(s)} — ${shiftTypeShortLabel(s)}`}
                              >
                                {s.is_replacement ? (
                                  <span className="inline-flex max-w-full shrink-0 self-start truncate rounded bg-orange-500 px-1 py-px text-[9px] font-bold uppercase leading-none text-white">
                                    Rempl.
                                  </span>
                                ) : null}
                                <span className="block w-full min-w-0 truncate">
                                  {employeeShort(s)} · {shiftTypeShortLabel(s)}
                                </span>
                                {s.is_replacement && s.original_employee_name ? (
                                  <span className="block w-full min-w-0 truncate text-[10px] font-normal opacity-95">
                                    Remplace {s.original_employee_name}
                                  </span>
                                ) : null}
                              </button>
                            ))}
                            {more > 0 ? (
                              <span className="w-full min-w-0 truncate text-xs text-muted-foreground">
                                +{more} autre{more > 1 ? 's' : ''}
                              </span>
                            ) : null}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}

      {viewMode === 'astreintes' ? (
        <div className="space-y-4">
          {!isRH ? (
            <div className="rounded-md border bg-muted/30 p-6 text-sm text-muted-foreground">
              La vue astreintes est réservée aux accès RH.
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <h2 className="text-lg font-semibold tracking-tight">
                  Calendrier des astreintes
                </h2>
                <Button type="button" size="sm" onClick={openOnCallDialog}>
                  <Plus className="mr-1 h-4 w-4" />
                  Ajouter une astreinte
                </Button>
              </div>
              {onCallQuery.isLoading ? (
                <div className="space-y-2 rounded-md border p-4">
                  <Skeleton className="h-8 w-48" />
                  <Skeleton className="h-64 w-full" />
                </div>
              ) : onCallQuery.isError ? (
                <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
                  {apiErrorMessage(onCallQuery.error)}
                </div>
              ) : (onCallQuery.data?.length ?? 0) === 0 ? (
                <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
                  Aucune astreinte sur ce mois.
                </div>
              ) : (
                <div className="w-full overflow-x-auto rounded-md border">
                  <table className="w-full min-w-[720px] border-collapse text-sm">
                    <thead>
                      <tr className="border-b bg-muted/40">
                        {['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'].map((d) => (
                          <th
                            key={d}
                            className="border-r px-2 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground last:border-r-0"
                          >
                            {d}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {monthCalendarRows.map((row, ri) => (
                        <tr key={ri} className="border-b last:border-b-0">
                          {row.map((cell) => {
                            const iso = format(cell, 'yyyy-MM-dd');
                            const inMonth = isSameMonth(cell, monthAnchor);
                            const list = onCallByDay[iso] ?? [];
                            return (
                              <td
                                key={iso}
                                className="align-top border-r px-1.5 py-2 last:border-r-0"
                              >
                                <div
                                  className={`mb-1 text-xs font-semibold ${
                                    inMonth ? 'text-foreground' : 'text-muted-foreground/60'
                                  }`}
                                >
                                  {format(cell, 'd')}
                                </div>
                                <div className="flex min-h-[72px] flex-col gap-1">
                                  {list.map((s) => (
                                    <button
                                      key={s.id}
                                      type="button"
                                      className="w-full truncate rounded-md border border-indigo-200/80 bg-indigo-100 px-2 py-1 text-left text-[11px] font-medium text-indigo-950 ring-1 ring-black/5 transition hover:bg-indigo-200 dark:border-indigo-800 dark:bg-indigo-950 dark:text-indigo-100 dark:hover:bg-indigo-900"
                                      onClick={() => openEdit(s)}
                                      title="Voir / modifier"
                                    >
                                      {employeeShort(s)}
                                    </button>
                                  ))}
                                </div>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      ) : null}

      {viewMode === 'remplacements' ? (
        <div className="space-y-4">
          {!isRH ? (
            <div className="rounded-md border bg-muted/30 p-6 text-sm text-muted-foreground">
              La vue remplacements est réservée aux accès RH.
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <h2 className="text-lg font-semibold tracking-tight">
                  Gestion des remplacements
                </h2>
                <Button type="button" size="sm" onClick={openReplacementDialog}>
                  <Plus className="mr-1 h-4 w-4" />
                  Planifier un remplacement
                </Button>
              </div>
              {replacementsQuery.isLoading ? (
                <div className="space-y-2 rounded-md border p-4">
                  <Skeleton className="h-8 w-48" />
                  <Skeleton className="h-40 w-full" />
                </div>
              ) : replacementsQuery.isError ? (
                <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
                  {apiErrorMessage(replacementsQuery.error)}
                </div>
              ) : (replacementsQuery.data?.length ?? 0) === 0 ? (
                <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
                  Aucun remplacement ce mois-ci.
                </div>
              ) : (
                <div className="w-full overflow-x-auto rounded-md border">
                  <table className="w-full min-w-[880px] border-collapse text-sm">
                    <thead>
                      <tr className="border-b bg-muted/40">
                        <th className="border-r px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Date
                        </th>
                        <th className="border-r px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Remplaçant
                        </th>
                        <th className="border-r px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Remplacé
                        </th>
                        <th className="border-r px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Horaires
                        </th>
                        <th className="border-r px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Motif
                        </th>
                        <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {(replacementsQuery.data ?? []).map((s) => (
                        <tr key={s.id} className="border-b last:border-b-0">
                          <td className="border-r px-3 py-2 align-top text-muted-foreground">
                            {formatDateFrCell(s.shift_date)}
                          </td>
                          <td className="border-r px-3 py-2 align-top font-medium">
                            {replacerDisplayName(s)}
                          </td>
                          <td className="border-r px-3 py-2 align-top">
                            {s.original_employee_name ?? '—'}
                          </td>
                          <td className="border-r px-3 py-2 align-top tabular-nums">
                            {formatHourRange(s)}
                          </td>
                          <td className="border-r px-3 py-2 align-top text-muted-foreground">
                            {s.replacement_reason?.trim() ? s.replacement_reason : '—'}
                          </td>
                          <td className="px-3 py-2 align-top text-right">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                              disabled={deleteMutation.isPending || s.is_locked}
                              title={s.is_locked ? 'Shift verrouillé' : 'Supprimer'}
                              onClick={() => {
                                if (!s.is_locked) deleteMutation.mutate(s.id);
                              }}
                              aria-label="Supprimer le remplacement"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      ) : null}

      <Dialog open={onCallDialogOpen} onOpenChange={setOnCallDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nouvelle astreinte</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="oncall-employee">Employé</Label>
              <Select
                value={onCallEmployeeId || undefined}
                onValueChange={setOnCallEmployeeId}
              >
                <SelectTrigger id="oncall-employee">
                  <SelectValue placeholder="Choisir un salarié" />
                </SelectTrigger>
                <SelectContent>
                  {(employees ?? []).map((e) => (
                    <SelectItem key={e.id} value={e.id}>
                      {e.last_name} {e.first_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="oncall-date">Date</Label>
              <Input
                id="oncall-date"
                type="date"
                value={onCallDate}
                onChange={(e) => setOnCallDate(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="oncall-start">Heure début</Label>
                <Input
                  id="oncall-start"
                  type="time"
                  step={60}
                  value={onCallStart}
                  onChange={(e) => setOnCallStart(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="oncall-end">Heure fin</Label>
                <Input
                  id="oncall-end"
                  type="time"
                  step={60}
                  value={onCallEnd}
                  onChange={(e) => setOnCallEnd(e.target.value)}
                />
              </div>
            </div>
          </div>
          <DialogFooter className="gap-2 sm:justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOnCallDialogOpen(false)}
              disabled={createOnCallMutation.isPending}
            >
              Annuler
            </Button>
            <Button
              type="button"
              onClick={submitOnCall}
              disabled={createOnCallMutation.isPending}
            >
              Confirmer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={replacementDialogOpen} onOpenChange={setReplacementDialogOpen}>
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Planifier un remplacement</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="rep-original">Salarié remplacé</Label>
              <Select value={repOriginalId || undefined} onValueChange={setRepOriginalId}>
                <SelectTrigger id="rep-original">
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent>
                  {(employees ?? []).map((e) => (
                    <SelectItem key={e.id} value={e.id}>
                      {e.last_name} {e.first_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rep-replacing">Salarié remplaçant</Label>
              <Select value={repReplacingId || undefined} onValueChange={setRepReplacingId}>
                <SelectTrigger id="rep-replacing">
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent>
                  {(employees ?? []).map((e) => (
                    <SelectItem key={e.id} value={e.id}>
                      {e.last_name} {e.first_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rep-type">Type de shift</Label>
              <Select value={repShiftTypeId || undefined} onValueChange={setRepShiftTypeId}>
                <SelectTrigger id="rep-type">
                  <SelectValue placeholder="Choisir un type" />
                </SelectTrigger>
                <SelectContent>
                  {(shiftTypesQuery.data ?? []).map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rep-date">Date</Label>
              <Input
                id="rep-date"
                type="date"
                value={repDate}
                onChange={(e) => setRepDate(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="rep-start">Heure début</Label>
                <Input
                  id="rep-start"
                  type="time"
                  step={60}
                  value={repStart}
                  onChange={(e) => setRepStart(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rep-end">Heure fin</Label>
                <Input
                  id="rep-end"
                  type="time"
                  step={60}
                  value={repEnd}
                  onChange={(e) => setRepEnd(e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rep-reason">Motif (optionnel)</Label>
              <Input
                id="rep-reason"
                value={repReason}
                onChange={(e) => setRepReason(e.target.value)}
                placeholder="Ex. absence, formation…"
              />
            </div>
          </div>
          <DialogFooter className="gap-2 sm:justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => setReplacementDialogOpen(false)}
              disabled={createReplacementMutation.isPending}
            >
              Annuler
            </Button>
            <Button
              type="button"
              onClick={submitReplacement}
              disabled={createReplacementMutation.isPending}
            >
              Confirmer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
