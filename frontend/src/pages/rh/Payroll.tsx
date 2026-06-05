import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueries, useQueryClient } from '@tanstack/react-query';
import { RhPageHeader } from '@/components/layout';
import { PageFetchIndicator } from '@/components/skeletons/PageFetchIndicator';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { usePayrollEmployeesQuery, type EmployeeListItem } from '@/hooks/queries/useEmployeesQuery';
import { useEmployeePayslipsQuery } from '@/hooks/queries/useEmployeePayslipsQuery';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { deletePayslip, getEmployeePayslips, type PayslipInfo } from '@/api/payslips';
import { queryKeys } from '@/lib/queryKeys';
import { showErrorToast } from '@/lib/errorMessages';
import { PayrollEmployeeExplorer } from '@/features/payroll/components/PayrollEmployeeExplorer';
import {
  PayrollMonthExplorer,
  type EmployeeMonthState,
} from '@/features/payroll/components/PayrollMonthExplorer';
import { PayrollGroupLaunchCta } from '@/features/payroll/components/PayrollGroupLaunchCta';
import { PayrollMonthList, type MonthStatusMap } from '@/features/payroll/components/PayrollMonthList';
import type { PayslipRowState } from '@/features/payroll/components/PayrollPayslipRow';
import { PayrollProgressBar } from '@/features/payroll/components/PayrollProgressBar';
import {
  usePayrollGeneration,
  type PayrollGenerationJob,
  type PayrollGenerationLogEntry,
} from '@/features/payroll/hooks/usePayrollGeneration';
import {
  buildYearOptions,
  PAYROLL_MONTHS,
} from '@/features/payroll/utils/payrollMonth';

type PayrollView = 'employee' | 'month';

function employeeDisplayName(emp: EmployeeListItem): string {
  return `${emp.first_name} ${emp.last_name}`;
}

function buildRowState(
  payslip: PayslipInfo | undefined,
  employeeId: string,
  year: number,
  month: number,
  generation: {
    currentJob: { employeeId: string; year: number; month: number } | null;
    queuedJobs: PayrollGenerationJob[];
    log: PayrollGenerationLogEntry[];
    failedJobs: Record<string, string>;
  }
): PayslipRowState {
  const logEntry = generation.log.find(
    (e) => e.employeeId === employeeId && e.year === year && e.month === month
  );
  const jobKey = `${employeeId}-${year}-${month}`;
  const persistedError = generation.failedJobs[jobKey];
  const isCurrent =
    generation.currentJob?.employeeId === employeeId &&
    generation.currentJob.year === year &&
    generation.currentJob.month === month;
  const isQueued = generation.queuedJobs.some(
    (job) => job.employeeId === employeeId && job.year === year && job.month === month
  );

  if (isCurrent || isQueued) {
    return { status: 'loading', payslip };
  }
  if (payslip) {
    return { status: 'success', payslip };
  }
  if (logEntry?.status === 'error' || persistedError) {
    return { status: 'error', errorMessage: logEntry?.error ?? persistedError };
  }
  return { status: 'idle' };
}

function buildMonthStatuses(
  payslipsForYear: PayslipInfo[],
  employeeId: string,
  year: number,
  generation: {
    currentJob: { employeeId: string; year: number; month: number } | null;
    queuedJobs: PayrollGenerationJob[];
    log: PayrollGenerationLogEntry[];
    failedJobs: Record<string, string>;
  }
): MonthStatusMap {
  const map: MonthStatusMap = {};
  for (const month of PAYROLL_MONTHS) {
    const payslip = payslipsForYear.find((p) => p.month === month);
    map[month] = buildRowState(payslip, employeeId, year, month, generation);
  }
  return map;
}

