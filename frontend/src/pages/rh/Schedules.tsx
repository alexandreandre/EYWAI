import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { RefreshCw } from 'lucide-react';
import { useEmployeesQuery } from '@/hooks/queries/useEmployeesQuery';
import { getTeams, type Team } from '@/api/teams';
import * as calendarApi from '@/api/calendar';
import { useEmployeeCalendarOverview } from '@/hooks/useEmployeeCalendarOverview';
import type { SchedulesEmployeeInput } from '@/lib/schedulesOverview';
import { filterPresentEmployees } from '@/lib/employmentStatus';
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
import { PointageImportBanner } from '@/components/schedules/assisted-fill/PointageImportBanner';
import { usePointageImportJobs, type PointageImportJob } from '@/hooks/usePointageImportJobs';
import { PlanningImportBanner } from '@/components/schedules/PlanningImportBanner';
import { usePlanningImportJobs, type PlanningImportJob } from '@/hooks/usePlanningImportJobs';
import { TeamPlanningView } from '@/components/schedules/TeamPlanningView';
import { PlanningImportPanel } from '@/features/admin-import/components/PlanningImportPanel';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import type {
  ModeFilter,
  SaisieStatusFilter,
  SortDir,
  SortKey,
  ViewMode,
} from '@/components/schedules/types';
import { Dialog, DialogContent } from '@/components/ui/dialog';
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
  const companyId = useActiveCompanyId();
  const now = new Date();
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());

  const employeesQuery = useEmployeesQuery();
  const employees = useMemo(
    () => filterPresentEmployees((employeesQuery.data ?? []) as Employee[]),
    [employeesQuery.data],
  );
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
  const [aiTargetIds, setAiTargetIds] = useState<string[] | null>(null);
  const [calendarImportOpen, setCalendarImportOpen] = useState(false);
  const [planningReviewJob, setPlanningReviewJob] = useState<PlanningImportJob | null>(null);
  const [pointageImportOpen, setPointageImportOpen] = useState(false);
  const [pointageReviewJob, setPointageReviewJob] = useState<PointageImportJob | null>(null);
  const {
    activeJobs: pointageActiveJobs,
    reviewJobs: pointageReviewJobs,
    cancelJob: cancelPointageJob,
    dismissReview: dismissPointageReview,
  } = usePointageImportJobs();
  const {
    activeJobs: planningActiveJobs,
    finishedJobs: planningFinishedJobs,
    dismissJob: dismissPlanningJob,
    cancelJob: cancelPlanningJob,
  } = usePlanningImportJobs();
  const handledPlanningImportJobsRef = useRef<Set<string>>(new Set());
  const [planningFocusWeek, setPlanningFocusWeek] = useState<number | null>(null);
  const [planningHighlightDays, setPlanningHighlightDays] = useState<number[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const { data: teamsData } = useQuery({
    queryKey: ['teams-active'],
    queryFn: () => getTeams(false),
  });

  const teams: Team[] = useMemo(() => teamsData?.teams ?? [], [teamsData?.teams]);
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

  useEffect(() => {
    planningFinishedJobs.forEach((job) => {
      if (handledPlanningImportJobsRef.current.has(job.localId)) return;
      handledPlanningImportJobsRef.current.add(job.localId);

      if (job.status === 'committed') {
        refreshCalendars();
        toast({
          title: 'Calendrier enregistré',
          description: `${job.employeesProcessed ?? 0} salarié(s), ${(job.totalDaysWritten ?? 0).toLocaleString('fr-FR')} jour(s) de calendrier prévu.`,
        });
        return;
      }

      if (job.status === 'failed') {
        toast({
          title: 'Import calendrier interrompu',
          description: job.errorMessage ?? "L'enregistrement a échoué.",
          variant: 'destructive',
        });
        return;
      }

      if (job.status === 'cancelled') {
        refreshCalendars();
        toast({
          title: 'Import calendrier annulé',
          description:
            job.errorMessage ?? 'Les mois déjà enregistrés ont été conservés.',
        });
      }
    });
  }, [planningFinishedJobs, refreshCalendars, toast]);

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

  const aSaisirRows = useMemo(
    () => sortedRows.filter((r) => r.rowStatus === 'a_saisir'),
    [sortedRows]
  );

  const orderedEmployeesForDrawer = useMemo(
    () => sortedRows.map((r) => r.employee),
    [sortedRows]
  );

  const selectedEmployeeTeamId = useMemo(() => {
    const teamIds = new Set(
      [...selectedIds]
        .map((id) => rows.find((r) => r.employee.id === id)?.employee.team_id)
        .filter((id): id is string => Boolean(id)),
    );
    return teamIds.size === 1 ? [...teamIds][0] : null;
  }, [selectedIds, rows]);

  const drawerEmployee = drawerEmployeeId
    ? employees.find((e) => e.id === drawerEmployeeId) ?? null
    : null;

  const assistedFillRoster = useMemo(
    () =>
      employees.map((e) => ({
        id: e.id,
        first_name: e.first_name,
        last_name: e.last_name,
        time_tracking_id:
          (e as { time_tracking_id?: string | null }).time_tracking_id ?? null,
      })),
    [employees]
  );

  const aiDialogRoster = useMemo(() => {
    if (!aiTargetIds) return assistedFillRoster;
    const byId = new Map(
      rows.map((r) => [
        r.employee.id,
        {
          id: r.employee.id,
          first_name: r.employee.first_name,
          last_name: r.employee.last_name,
        },
      ])
    );
    return aiTargetIds
      .map((id) => byId.get(id))
      .filter((e): e is (typeof assistedFillRoster)[number] => e != null);
  }, [assistedFillRoster, aiTargetIds, rows]);

  const aiTargetSummary = useMemo(() => {
    if (!aiTargetIds) return null;
    return {
      count: aiDialogRoster.length,
      names: aiDialogRoster.map((e) => `${e.last_name} ${e.first_name}`),
    };
  }, [aiTargetIds, aiDialogRoster]);

  const openAssistedFillForSelection = useCallback((ids: string[]) => {
    setAiTargetIds(ids);
    setAssistedFillOpen(true);
  }, []);

  // Bouton d'en-tête : l'IA agit sur la sélection courante s'il y en a une,
  // sinon consigne libre sur tout le roster.
  const openAssistedFillFromHeader = useCallback(() => {
    if (selectedIds.size > 0) {
      setAiTargetIds([...selectedIds]);
    } else {
      setAiTargetIds(null);
    }
    setAssistedFillOpen(true);
  }, [selectedIds]);

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
        onOpenAssistedFill={openAssistedFillFromHeader}
        onOpenPointageImport={() => setPointageImportOpen(true)}
      />

      <PointageImportBanner
        jobs={[...pointageActiveJobs, ...pointageReviewJobs]}
        onReview={(job) => {
          setPointageReviewJob(job);
          setPointageImportOpen(true);
        }}
        onCancel={(job) => void cancelPointageJob(job.localId)}
        onDismiss={(job) => dismissPointageReview(job.localId)}
      />

      <PlanningImportBanner
        jobs={[...planningActiveJobs, ...planningFinishedJobs]}
        onReview={(job) => {
          if (!job.parseResult) return;
          setPlanningReviewJob(job);
          setCalendarImportOpen(true);
        }}
        onCancel={(job) => void cancelPlanningJob(job.localId)}
        onDismiss={(job) => dismissPlanningJob(job.localId)}
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
        filteredCount={filteredRows.length}
        totalCount={rows.length}
        aSaisirCount={aSaisirRows.length}
        isLoading={isPageLoading}
      />

      {allSaisiBanner && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50/80 px-4 py-3 text-sm text-emerald-900">
          Tous les calendriers affichés sont prêts pour la paie ce mois-ci. Vous pouvez lancer le
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
          initialWeekIndex={planningFocusWeek}
          highlightDays={planningHighlightDays}
          selectedIds={selectedIds}
          onToggleSelect={toggleSelect}
          onToggleSelectAll={toggleSelectAll}
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
        onFillWithAi={openAssistedFillForSelection}
      />

      <ApplyModelDialog
        open={applyModelOpen}
        onOpenChange={setApplyModelOpen}
        selectedEmployeeIds={[...selectedIds]}
        employeeTeamId={selectedEmployeeTeamId}
        year={selectedYear}
        month={selectedMonth}
        onApplied={() => {
          setSelectedIds(new Set());
          refreshCalendars();
        }}
      />

      <AssistedFillDialog
        open={assistedFillOpen}
        onOpenChange={(open) => {
          setAssistedFillOpen(open);
          if (!open) setAiTargetIds(null);
        }}
        year={selectedYear}
        month={selectedMonth}
        roster={aiDialogRoster}
        targetSummary={aiTargetSummary}
        broadcast={aiTargetIds !== null}
        onApplied={refreshCalendars}
      />

      <Dialog
        open={calendarImportOpen}
        onOpenChange={(open) => {
          setCalendarImportOpen(open);
          if (!open) setPlanningReviewJob(null);
        }}
      >
        <DialogContent className="max-h-[90vh] max-w-5xl overflow-y-auto p-0">
          {companyId ? (
            <PlanningImportPanel
              companyId={companyId}
              initialParseResult={planningReviewJob?.parseResult ?? null}
              embedded
              backgroundCommit
              onParseStarted={() => {
                setPlanningReviewJob(null);
                setCalendarImportOpen(false);
              }}
              onCommitStarted={() => {
                if (planningReviewJob) dismissPlanningJob(planningReviewJob.localId);
                setPlanningReviewJob(null);
                setCalendarImportOpen(false);
              }}
              onComplete={() => {
                setCalendarImportOpen(false);
                refreshCalendars();
              }}
            />
          ) : (
            <div className="p-6 text-sm text-muted-foreground">
              Sélectionnez une entreprise pour importer un calendrier.
            </div>
          )}
        </DialogContent>
      </Dialog>

      <PointageImportDialog
        open={pointageImportOpen}
        onOpenChange={setPointageImportOpen}
        year={selectedYear}
        month={selectedMonth}
        roster={assistedFillRoster}
        pendingReview={pointageReviewJob}
        onPendingReviewConsumed={() => setPointageReviewJob(null)}
        onApplied={(meta) => {
          refreshCalendars();
          if (meta?.focusWeekIndex != null) {
            setPlanningFocusWeek(meta.focusWeekIndex);
            if (viewMode !== 'team') setViewMode('team');
          }
          if (meta?.highlightDays?.length) {
            setPlanningHighlightDays(meta.highlightDays);
          }
        }}
        onNavigateToMonth={(y, m) => {
          setSelectedYear(y);
          setSelectedMonth(m);
        }}
        onFocusPlanningWeek={(weekIndex) => {
          setPlanningFocusWeek(weekIndex);
          if (viewMode !== 'team') setViewMode('team');
        }}
      />
    </div>
  );
}
