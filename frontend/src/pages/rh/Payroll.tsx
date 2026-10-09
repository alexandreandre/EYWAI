import { isPresentDuringMonth } from '@/lib/employmentStatus';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { RhPageHeader } from '@/components/layout';
import { PageFetchIndicator } from '@/components/skeletons/PageFetchIndicator';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { usePayrollEmployeesQuery, type EmployeeListItem } from '@/hooks/queries/useEmployeesQuery';
import { useEmployeePayslipsQuery } from '@/hooks/queries/useEmployeePayslipsQuery';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { deletePayslip, getEmployeePayslips, type PayslipInfo } from '@/api/payslips';
import { getExportHistory } from '@/api/exports';
import { queryKeys } from '@/lib/queryKeys';
import { showErrorToast } from '@/lib/errorMessages';
import { toast } from '@/hooks/use-toast';
import { PayrollEmployeeExplorer } from '@/features/payroll/components/PayrollEmployeeExplorer';
import {
  PayrollMonthExplorer,
  type EmployeeMonthState,
} from '@/features/payroll/components/PayrollMonthExplorer';
import { PayrollGroupLaunchCta } from '@/features/payroll/components/PayrollGroupLaunchCta';
import { PayrollMonthList, type MonthStatusMap } from '@/features/payroll/components/PayrollMonthList';
import type { PayslipRowState } from '@/features/payroll/components/PayrollPayslipRow';
import { GenerationEnCoursProvider } from '@/features/payroll/components/GenerationEnCoursContext';
import {
  libelleBandeauGeneration,
  lireInterruption,
  oublierInterruption,
  phraseInterruption,
} from '@/features/payroll/utils/generationEnCours';
import { PayrollProgressBar } from '@/features/payroll/components/PayrollProgressBar';
import { PayrollGenerationRefusalDialog } from '@/features/payroll/components/PayrollGenerationRefusalDialog';
import {
  usePayrollGeneration,
  type PayrollGenerationJob,
  type PayrollGenerationLogEntry,
} from '@/features/payroll/hooks/usePayrollGeneration';
import {
  buildYearOptions,
  monthYearLabel,
  PAYROLL_MONTHS,
} from '@/features/payroll/utils/payrollMonth';
import { payrollGenerationBlockReason } from '@/features/payroll/utils/employmentPeriod';
import { invaliderApresBulletin } from '@/features/payroll/utils/invalidationsBulletin';
import { messageDeSuppression } from '@/features/payroll/utils/suppressionBulletin';
import {
  jobsDesBulletinsPerimes,
  jobsDesLignesPerimes,
  montantsDepuisLigne,
  type LigneBulletinPaie,
} from '@/features/payroll/utils/bulletinARecalculer';
import { CreateEmployeeForm } from '@/features/employees/components/CreateEmployeeForm';
import { lireNouveauSalarie, salariesAvecNouveauEnTete } from '@/features/employees/utils/creationSalarie';
import { CreateExitDialog } from '@/components/exits/CreateExitDialog';
import { BandeauxSortieGuidee } from '@/features/payroll/components/BandeauxSortieGuidee';
import { useEmployeeExitsQuery } from '@/hooks/queries/useEmployeeExitsQuery';
import { bandeauxSortieDuMois, type BandeauSortieGuidee } from '@/features/payroll/utils/sortieGuidee';
import { ListeControleMois } from '@/features/payroll/components/ListeControleMois';
import { usePreflightAnomalies } from '@/features/payroll/hooks/usePreflightAnomaliesCount';
import {
  lectureCalendriersASaisir,
  lectureConflitsArret,
  listeControleDuMois,
  type ExportPourControle,
  type Lecture,
} from '@/features/payroll/utils/listeControleMois';
import {
  avecMois,
  avecRevue,
  lireParamsVuePaie,
  moisAffiche,
  type VuePaie,
} from '@/features/payroll/utils/vuePaieUrl';
import { estPretAValider } from '@/features/payroll/utils/validationGroupee';
import { ValiderBulletinsPrets } from '@/features/payroll/components/ValiderBulletinsPrets';
import {
  ecartAvecMoisPrecedent,
  estARevoir,
  libelleEcart,
  moisPrecedent,
  phraseSynthese,
  syntheseDuMois,
} from '@/features/payroll/utils/revueDuMois';

