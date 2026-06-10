import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { RefreshCw } from 'lucide-react';
import { useEmployeesQuery } from '@/hooks/queries/useEmployeesQuery';
import { getTeams, type Team } from '@/api/teams';
import * as calendarApi from '@/api/calendar';
import { useEmployeeCalendarOverview } from '@/hooks/useEmployeeCalendarOverview';
import type { SchedulesEmployeeInput } from '@/lib/schedulesOverview';
import { useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';
import { CalendarPilotHeader } from '@/components/schedules/CalendarPilotHeader';
import { CalendarFiltersBar } from '@/components/schedules/CalendarFiltersBar';
import { CalendarEmployeeTable } from '@/components/schedules/CalendarEmployeeTable';
import { CalendarEmployeeDrawer } from '@/components/schedules/CalendarEmployeeDrawer';
import { CalendarBulkActionsBar } from '@/components/schedules/CalendarBulkActionsBar';
import { ApplyModelDialog } from '@/components/schedules/ApplyModelDialog';
import { AssistedFillDialog } from '@/components/schedules/assisted-fill/AssistedFillDialog';
import { PointageImportDialog } from '@/components/schedules/assisted-fill/PointageImportDialog';
import { TeamPlanningView } from '@/components/schedules/TeamPlanningView';
import type {
  ModeFilter,
  SaisieStatusFilter,
  SortDir,
  SortKey,
  ViewMode,
} from '@/components/schedules/types';
import { invalidateRhSidebarBadges } from '@/lib/invalidateRhSidebarBadges';

function employeesLoadErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (error.response?.status === 503) {
      return 'Service temporairement indisponible. Réessayez dans quelques secondes.';
    }
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return 'Impossible de charger la liste des employés.';
}

interface Employee extends SchedulesEmployeeInput {
  job_title: string;
}