export default function Payroll() {
  const [searchParams, setSearchParams] = useSearchParams();
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();

  const employeesQuery = usePayrollEmployeesQuery();
  const employees = (employeesQuery.data ?? []) as EmployeeListItem[];

  const employeeFromUrl = searchParams.get('employee');
  const viewFromUrl = searchParams.get('view') === 'month' ? 'month' : 'employee';
  const [view, setView] = useState<PayrollView>(viewFromUrl);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(
    employeeFromUrl
  );
  const [selectedYear, setSelectedYear] = useState(() => new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(() => new Date().getMonth() + 1);
  const [deletingPayslipId, setDeletingPayslipId] = useState<string | null>(null);

  const generation = usePayrollGeneration();

  useEffect(() => () => generation.dismiss(), []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (employeeFromUrl) {
      setSelectedEmployeeId(employeeFromUrl);
    }
  }, [employeeFromUrl]);

  useEffect(() => {
    if (employees.length === 0) return;
    if (selectedEmployeeId && employees.some((e) => e.id === selectedEmployeeId)) return;
    if (employeeFromUrl && employees.some((e) => e.id === employeeFromUrl)) {
      setSelectedEmployeeId(employeeFromUrl);
      return;
    }
    setSelectedEmployeeId(employees[0]?.id ?? null);
  }, [employees, selectedEmployeeId, employeeFromUrl]);

  const selectEmployee = useCallback(
    (id: string) => {
      setSelectedEmployeeId(id);
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set('employee', id);
          return next;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  const handleViewChange = useCallback(
    (next: PayrollView) => {
      setView(next);
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev);
          if (next === 'month') {
            params.set('view', 'month');
          } else {
            params.delete('view');
          }
          return params;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  const payslipQueries = useQueries({
    queries: employees.map((emp) => ({
      queryKey: queryKeys.employeePayslips(companyId, emp.id),
      queryFn: () => getEmployeePayslips(emp.id),
      enabled: Boolean(companyId && employees.length > 0),
      staleTime: 30_000,
    })),
  });

  const yearCounts = useMemo(() => {
    const map: Record<string, number> = {};
    employees.forEach((emp, index) => {
      const data = payslipQueries[index]?.data ?? [];
      map[emp.id] = data.filter((p) => p.year === selectedYear).length;
    });
    return map;
  }, [employees, payslipQueries, selectedYear]);

  const selectedEmployee = employees.find((e) => e.id === selectedEmployeeId);
  const payslipsQuery = useEmployeePayslipsQuery(selectedEmployeeId ?? undefined);
  const allPayslips = payslipsQuery.data ?? [];
  const payslipsForYear = useMemo(
    () => allPayslips.filter((p) => p.year === selectedYear),
    [allPayslips, selectedYear]
  );

  const yearOptions = useMemo(
    () => buildYearOptions(allPayslips.map((p) => p.year), selectedYear),
    [allPayslips, selectedYear]
  );

  const generationState = useMemo(
    () => ({
      currentJob: generation.currentJob,
      queuedJobs: generation.queuedJobs,
      log: generation.log,
      failedJobs: generation.failedJobs,
    }),
    [generation.currentJob, generation.queuedJobs, generation.log, generation.failedJobs]
  );

  const monthStatuses = useMemo(() => {
    if (!selectedEmployeeId) return {};
    return buildMonthStatuses(payslipsForYear, selectedEmployeeId, selectedYear, generationState);
  }, [selectedEmployeeId, payslipsForYear, selectedYear, generationState]);

  const payslipsByEmployee = useMemo(() => {
    const map: Record<string, PayslipInfo[]> = {};
    employees.forEach((emp, index) => {
      map[emp.id] = payslipQueries[index]?.data ?? [];
    });
    return map;
  }, [employees, payslipQueries]);

  const monthGeneratedCounts = useMemo(() => {
    const counts: Record<number, number> = {};
    for (const month of PAYROLL_MONTHS) {
      counts[month] = employees.reduce((acc, emp) => {
        const has = (payslipsByEmployee[emp.id] ?? []).some(
          (p) => p.year === selectedYear && p.month === month
        );
        return acc + (has ? 1 : 0);
      }, 0);
    }
    return counts;
  }, [employees, payslipsByEmployee, selectedYear]);

  const monthEmployeeStates = useMemo<EmployeeMonthState[]>(() => {
    return employees.map((emp) => {
      const payslip = (payslipsByEmployee[emp.id] ?? []).find(
        (p) => p.year === selectedYear && p.month === selectedMonth
      );
      return {
        employee: emp,
        state: buildRowState(payslip, emp.id, selectedYear, selectedMonth, generationState),
      };
    });
  }, [employees, payslipsByEmployee, selectedYear, selectedMonth, generationState]);

  const monthMissingCount = useMemo(
    () => monthEmployeeStates.filter((row) => row.state.status !== 'success').length,
    [monthEmployeeStates]
  );

  const enqueueGeneration = useCallback(
    (months: number[]) => {
      if (!selectedEmployee || months.length === 0) return;
      const jobs = months.map((month) => ({
        employeeId: selectedEmployee.id,
        employeeName: employeeDisplayName(selectedEmployee),
        year: selectedYear,
        month,
      }));
      generation.generateJobs(jobs);
    },
    [selectedEmployee, selectedYear, generation]
  );

  const handleGenerateMonth = useCallback(
    (month: number) => enqueueGeneration([month]),
    [enqueueGeneration]
  );

  const handleGenerateYear = useCallback(() => {
    const missing = PAYROLL_MONTHS.filter((m) => monthStatuses[m]?.status !== 'success');
    enqueueGeneration(missing);
  }, [monthStatuses, enqueueGeneration]);

  const handleGenerateEmployeeForMonth = useCallback(
    (employeeId: string) => {
      const emp = employees.find((e) => e.id === employeeId);
      if (!emp) return;
      generation.generateJobs([
        {
          employeeId: emp.id,
          employeeName: employeeDisplayName(emp),
          year: selectedYear,
          month: selectedMonth,
        },
      ]);
    },
    [employees, selectedYear, selectedMonth, generation]
  );

  const handleGenerateWholeMonth = useCallback(() => {
    const jobs = monthEmployeeStates
      .filter((row) => row.state.status !== 'success')
      .map((row) => ({
        employeeId: row.employee.id,
        employeeName: employeeDisplayName(row.employee),
        year: selectedYear,
        month: selectedMonth,
      }));
    if (jobs.length === 0) return;
    generation.generateJobs(jobs);
  }, [monthEmployeeStates, selectedYear, selectedMonth, generation]);

  const handleDeletePayslip = useCallback(
    async (payslipId: string, employeeId?: string) => {
      const targetEmployeeId = employeeId ?? selectedEmployeeId;
      if (!targetEmployeeId) return;
      setDeletingPayslipId(payslipId);
      try {
        await deletePayslip(payslipId);
        await queryClient.invalidateQueries({
          queryKey: queryKeys.employeePayslips(companyId, targetEmployeeId),
        });
      } catch (error) {
        showErrorToast(error, {
          title: 'Suppression impossible',
          fallback: 'La suppression du bulletin a échoué.',
        });
      } finally {
        setDeletingPayslipId(null);
      }
    },
    [companyId, queryClient, selectedEmployeeId]
  );

  const missingMonthsCount = useMemo(
    () => PAYROLL_MONTHS.filter((m) => monthStatuses[m]?.status !== 'success').length,
    [monthStatuses]
  );

  const monthYearOptions = useMemo(() => {
    const years = employees.flatMap((emp) => (payslipsByEmployee[emp.id] ?? []).map((p) => p.year));
    return buildYearOptions(years, selectedYear);
  }, [employees, payslipsByEmployee, selectedYear]);

  const loadingEmployees = employeesQuery.isLoading && employees.length === 0;
  const loadingPayslipsInitial =
    Boolean(selectedEmployeeId) &&
    payslipsQuery.isLoading &&
    payslipsQuery.data === undefined;
  const loadingMonthData =
    employees.length === 0
      ? loadingEmployees
      : payslipQueries.some((q) => q.isLoading && q.data === undefined);
  const error = employeesQuery.error
    ? 'Impossible de charger la liste des collaborateurs. Réessayez.'
    : null;

  const progressSlot =
    generation.phase !== 'idle' ? (
      <PayrollProgressBar
        phase={generation.phase}
        progress={generation.progress}
        currentLabel={generation.currentLabel}
        estimatedRemainingSec={generation.estimatedRemainingSec}
        log={generation.log}
        totalJobs={generation.totalJobs}
        completedCount={generation.completedCount}
        onDismiss={generation.dismiss}
        onCancel={generation.cancel}
      />
    ) : null;

  return (
    <div className="space-y-6">
      <PageFetchIndicator isFetching={employeesQuery.isFetching || payslipsQuery.isFetching} />
      <RhPageHeader
        title="Gestion de la Paie"
        description="Générez et consultez les bulletins par collaborateur ou par mois."
      />

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="space-y-3">
        <PayrollGroupLaunchCta />

        <Tabs value={view} onValueChange={(v) => handleViewChange(v as PayrollView)}>
          <TabsList className="w-full sm:w-auto">
            <TabsTrigger value="employee" className="flex-1 sm:flex-none">
              Par collaborateur
            </TabsTrigger>
            <TabsTrigger value="month" className="flex-1 sm:flex-none">
              Par mois
            </TabsTrigger>
          </TabsList>

          <TabsContent value="employee" className="mt-3">
            <PayrollEmployeeExplorer
              employees={employees}
              selectedEmployeeId={selectedEmployeeId}
              onSelectEmployee={selectEmployee}
              yearCounts={yearCounts}
              selectedYear={selectedYear}
              yearOptions={yearOptions}
              onYearChange={setSelectedYear}
              missingMonthsCount={missingMonthsCount}
              onGenerateYear={handleGenerateYear}
              detailLoading={loadingPayslipsInitial}
              loadingEmployees={loadingEmployees}
              progressSlot={progressSlot}
              renderDetail={() =>
                selectedEmployee ? (
                  <PayrollMonthList
                    selectedYear={selectedYear}
                    monthStatuses={monthStatuses}
                    loadingPayslips={loadingPayslipsInitial}
                    onGenerateMonth={handleGenerateMonth}
                    onDeletePayslip={handleDeletePayslip}
                    deletingPayslipId={deletingPayslipId}
                  />
                ) : null
              }
            />
          </TabsContent>

          <TabsContent value="month" className="mt-3">
            <PayrollMonthExplorer
              selectedYear={selectedYear}
              yearOptions={monthYearOptions}
              onYearChange={setSelectedYear}
              selectedMonth={selectedMonth}
              onSelectMonth={setSelectedMonth}
              monthGeneratedCounts={monthGeneratedCounts}
              totalEmployees={employees.length}
              employeeStates={monthEmployeeStates}
              missingCount={monthMissingCount}
              onGenerateEmployee={handleGenerateEmployeeForMonth}
              onGenerateMonth={handleGenerateWholeMonth}
              onDeletePayslip={handleDeletePayslip}
              deletingPayslipId={deletingPayslipId}
              loadingEmployees={loadingEmployees}
              loadingPayslips={loadingMonthData}
              progressSlot={progressSlot}
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