type PayrollView = VuePaie;

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
    const warnings = [
      ...(payslip.warnings ?? []),
      ...(logEntry?.status === 'warning' ? logEntry.warnings ?? [] : []),
    ];
    const uniqueWarnings = [...new Set(warnings.filter(Boolean))];
    return {
      status: 'success',
      payslip,
      warnings: uniqueWarnings.length > 0 ? uniqueWarnings : undefined,
    };
  }
  if (logEntry?.status === 'error' || persistedError) {
    return { status: 'error', errorMessage: logEntry?.error ?? persistedError };
  }
  return { status: 'idle' };
}

function buildMonthStatuses(
  payslipsForYear: PayslipInfo[],
  employee: EmployeeListItem,
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
    const state = buildRowState(payslip, employee.id, year, month, generation);
    const unavailableReason = payrollGenerationBlockReason(employee, year, month);
    map[month] =
      unavailableReason && state.status !== 'success' && state.status !== 'loading'
        ? { status: 'unavailable', errorMessage: unavailableReason }
        : state;
  }
  return map;
}

function canGeneratePayslip(state: PayslipRowState | undefined): boolean {
  return state?.status === 'idle' || state?.status === 'error';
}

export default function Payroll() {
  const [searchParams, setSearchParams] = useSearchParams();
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();

  const employeesQuery = usePayrollEmployeesQuery();
  const employeesTous = (employeesQuery.data ?? []) as EmployeeListItem[];

  const employeeFromUrl = searchParams.get('employee');
  const paramsVue = lireParamsVuePaie(searchParams);
  const view = paramsVue.view;
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(
    employeeFromUrl
  );
  // ?month=YYYY-MM : posé par « Voir les bulletins », par la liste de contrôle
  // et par le choix du mois. Relu à chaque changement d’URL. Sans lui, le mois
  // de paie (jusqu’au 15, le mois précédent), pas le mois civil.
  const [selectedYear, setSelectedYear] = useState(
    () => moisAffiche(paramsVue, new Date()).year
  );
  const [selectedMonth, setSelectedMonth] = useState(
    () => moisAffiche(paramsVue, new Date()).month
  );
  const aRevoirSeulement = paramsVue.aRevoir;
  // Un parti reste visible sur les mois où il était présent : toute l'année
  // en vue salarié, le mois choisi en vue mois (salarié 086, sorti le 24/07 :
  // bulletin de juin à consulter, juillet à générer — retour Gaëlle 12/09).
  const idNouveau = lireNouveauSalarie();
  const employees = useMemo(
    () =>
      salariesAvecNouveauEnTete(
        employeesTous.filter((e) =>
          view === 'month'
            ? isPresentDuringMonth(e, selectedYear, selectedMonth)
            : isPresentDuringMonth(e, selectedYear, 1)
        ),
      ),
    [employeesTous, view, selectedYear, selectedMonth, idNouveau]
  );
  const salariesDuMois = useMemo(
    () => employeesTous.filter((e) => isPresentDuringMonth(e, selectedYear, selectedMonth)),
    [employeesTous, selectedYear, selectedMonth]
  );
  const [deletingPayslipId, setDeletingPayslipId] = useState<string | null>(null);
  const [refusalDialogDismissed, setRefusalDialogDismissed] = useState(false);
  const [departACreer, setDepartACreer] = useState<BandeauSortieGuidee | null>(null);
  const [dialogDepartOuvert, setDialogDepartOuvert] = useState(false);

  const generation = usePayrollGeneration();
  // Génération interrompue par une page quittée : dite une fois au retour.
  const [interruption, setInterruption] = useState(() => {
    try {
      return lireInterruption(window.sessionStorage, companyId);
    } catch {
      return null;
    }
  });
  const oublierNoteInterruption = () => {
    try {
      oublierInterruption(window.sessionStorage);
    } catch {
      // Stockage indisponible : rien à effacer.
    }
    setInterruption(null);
  };
  const generationEnCours = generation.phase === 'running';
  const exitsQuery = useEmployeeExitsQuery(true);
  const preflightQuery = usePreflightAnomalies(selectedYear, selectedMonth);

  useEffect(() => () => generation.dismiss(), []); // eslint-disable-line react-hooks/exhaustive-deps

  // Une nouvelle passe de génération ré-arme le récapitulatif des refusés.
  useEffect(() => {
    if (generation.phase === 'running') {
      setRefusalDialogDismissed(false);
      oublierNoteInterruption();
    }
  }, [generation.phase]);

  useEffect(() => {
    if (employeeFromUrl) {
      setSelectedEmployeeId(employeeFromUrl);
    }
  }, [employeeFromUrl]);

  useEffect(() => {
    if (paramsVue.year != null) setSelectedYear(paramsVue.year);
    if (paramsVue.month != null) setSelectedMonth(paramsVue.month);
  }, [paramsVue.year, paramsVue.month]);

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

  // Le mois choisi va dans l’adresse : le retour d’un bulletin y revient.
  const choisirMois = useCallback(
    (year: number, month: number) => {
      setSelectedYear(year);
      setSelectedMonth(month);
      setSearchParams((prev) => avecMois(prev, year, month), { replace: true });
    },
    [setSearchParams]
  );

  const changerARevoir = useCallback(
    (actif: boolean) => {
      setSearchParams((prev) => avecRevue(prev, actif), { replace: true });
    },
    [setSearchParams]
  );

  const handleViewChange = useCallback(
    (next: PayrollView) => {
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
    if (!selectedEmployee) return {};
    return buildMonthStatuses(payslipsForYear, selectedEmployee, selectedYear, generationState);
  }, [selectedEmployee, payslipsForYear, selectedYear, generationState]);

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

  const precedent = useMemo(
    () => moisPrecedent(selectedYear, selectedMonth),
    [selectedYear, selectedMonth]
  );

  const monthEmployeeStates = useMemo<EmployeeMonthState[]>(() => {
    return employees.map((emp) => {
      const payslip = (payslipsByEmployee[emp.id] ?? []).find(
        (p) => p.year === selectedYear && p.month === selectedMonth
      );
      const payslipPrecedent = (payslipsByEmployee[emp.id] ?? []).find(
        (p) => p.year === precedent.year && p.month === precedent.month
      );
      const state = buildRowState(
        payslip,
        emp.id,
        selectedYear,
        selectedMonth,
        generationState
      );
      const unavailableReason = payrollGenerationBlockReason(
        emp,
        selectedYear,
        selectedMonth
      );
      const rowState: PayslipRowState =
        unavailableReason && state.status !== 'success' && state.status !== 'loading'
          ? { status: 'unavailable' as const, errorMessage: unavailableReason }
          : state;
      const ecart = payslip ? ecartAvecMoisPrecedent(payslip, payslipPrecedent) : null;
      return {
        employee: emp,
        state: rowState,
        payslipPrecedent,
        ecart: ecart
          ? {
              texte: libelleEcart(ecart, selectedYear, selectedMonth),
              fort: ecart.fort,
              raison: ecart.raison,
            }
          : null,
        aRevoir: estARevoir({
          statut: rowState.status,
          bulletin: rowState.payslip,
          alertes: rowState.warnings,
          ecart,
        }),
        pret: estPretAValider({
          statut: rowState.status,
          bulletin: rowState.payslip,
          alertes: rowState.warnings,
          ecart,
        }),
      };
    });
  }, [employees, payslipsByEmployee, selectedYear, selectedMonth, precedent, generationState]);

  const syntheseMois = useMemo(
    () =>
      phraseSynthese(
        syntheseDuMois(
          monthEmployeeStates.map((row) => ({
            statut: row.state.status,
            bulletin: row.state.payslip,
            bulletinPrecedent: row.payslipPrecedent,
          }))
        ),
        selectedYear,
        selectedMonth
      ),
    [monthEmployeeStates, selectedYear, selectedMonth]
  );

  const idsPretsAValider = useMemo(
    () =>
      monthEmployeeStates
        .filter((row) => row.pret && row.state.payslip)
        .map((row) => row.state.payslip!.id),
    [monthEmployeeStates]
  );
  const nomParBulletin = useMemo(() => {
    const noms: Record<string, string> = {};
    for (const row of monthEmployeeStates) {
      if (row.state.payslip) noms[row.state.payslip.id] = employeeDisplayName(row.employee);
    }
    return noms;
  }, [monthEmployeeStates]);

  const monthMissingCount = useMemo(
    () => monthEmployeeStates.filter((row) => canGeneratePayslip(row.state)).length,
    [monthEmployeeStates]
  );

  const bandeauxSortie = useMemo(() => {
    if (view !== 'month') return [];
    if (exitsQuery.isLoading && exitsQuery.data === undefined) return [];
    // Bulletins pas encore lus : on ne sait pas qui a déjà son bulletin de
    // sortie, et un bandeau « générez-le » cliquable serait faux (recette 02/10).
    if (payslipQueries.some((q) => q.isLoading && q.data === undefined)) return [];
    const idsAvecBulletin = new Set(
      employees
        .filter((emp) =>
          (payslipsByEmployee[emp.id] ?? []).some(
            (p) => p.year === selectedYear && p.month === selectedMonth
          )
        )
        .map((emp) => emp.id)
    );
    return bandeauxSortieDuMois(
      employees,
      exitsQuery.data ?? [],
      selectedYear,
      selectedMonth,
      idsAvecBulletin
    );
  }, [
    view,
    employees,
    exitsQuery.isLoading,
    exitsQuery.data,
    payslipQueries,
    payslipsByEmployee,
    selectedYear,
    selectedMonth,
  ]);

  const enqueueGeneration = useCallback(
    (months: number[]) => {
      if (!selectedEmployee || months.length === 0) return;
      const jobs = months.map((month) => {
        const payslip = payslipsForYear.find((p) => p.month === month);
        return {
          employeeId: selectedEmployee.id,
          employeeName: employeeDisplayName(selectedEmployee),
          year: selectedYear,
          month,
          ...(payslip ? { montantsAvant: montantsDepuisLigne(payslip) } : {}),
        };
      });
      generation.generateJobs(jobs);
    },
    [selectedEmployee, selectedYear, payslipsForYear, generation]
  );

  const handleGenerateMonth = useCallback(
    (month: number) => enqueueGeneration([month]),
    [enqueueGeneration]
  );

  const handleGenerateYear = useCallback(() => {
    const missing = PAYROLL_MONTHS.filter((m) => canGeneratePayslip(monthStatuses[m]));
    enqueueGeneration(missing);
  }, [monthStatuses, enqueueGeneration]);

  const handleGenerateEmployeeForMonth = useCallback(
    (employeeId: string) => {
      const emp = employees.find((e) => e.id === employeeId);
      if (!emp) return;
      if (payrollGenerationBlockReason(emp, selectedYear, selectedMonth)) return;
      const payslip = (payslipsByEmployee[emp.id] ?? []).find(
        (p) => p.year === selectedYear && p.month === selectedMonth
      );
      generation.generateJobs([
        {
          employeeId: emp.id,
          employeeName: employeeDisplayName(emp),
          year: selectedYear,
          month: selectedMonth,
          ...(payslip ? { montantsAvant: montantsDepuisLigne(payslip) } : {}),
        },
      ]);
    },
    [employees, payslipsByEmployee, selectedYear, selectedMonth, generation]
  );

  const handleGenerateWholeMonth = useCallback(() => {
    const jobs = monthEmployeeStates
      .filter((row) => canGeneratePayslip(row.state))
      .map((row) => ({
        employeeId: row.employee.id,
        employeeName: employeeDisplayName(row.employee),
        year: selectedYear,
        month: selectedMonth,
      }));
    if (jobs.length === 0) return;
    generation.generateJobs(jobs);
  }, [monthEmployeeStates, selectedYear, selectedMonth, generation]);

  const jobsPerimesDuMois = useMemo(
    () => jobsDesBulletinsPerimes(employees, payslipsByEmployee, selectedYear, selectedMonth),
    [employees, payslipsByEmployee, selectedYear, selectedMonth]
  );

  const jobsPerimesDuSalarie = useMemo(
    () =>
      selectedEmployee
        ? jobsDesLignesPerimes(selectedEmployee, payslipsForYear)
        : [],
    [selectedEmployee, payslipsForYear]
  );

  const handleRecalculerPerimesMois = useCallback(() => {
    if (jobsPerimesDuMois.length === 0) return;
    generation.generateJobs(jobsPerimesDuMois);
  }, [jobsPerimesDuMois, generation]);

  const handleRecalculerPerimesSalarie = useCallback(() => {
    if (jobsPerimesDuSalarie.length === 0) return;
    generation.generateJobs(jobsPerimesDuSalarie);
  }, [jobsPerimesDuSalarie, generation]);

  const handleDeletePayslip = useCallback(
    async (payslipId: string, employeeId?: string) => {
      const targetEmployeeId = employeeId ?? selectedEmployeeId;
      if (!targetEmployeeId) return;
      setDeletingPayslipId(payslipId);
      let resultat: { dejaSupprime: boolean } | null = null;
      try {
        resultat = await deletePayslip(payslipId, companyId);
      } catch (error) {
        showErrorToast(error, {
          title: 'Suppression impossible',
          fallback: 'La suppression du bulletin a échoué.',
        });
      } finally {
        // Même en échec : le bulletin a pu changer depuis un autre écran.
        await invaliderApresBulletin(queryClient, companyId, targetEmployeeId);
        setDeletingPayslipId(null);
      }
      if (resultat) toast(messageDeSuppression(resultat));
    },
    [companyId, queryClient, selectedEmployeeId]
  );

  const missingMonthsCount = useMemo(
    () => PAYROLL_MONTHS.filter((m) => canGeneratePayslip(monthStatuses[m])).length,
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

  const lectureBulletins = useMemo((): Lecture<Record<string, LigneBulletinPaie[]>> => {
    if (loadingMonthData) return { statut: 'chargement' };
    const map: Record<string, LigneBulletinPaie[]> = {};
    for (const emp of salariesDuMois) {
      map[emp.id] = payslipsByEmployee[emp.id] ?? [];
    }
    return { statut: 'ok', valeur: map };
  }, [loadingMonthData, salariesDuMois, payslipsByEmployee]);

  const lectureDeparts = useMemo((): Lecture<NonNullable<typeof exitsQuery.data>> => {
    if (exitsQuery.isError && exitsQuery.data === undefined) return { statut: 'erreur' };
    if (exitsQuery.isLoading && exitsQuery.data === undefined) return { statut: 'chargement' };
    return { statut: 'ok', valeur: exitsQuery.data ?? [] };
  }, [exitsQuery.isError, exitsQuery.isLoading, exitsQuery.data]);

  const lectureCalendriers = lectureCalendriersASaisir({
    chargement: preflightQuery.isLoading,
    erreur: Boolean(preflightQuery.isError),
    anomalies: preflightQuery.data?.anomalies,
  });
  const lectureConflits = lectureConflitsArret({
    chargement: preflightQuery.isLoading,
    erreur: Boolean(preflightQuery.isError),
    heures_sur_arret: preflightQuery.data?.heures_sur_arret,
  });

  // Exports du mois (DSN, comptabilité) : la dernière étape de la liste de contrôle.
  const periodeExports = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}`;
  const exportsDuMoisQuery = useQuery({
    queryKey: ['export-history', companyId, 'mois', periodeExports],
    queryFn: () => getExportHistory(undefined, periodeExports),
    enabled: Boolean(companyId),
    staleTime: 30_000,
  });
  const lectureExports = useMemo((): Lecture<readonly ExportPourControle[]> => {
    if (exportsDuMoisQuery.isError && exportsDuMoisQuery.data === undefined) return { statut: 'erreur' };
    if (exportsDuMoisQuery.data === undefined) return { statut: 'chargement' };
    return { statut: 'ok', valeur: exportsDuMoisQuery.data.exports ?? [] };
  }, [exportsDuMoisQuery.isError, exportsDuMoisQuery.data]);

  const lectureSalaries = useMemo((): Lecture<typeof salariesDuMois> => {
    if (employeesQuery.isError && employeesQuery.data === undefined) return { statut: 'erreur' };
    if (loadingEmployees) return { statut: 'chargement' };
    return { statut: 'ok', valeur: salariesDuMois };
  }, [employeesQuery.isError, employeesQuery.data, loadingEmployees, salariesDuMois]);

  const listeControle = useMemo(() => {
    if (loadingEmployees) return null;
    return listeControleDuMois({
      year: selectedYear,
      month: selectedMonth,
      salaries: salariesDuMois,
      lectureSalaries,
      bulletinsParSalarie: lectureBulletins,
      departs: lectureDeparts,
      calendriersASaisir: lectureCalendriers,
      conflitsArret: lectureConflits,
      exportsDuMois: lectureExports,
    });
  }, [
    loadingEmployees,
    selectedYear,
    selectedMonth,
    salariesDuMois,
    lectureSalaries,
    lectureBulletins,
    lectureDeparts,
    lectureCalendriers,
    lectureConflits,
    lectureExports,
  ]);

  const generatedCount = useMemo(
    () =>
      generation.log.filter(
        (entry) => entry.status === 'success' || entry.status === 'warning'
      ).length,
    [generation.log]
  );

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
        arretDemande={generation.arretDemande}
      />
    ) : null;

  return (
    <GenerationEnCoursProvider value={generationEnCours}>
    <div className="space-y-6">
      <PageFetchIndicator isFetching={employeesQuery.isFetching || payslipsQuery.isFetching} />
      <RhPageHeader
        title="Gestion de la Paie"
        description="Générez et consultez les bulletins par collaborateur ou par mois."
        actions={<CreateEmployeeForm />}
      />

      {generationEnCours && (
        <div
          role="status"
          data-testid="bandeau-generation"
          className="rounded-md border border-sky-200 bg-sky-50 px-4 py-3 text-sm font-medium text-sky-900"
        >
          {libelleBandeauGeneration(generation.completedCount, generation.totalJobs)}
        </div>
      )}

      {!generationEnCours && interruption && (
        <div
          role="alert"
          data-testid="bandeau-interruption"
          className="flex items-start justify-between gap-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
        >
          <span>{phraseInterruption(interruption)}</span>
          <button type="button" className="underline" onClick={oublierNoteInterruption}>
            Compris
          </button>
        </div>
      )}

      {!generationEnCours && generation.recapEchecs.length > 0 && (
        <div
          role="alert"
          data-testid="recap-echecs-generation"
          className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
        >
          <div className="flex items-start justify-between gap-3">
            <p className="font-medium">
              {generation.recapEchecs.length} bulletin{generation.recapEchecs.length > 1 ? 's' : ''} non généré
              {generation.recapEchecs.length > 1 ? 's' : ''} à la dernière génération
            </p>
            <button type="button" className="underline" onClick={generation.oublierEchecs}>
              Masquer
            </button>
          </div>
          <ul className="mt-1 list-disc pl-5">
            {generation.recapEchecs.map((echec) => (
              <li key={echec.cle}>
                {echec.nom} ({echec.mois}) : {echec.raison}
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <ListeControleMois
        titreMois={monthYearLabel(selectedMonth, selectedYear)}
        liste={listeControle}
        chargement={loadingEmployees}
        preflightEnErreur={Boolean(preflightQuery.isError)}
        onRetryPreflight={() => {
          void preflightQuery.refetch();
        }}
        isRetrying={preflightQuery.isFetching}
      />

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
              onYearChange={(year) => choisirMois(year, selectedMonth)}
              missingMonthsCount={missingMonthsCount}
              onGenerateYear={handleGenerateYear}
              perimesCount={jobsPerimesDuSalarie.length}
              onRecalculerPerimes={handleRecalculerPerimesSalarie}
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

          <TabsContent value="month" className="mt-3 space-y-3">
            <BandeauxSortieGuidee
              bandeaux={bandeauxSortie}
              onCreerLeDepart={(bandeau) => {
                setDepartACreer(bandeau);
                setDialogDepartOuvert(true);
              }}
              onGenererBulletin={handleGenerateEmployeeForMonth}
            />
            <PayrollMonthExplorer
              selectedYear={selectedYear}
              yearOptions={monthYearOptions}
              onYearChange={(year) => choisirMois(year, selectedMonth)}
              selectedMonth={selectedMonth}
              onSelectMonth={(month) => choisirMois(selectedYear, month)}
              monthGeneratedCounts={monthGeneratedCounts}
              totalEmployees={employees.length}
              employeeStates={monthEmployeeStates}
              missingCount={monthMissingCount}
              onGenerateEmployee={handleGenerateEmployeeForMonth}
              onGenerateMonth={handleGenerateWholeMonth}
              perimesCount={jobsPerimesDuMois.length}
              onRecalculerPerimes={handleRecalculerPerimesMois}
              onDeletePayslip={handleDeletePayslip}
              deletingPayslipId={deletingPayslipId}
              loadingEmployees={loadingEmployees}
              loadingPayslips={loadingMonthData}
              progressSlot={progressSlot}
              synthese={loadingMonthData ? undefined : syntheseMois}
              aRevoirSeulement={aRevoirSeulement}
              onARevoirChange={changerARevoir}
              actionValider={
                <ValiderBulletinsPrets
                  idsPrets={loadingMonthData ? [] : idsPretsAValider}
                  nomParBulletin={nomParBulletin}
                  companyId={companyId}
                  titreMois={monthYearLabel(selectedMonth, selectedYear)}
                  disabled={generation.phase === 'running'}
                  onTermine={() => invaliderApresBulletin(queryClient, companyId, undefined)}
                />
              }
            />
          </TabsContent>
        </Tabs>
      </div>

      <CreateExitDialog
        open={dialogDepartOuvert}
        onOpenChange={(open) => {
          setDialogDepartOuvert(open);
          if (!open) setDepartACreer(null);
        }}
        initialEmployeeId={departACreer?.employeeId}
        initialExitType={departACreer?.motifPropose ?? undefined}
        initialLastWorkingDay={departACreer?.dateIso}
      />

      <PayrollGenerationRefusalDialog
        open={
          generation.phase === 'done' &&
          generation.refusedJobs.length > 0 &&
          !refusalDialogDismissed
        }
        refusals={generation.refusedJobs}
        generatedCount={generatedCount}
        onForce={generation.forceRefused}
        onRetry={generation.retryJob}
        onDismiss={() => setRefusalDialogDismissed(true)}
      />
    </div>
    </GenerationEnCoursProvider>
  );
}
