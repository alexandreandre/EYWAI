import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  fetchAllEmployeesOverview,
  computeGlobalKpis,
  applyDayPatchToRow,
  persistEmployeeMonth,
  type EmployeeCalendarOverviewRow,
  type SchedulesEmployeeInput,
  type GlobalOverviewKpis,
  type DayPatch,
} from '@/lib/schedulesOverview';
import { invalidateRhSidebarBadges } from '@/lib/invalidateRhSidebarBadges';

export function useEmployeeCalendarOverview(
  employees: SchedulesEmployeeInput[],
  year: number,
  month: number
) {
  const queryClient = useQueryClient();
  const [rows, setRows] = useState<EmployeeCalendarOverviewRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadErrors, setLoadErrors] = useState(0);
  const rowsRef = useRef<EmployeeCalendarOverviewRow[]>([]);
  rowsRef.current = rows;

  const load = useCallback(async () => {
    if (employees.length === 0) {
      setRows([]);
      return;
    }
    setIsLoading(true);
    try {
      const result = await fetchAllEmployeesOverview(employees, year, month);
      setRows(result);
      setLoadErrors(result.filter((r) => r.loadError).length);
    } finally {
      setIsLoading(false);
    }
  }, [employees, year, month]);

  useEffect(() => {
    void load();
  }, [load]);

  const globalKpis: GlobalOverviewKpis = useMemo(
    () => computeGlobalKpis(rows),
    [rows]
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
   * Rollback automatique en cas d'erreur.
   */
  const applyAndPersistDayPatch = useCallback(
    async (employeeId: string, day: number, patch: DayPatch): Promise<boolean> => {
      const previousRow = rowsRef.current.find(
        (r) => r.employee.id === employeeId
      );
      if (!previousRow) return false;

      const nextRow = applyDayPatchToRow(previousRow, day, patch, year, month);
      setRows((prev) =>
        prev.map((r) => (r.employee.id === employeeId ? nextRow : r))
      );

      try {
        await persistEmployeeMonth(
          employeeId,
          year,
          month,
          nextRow.planned,
          nextRow.actual
        );
        void invalidateRhSidebarBadges(queryClient);
        return true;
      } catch (err) {
        setRows((prev) =>
          prev.map((r) => (r.employee.id === employeeId ? previousRow : r))
        );
        throw err;
      }
    },
    [year, month, queryClient]
  );

  return {
    rows,
    isLoading,
    loadErrors,
    globalKpis,
    refetch: load,
    updateRow,
    applyAndPersistDayPatch,
  };
}
