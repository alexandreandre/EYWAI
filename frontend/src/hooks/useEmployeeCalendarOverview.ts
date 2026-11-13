import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  fetchAllEmployeesOverview,
  computeGlobalKpis,
  applyDayPatchToRow,
  persistEmployeeMonth,
  rowFromCalendarSnapshot,
  type EmployeeCalendarOverviewRow,
  type SchedulesEmployeeInput,
  type GlobalOverviewKpis,
  type DayPatch,
} from '@/lib/schedulesOverview';
import { calendarSaveFailureMessage } from '@/lib/calendarSaveFeedback';
import { invalidateRhSidebarBadges } from '@/lib/invalidateRhSidebarBadges';
import { getPeriodeVariables } from '@/api/periodeVariables';
import { useObservedPublicHolidays } from '@/hooks/useObservedPublicHolidays';
import { useToast } from '@/components/ui/use-toast';
import {
  planningWarningsToast,
  summarizePlanningWarnings,
} from '@/lib/planningAbsenceWarnings';

const EMPTY_ROWS: EmployeeCalendarOverviewRow[] = [];

export function useEmployeeCalendarOverview(
  employees: SchedulesEmployeeInput[],
  year: number,
  month: number
) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { activeCompanyId, observedHolidayIds } = useObservedPublicHolidays();
  const [rows, setRows] = useState<EmployeeCalendarOverviewRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const rowsRef = useRef<EmployeeCalendarOverviewRow[]>([]);
  const pending = useRef(new Set<string>());
  const loadSequence = useRef(0);
  const context = useMemo(() => ({ active: false, year, month, activeCompanyId, employees }), [year, month, activeCompanyId, employees]);
  const [loadedContext, setLoadedContext] = useState<object | null>(null);
  useLayoutEffect(() => {
    context.active = true;
    return () => { context.active = false; };
  }, [context]);
  const visibleRows = loadedContext === context ? rows : EMPTY_ROWS;
  rowsRef.current = visibleRows;

  const load = useCallback(async () => {
    if (!context.active) return;
    const request = ++loadSequence.current;
    const isCurrent = () => context.active && request === loadSequence.current;
    setLoadedContext(null);
    if (employees.length === 0) {
      setRows([]);
      setLoadedContext(context);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      // Fin de la fenêtre des variables : les jours d'après sont au mois
      // suivant, ils ne s'affichent pas en anomalie. Illisible : tout le mois
      // est jugé (règle stricte, jamais un mois oublié en silence).
      const finFenetre = await getPeriodeVariables(year, month)
        .then((p) => p.fin)
        .catch((): null => null);
      const result = await fetchAllEmployeesOverview(
        employees,
        year,
        month,
        5,
        observedHolidayIds,
        { finFenetre, companyId: activeCompanyId }
      );
      if (!isCurrent()) return;
      setRows(result);
      setLoadedContext(context);
    } finally {
      if (isCurrent()) setIsLoading(false);
    }
  }, [employees, year, month, observedHolidayIds, activeCompanyId, context]);

  useEffect(() => {
    void load();
  }, [load]);

  const globalKpis: GlobalOverviewKpis = useMemo(
    () => computeGlobalKpis(visibleRows),
    [visibleRows]
  );

  const updateRow = useCallback(
    (employeeId: string, patch: Partial<EmployeeCalendarOverviewRow>) => {
      setRows((prev) =>
        prev.map((r) =>
          r.employee.id === employeeId ? { ...r, ...patch } : r
        )
      );
    },
    []
  );

  /**
   * Mise à jour optimiste d'un jour pour un employé + persistance backend.
   * Les saisies non confirmées restent visibles ; recharge explicite avant reprise.
   */
  const applyAndPersistDayPatch = useCallback(
    async (employeeId: string, day: number, patch: DayPatch): Promise<boolean> => {
      const previousRow = rowsRef.current.find(
        (r) => r.employee.id === employeeId
      );
      if (!context.active || !previousRow || previousRow.loadError || previousRow.revision === undefined || pending.current.has(employeeId)) return false;
      pending.current.add(employeeId);
      const loadAtStart = loadSequence.current;
      const isCurrent = () => context.active && loadAtStart === loadSequence.current;

      const nextRow = applyDayPatchToRow(previousRow, day, patch, year, month);
      setRows((prev) =>
        prev.map((r) => (r.employee.id === employeeId ? nextRow : r))
      );

      try {
        const saved = await persistEmployeeMonth(
          employeeId,
          year,
          month,
          nextRow.planned,
          nextRow.actual,
          { companyId: activeCompanyId, expectedRevision: previousRow.revision },
        );
        if (!isCurrent()) return false;
        setRows((current) => current.map((r) => r.employee.id === employeeId ? rowFromCalendarSnapshot(nextRow, saved, year, month) : r));
        // Demandes de congé créées/annulées par la saisie, écarts de solde…
        // — la vue semaine doit le dire autant que le calendrier complet.
        const warningsToast = planningWarningsToast(
          summarizePlanningWarnings(saved.warnings)
        );
        if (warningsToast) toast(warningsToast);
        void invalidateRhSidebarBadges(queryClient);
        return true;
      } catch (err) {
        if (isCurrent()) {
          setRows((prev) => prev.map((r) => r.employee.id === employeeId ? { ...nextRow, rowStatus: 'a_saisir', loadError: true } : r));
          toast({ title: 'Enregistrement incomplet', description: calendarSaveFailureMessage(err), variant: 'destructive' });
        }
        return false;
      } finally {
        pending.current.delete(employeeId);
      }
    },
    [year, month, queryClient, toast, context, activeCompanyId]
  );

  return {
    rows: visibleRows,
    isLoading: isLoading || loadedContext !== context,
    loadErrors: visibleRows.filter((row) => row.loadError).length,
    globalKpis,
    refetch: load,
    updateRow,
    applyAndPersistDayPatch,
  };
}