export default function Schedules() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const now = new Date();
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());

  const employeesQuery = useEmployeesQuery();
  const employees = (employeesQuery.data ?? []) as Employee[];
  const employeesLoading = employeesQuery.isLoading && !employeesQuery.data;
  const employeesLoadError = employeesQuery.isError;
  const refetchEmployees = employeesQuery.refetch;
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTeamIds, setSelectedTeamIds] = useState<string[]>([]);
  const [saisieFilter, setSaisieFilter] = useState<SaisieStatusFilter>('all');
  const [modeFilter, setModeFilter] = useState<ModeFilter>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('team');

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [drawerEmployeeId, setDrawerEmployeeId] = useState<string | null>(null);
  const [applyModelOpen, setApplyModelOpen] = useState(false);
  const [assistedFillOpen, setAssistedFillOpen] = useState(false);
  const [pointageImportOpen, setPointageImportOpen] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const { data: teamsData } = useQuery({
    queryKey: ['teams-active'],
    queryFn: () => getTeams(false),
  });

  const teams: Team[] = teamsData?.teams ?? [];
  const teamsById = useMemo(
    () => new Map(teams.map((t) => [t.id, t])),
    [teams]
  );

  const employeeInputs: SchedulesEmployeeInput[] = employees;

  const { rows, isLoading, loadErrors, globalKpis, refetch, applyAndPersistDayPatch } =
    useEmployeeCalendarOverview(employeeInputs, selectedYear, selectedMonth);

  const refreshCalendars = useCallback(() => {
    void refetch();
    void invalidateRhSidebarBadges(queryClient);
  }, [refetch, queryClient]);

  const isPageLoading =
    employeesLoading ||
    isLoading ||
    (employees.length > 0 && rows.length === 0);

    useEffect(() => {
    if (loadErrors > 0) {
      toast({
        title: 'Attention',
        description: `${loadErrors} calendrier(s) n'ont pas pu être chargés.`,
        variant: 'destructive',
      });
    }
  }, [loadErrors, toast]);

  const filteredRows = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    return rows.filter((row) => {
      if (q) {
        const match =
          row.employee.first_name.toLowerCase().includes(q) ||
          row.employee.last_name.toLowerCase().includes(q) ||
          (row.employee.job_title ?? '').toLowerCase().includes(q);
        if (!match) return false;
      }
      if (
        selectedTeamIds.length > 0 &&
        (!row.employee.team_id || !selectedTeamIds.includes(row.employee.team_id))
      ) {
        return false;
      }
      if (saisieFilter !== 'all' && row.rowStatus !== saisieFilter) return false;
      if (modeFilter === 'forfait_jour' && !row.isForfaitJour) return false;
      if (modeFilter === 'horaire' && row.isForfaitJour) return false;
      return true;
    });
  }, [rows, searchQuery, selectedTeamIds, saisieFilter, modeFilter]);

  const sortedRows = useMemo(() => {
    const sorted = [...filteredRows];
    const dir = sortDir === 'asc' ? 1 : -1;

    sorted.sort((a, b) => {
      switch (sortKey) {
        case 'team': {
          const ta = a.employee.team_id
            ? teamsById.get(a.employee.team_id)?.name ?? ''
            : '';
          const tb = b.employee.team_id
            ? teamsById.get(b.employee.team_id)?.name ?? ''
            : '';
          return ta.localeCompare(tb, 'fr') * dir;
        }
        case 'status':
          return a.rowStatus.localeCompare(b.rowStatus) * dir;
        case 'heures_prevues':
          return (a.heuresPrevues - b.heuresPrevues) * dir;
        case 'heures_faites':
          return (a.heuresFaites - b.heuresFaites) * dir;
        case 'ecart':
          return (a.ecart - b.ecart) * dir;
        case 'name':
        default: {
          const na = `${a.employee.last_name} ${a.employee.first_name}`;
          const nb = `${b.employee.last_name} ${b.employee.first_name}`;
          return na.localeCompare(nb, 'fr') * dir;
        }
      }
    });
    return sorted;
  }, [filteredRows, sortKey, sortDir, teamsById]);

  const visibleIds = sortedRows.map((r) => r.employee.id);

  const orderedEmployeesForDrawer = useMemo(
    () => sortedRows.map((r) => r.employee),
    [sortedRows]
  );

  const drawerEmployee = drawerEmployeeId
    ? employees.find((e) => e.id === drawerEmployeeId) ?? null
    : null;

  const assistedFillRoster = useMemo(
    () =>
      employees.map((e) => ({
        id: e.id,
        first_name: e.first_name,
        last_name: e.last_name,
      })),
    [employees]
  );

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = (ids: string[]) => {
    const allSelected = ids.length > 0 && ids.every((id) => selectedIds.has(id));
    if (allSelected) {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        ids.forEach((id) => next.delete(id));
        return next;
      });
      } else {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        ids.forEach((id) => next.add(id));
        return next;
      });
    }
  };

  const selectLatecomers = () => {
    const late = sortedRows
      .filter((r) => r.rowStatus === 'a_saisir')
      .map((r) => r.employee.id);
    setSelectedIds(new Set(late));
  };

  const allSaisiBanner =
    !isPageLoading &&
    filteredRows.length > 0 &&
    filteredRows.every((r) => r.rowStatus !== 'a_saisir');

      return (
    <div className="space-y-2 pb-28">
      <CalendarPilotHeader
        year={selectedYear}
        month={selectedMonth}
        onYearChange={setSelectedYear}
        onMonthChange={setSelectedMonth}
        kpis={globalKpis}
        isLoading={isPageLoading}
        onOpenAssistedFill={() => setAssistedFillOpen(true)}
        onOpenPointageImport={() => setPointageImportOpen(true)}
      />

      {employeesLoadError && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-center">
          <p className="text-sm text-destructive">
            {employeesLoadErrorMessage(employeesQuery.error)}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-3 gap-2"
            onClick={() => void refetchEmployees()}
          >
            <RefreshCw className="h-4 w-4" />
            Réessayer
          </Button>
        </div>
      )}

      <CalendarFiltersBar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        teams={teams}
        selectedTeamIds={selectedTeamIds}
        onTeamIdsChange={setSelectedTeamIds}
        saisieFilter={saisieFilter}
        onSaisieFilterChange={setSaisieFilter}
        modeFilter={modeFilter}
        onModeFilterChange={setModeFilter}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        onSelectLatecomers={selectLatecomers}
        filteredCount={filteredRows.length}
        totalCount={rows.length}
        isLoading={isPageLoading}
      />

      {allSaisiBanner && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50/80 px-4 py-3 text-sm text-emerald-900">
          Tous les calendriers affichés sont saisis pour ce mois. Vous pouvez lancer le
          calcul de paie.
                        </div>
                      )}

      {viewMode === 'list' ? (
        <CalendarEmployeeTable
          rows={sortedRows}
          teamsById={teamsById}
          isLoading={isPageLoading}
          employeesLoadError={employeesLoadError}
          employeesLoadErrorMessage={employeesLoadErrorMessage(employeesQuery.error)}
          onRetryEmployees={() => void refetchEmployees()}
          unfilteredRowCount={rows.length}
          selectedIds={selectedIds}
          onToggleSelect={toggleSelect}
          onToggleSelectAll={toggleSelectAll}
          onOpenEmployee={setDrawerEmployeeId}
          sortKey={sortKey}
          sortDir={sortDir}
          onSort={handleSort}
          visibleIds={visibleIds}
        />
      ) : (
        <TeamPlanningView
          rows={sortedRows}
          year={selectedYear}
          month={selectedMonth}
          isLoading={isPageLoading}
          employeesLoadError={employeesLoadError}
          employeesLoadErrorMessage={employeesLoadErrorMessage(employeesQuery.error)}
          onRetryEmployees={() => void refetchEmployees()}
          unfilteredRowCount={rows.length}
          onApplyDayPatch={applyAndPersistDayPatch}
          onOpenEmployee={setDrawerEmployeeId}
        />
      )}

      <CalendarEmployeeDrawer
        open={drawerEmployeeId !== null}
        onOpenChange={(open) => !open && setDrawerEmployeeId(null)}
        employee={drawerEmployee}
        orderedEmployees={orderedEmployeesForDrawer}
        year={selectedYear}
        month={selectedMonth}
        onNavigate={setDrawerEmployeeId}
        onSaved={refreshCalendars}
      />

      <CalendarBulkActionsBar
        selectedCount={selectedIds.size}
        selectedEmployeeIds={[...selectedIds]}
        year={selectedYear}
        month={selectedMonth}
        overviewRows={rows}
        onClearSelection={() => setSelectedIds(new Set())}
        onOpenApplyModel={() => setApplyModelOpen(true)}
        onActionComplete={refreshCalendars}
      />

      <ApplyModelDialog
        open={applyModelOpen}
        onOpenChange={setApplyModelOpen}
        selectedEmployeeIds={[...selectedIds]}
        year={selectedYear}
        month={selectedMonth}
        onApplied={() => {
          setSelectedIds(new Set());
          refreshCalendars();
        }}
      />

      <AssistedFillDialog
        open={assistedFillOpen}
        onOpenChange={setAssistedFillOpen}
        year={selectedYear}
        month={selectedMonth}
        roster={assistedFillRoster}
        onApplied={refreshCalendars}
      />

      <PointageImportDialog
        open={pointageImportOpen}
        onOpenChange={setPointageImportOpen}
        year={selectedYear}
        month={selectedMonth}
        roster={assistedFillRoster}
        onApplied={refreshCalendars}
      />
    </div>
  );
}
