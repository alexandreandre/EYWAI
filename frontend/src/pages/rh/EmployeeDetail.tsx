// src/pages/EmployeeDetail.tsx

import { log } from '@/lib/logger';
import { lazy, Suspense, useCallback, useState, useEffect, useRef, useMemo } from "react";
import { useParams, Link, useNavigate, useLocation } from "react-router-dom";
import { updateEmployee } from "@/api/employees";
import apiClient from "@/api/apiClient";
import { EmployeeOnboardingCompletion } from "@/features/employee-detail/components/EmployeeOnboardingCompletion";
import { EmployeeProfileEditDialog } from "@/features/employee-detail/components/EmployeeProfileEditDialog";
import { isProfileIncomplete } from "@/features/employee-detail/components/employeeProfileFormUtils";
import * as saisiesApi from "@/api/saisies";
import { useCalendar } from "@/hooks/useCalendar";
import { toast } from "@/components/ui/use-toast";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, ArrowLeft, ClipboardEdit, MessageSquare, Calendar as CalendarIcon, FileText, TrendingUp, Stethoscope, ScanLine } from "lucide-react";
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { EmployeeDetailBadgeuseSection } from "@/components/badgeuse/rh/EmployeeDetailBadgeuseSection";
import { getEmployeeDaysSummary } from "@/api/badgeuse";
import { periodRangeLastDays } from "@/lib/badgeuseApiUtils";
import { EmployeeDetailHeaderCard } from "@/components/employee-detail/EmployeeDetailHeaderCard";
import { EmployeeDetailTrialPeriodCard } from "@/components/employee-detail/EmployeeDetailTrialPeriodCard";
import {
  EmployeeDetailAnnualReviewsTab,
  annualReviewsEmployeeQueryKey,
} from "@/components/employee-detail/EmployeeDetailAnnualReviewsTab";
import { getEmployeeAnnualReviews } from "@/api/annualReviews";
import { hasAnnualReviewTabAlert } from "@/lib/annualReviewLabels";
import * as collectiveAgreementsApi from "@/api/collectiveAgreements";
import { EmployeeCSEBlock } from "@/components/EmployeeCSEBlock";
import {
  EmployeeDetailMedicalTab,
  medicalEmployeeQueryKey,
} from "@/components/employee-detail/EmployeeDetailMedicalTab";
import { hasMedicalOverdue } from "@/lib/medicalFollowUpLabels";
import { getMedicalSettings, getObligationsForEmployee } from "@/api/medicalFollowUp";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { assignEmployeeTeam, getTeams } from "@/api/teams";
import { EmployeeDetailDocumentsTab } from "@/components/employee-detail/EmployeeDetailDocumentsTab";
import { EmployeeBoethCard } from "@/features/employee-detail/components/EmployeeBoethCard";
import { EmployeePasSettingsCard } from "@/features/employee-detail/components/EmployeePasSettingsCard";
import {
  diffWatchedSnapshots,
  extractWatchedSnapshot,
  resolveAvenantTypeFromDiffs,
  type ContractualFieldDiff,
} from "@/utils/employeeContractualWatch";
import { useCompany } from "@/contexts/CompanyContext";
import { useAuth } from "@/contexts/AuthContext";
import { SaisieModal } from "@/components/SaisieModal";
import { cn } from "@/lib/utils";
import {
  resolveDefaultCollectiveAgreementId,
  sortAffiliatedCompanyAgreements,
} from '@/lib/companyCollectiveAgreementUtils';
import { TAB_AUGMENTATIONS_PROMOTIONS, normalizeEmployeeDetailTab } from "@/features/employee-detail/utils/tabs";
import type { Employee } from "@/features/employee-detail/types";
import { EmployeeDetailSaisiesTab } from "@/features/employee-detail/components/EmployeeDetailSaisiesTab";
import { WorkMedalEmployeeSection } from "@/features/work-medals/components/WorkMedalEmployeeSection";
import { EmployeeLoansCard } from "@/features/employee-detail/components/EmployeeLoansCard";
import { ContractualChangeDialog } from "@/features/employee-detail/components/ContractualChangeDialog";
import {
  employeePlaceholderFromList,
  type EmployeeDetailLocationState,
} from "@/features/employees/utils/employeePreview";
import { useEmployeeQuery, useUpdateEmployeeCache } from "@/hooks/queries/useEmployeeQuery";
import { queryKeys } from "@/lib/queryKeys";
import { Skeleton } from "@/components/ui/skeleton";

const EmployeeDetailAugmentationsPromotionsTab = lazy(() =>
  import("@/features/employee-detail/components/EmployeeDetailAugmentationsPromotionsTab").then(
    (m) => ({ default: m.EmployeeDetailAugmentationsPromotionsTab }),
  ),
);
const EmployeeDetailCalendarTab = lazy(() =>
  import("@/features/employee-detail/components/EmployeeDetailCalendarTab").then(
    (m) => ({ default: m.EmployeeDetailCalendarTab }),
  ),
);

function TabPanelSkeleton() {
  return (
    <div className="space-y-3 rounded-lg border p-4">
      <Skeleton className="h-6 w-48" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}

export default function EmployeeDetail() {
  const { employeeId } = useParams<{ employeeId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const previewFromState = (location.state as EmployeeDetailLocationState | null)?.employeePreview;
  const employeePreview =
    previewFromState?.id === employeeId
      ? employeePlaceholderFromList(previewFromState)
      : undefined;

  const employeeQuery = useEmployeeQuery(employeeId, { placeholder: employeePreview });
  const employee = employeeQuery.data ?? null;
  const employeeReady = Boolean(employee && !employeeQuery.isPlaceholderData);
  const updateEmployeeCache = useUpdateEmployeeCache();
  const employeeStatut = employee?.statut;
  const [activeTab, setActiveTab] = useState<string>(() => {
    const params = new URLSearchParams(location.search);
    return normalizeEmployeeDetailTab(params.get("tab"));
  });
  const [profileEditOpen, setProfileEditOpen] = useState(false);

  const {
    selectedDate,
    setSelectedDate,
    plannedCalendar,
    actualHours,
    isLoading: isCalendarLoading,
    isSaving,
    saveAllCalendarData,
    updateDayData,
    weekTemplate,
    setWeekTemplate,
    applyWeekTemplate,
    selectedDays,
    handleDaySelection,
    bulkUpdateDays,
    isDirty,
    applyWeekTemplateAndSave,
    bulkUpdateDaysAndSave,
    updateSelection,
    isForfaitJour,
    monthCompletionStatus,
    copyPreviousMonthPlanned,
    copyPlannedToActualForDay,
    bulkCopyPlannedToActual,
    isCopyingPrevMonth,
    refetch: refetchCalendar,
  } = useCalendar(employeeId, employeeStatut, { enabled: activeTab === "calendrier" });

  const [saisieModalOpen, setSaisieModalOpen] = useState(false);
  const [isLoadingSaisies, setIsLoadingSaisies] = useState(false);
  const [employeeSaisies, setEmployeeSaisies] = useState<any[]>([]);
  const [calendarView, setCalendarView] = useState<'month' | 'year'>('month');

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    setActiveTab(normalizeEmployeeDetailTab(params.get("tab")));
  }, [employeeId, location.search]);

  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? "";
  const { user } = useAuth();
  const showEmployeeCSEBlock =
    user?.role === "rh" || user?.role === "admin" || user?.role === "collaborateur_rh";
  const canEditEmployeePaySettings =
    user?.role === "rh" || user?.role === "admin" || user?.role === "collaborateur_rh";
  const canDeleteReview =
    user?.role === "rh" || user?.role === "admin" || user?.role === "collaborateur_rh";

  const [collectiveAgreementId, setCollectiveAgreementId] = useState<string | null>(null);
  const [isSavingCC, setIsSavingCC] = useState(false);
  const [draftTeamId, setDraftTeamId] = useState<string>("__none__");
  const [savingTeam, setSavingTeam] = useState(false);

  const teamsActiveQuery = useQuery({
    queryKey: ["teams-active"],
    queryFn: () => getTeams(false),
    enabled: Boolean(employeeId && employeeReady),
    staleTime: 5 * 60_000,
  });
  const activeTeamsSorted = useMemo(
    () =>
      [...(teamsActiveQuery.data?.teams ?? [])].sort((a, b) =>
        a.name.localeCompare(b.name, "fr", { sensitivity: "base" }),
      ),
    [teamsActiveQuery.data?.teams],
  );
  const queryClient = useQueryClient();
  const contractualBaselineSeededRef = useRef(false);
  const contractualInitialWatchRef = useRef<ReturnType<typeof extractWatchedSnapshot> | null>(null);
  const [contractualOpen, setContractualOpen] = useState(false);
  const [contractualDiffs, setContractualDiffs] = useState<ContractualFieldDiff[]>([]);
  const [contractualAvenantType, setContractualAvenantType] = useState("avenant_general");
  const [contractualTemplate, setContractualTemplate] = useState("__eywai__");
  const [contractualDateEffet, setContractualDateEffet] = useState("");
  const [contractualMotifExtra, setContractualMotifExtra] = useState("");

  useEffect(() => {
    contractualBaselineSeededRef.current = false;
    contractualInitialWatchRef.current = null;
  }, [employeeId]);

  useEffect(() => {
    if (employee?.team_id) setDraftTeamId(employee.team_id);
    else setDraftTeamId("__none__");
  }, [employee?.team_id]);

  const savedTeamSelectValue = employee?.team_id ? employee.team_id : "__none__";
  const teamAssignmentDirty = draftTeamId !== savedTeamSelectValue;

  useEffect(() => {
    if (!employeeReady || contractualBaselineSeededRef.current) return;
    contractualInitialWatchRef.current = extractWatchedSnapshot(
      employee as unknown as Record<string, unknown>,
    );
    contractualBaselineSeededRef.current = true;
  }, [employee, employeeId, employeeReady]);

  const resetContractualBaselineFromEmployee = useCallback((emp: Employee) => {
    contractualInitialWatchRef.current = extractWatchedSnapshot(
      emp as unknown as Record<string, unknown>,
    );
  }, []);

  const evaluateContractualAfterPersist = useCallback((nextEmployee: Employee) => {
    if (!contractualInitialWatchRef.current) return;
    const cur = extractWatchedSnapshot(nextEmployee as unknown as Record<string, unknown>);
    const diffs = diffWatchedSnapshots(contractualInitialWatchRef.current, cur);
    if (diffs.length === 0) return;
    setContractualDiffs(diffs);
    setContractualAvenantType(resolveAvenantTypeFromDiffs(diffs));
    setContractualTemplate("__eywai__");
    setContractualDateEffet("");
    setContractualMotifExtra("");
    setContractualOpen(true);
  }, []);

  const medicalSettingsQuery = useQuery({
    queryKey: queryKeys.medicalSettings(activeCompanyId),
    queryFn: getMedicalSettings,
    enabled: Boolean(activeCompanyId),
    staleTime: 5 * 60_000,
  });
  const medicalModuleEnabled = medicalSettingsQuery.data?.enabled === true;

  const medicalTabBadgeQuery = useQuery({
    queryKey: employeeId ? medicalEmployeeQueryKey(employeeId) : ["medical-follow-up", "employee", "none"],
    queryFn: () => getObligationsForEmployee(employeeId!),
    enabled: medicalModuleEnabled && !!employeeId && employeeReady,
    staleTime: 60_000,
  });
  const medicalTabHasOverdue = hasMedicalOverdue(medicalTabBadgeQuery.data ?? []);

  const annualReviewsTabBadgeQuery = useQuery({
    queryKey: employeeId ? annualReviewsEmployeeQueryKey(employeeId) : ["annual-reviews", "employee", "none"],
    queryFn: async () => {
      const res = await getEmployeeAnnualReviews(employeeId!);
      return res.data ?? [];
    },
    enabled: !!employeeId && employeeReady,
    staleTime: 60_000,
  });
  const annualReviewTabHasAlert = hasAnnualReviewTabAlert(annualReviewsTabBadgeQuery.data ?? []);

  const badgeuseWeekRange = useMemo(() => periodRangeLastDays(7), []);
  const badgeuseTabBadgeQuery = useQuery({
    queryKey: [
      "badgeuse",
      "employee-days",
      activeCompanyId,
      employeeId,
      badgeuseWeekRange.from,
      badgeuseWeekRange.to,
      "tab-badge",
    ],
    queryFn: () =>
      getEmployeeDaysSummary(
        employeeId!,
        activeCompanyId,
        badgeuseWeekRange.from,
        badgeuseWeekRange.to
      ),
    enabled: Boolean(employeeId && activeCompanyId && !isForfaitJour && employeeReady),
    staleTime: 60_000,
  });
  const badgeuseTabHasAnomaly = (badgeuseTabBadgeQuery.data ?? []).some((d) => d.has_anomalies);

  const refreshEmployeeSnapshot = useCallback(async () => {
    if (!employeeId) return;
    const employeeRes = await apiClient.get<Employee>(`/api/employees/${employeeId}`);
    updateEmployeeCache(employeeId, employeeRes.data);
    evaluateContractualAfterPersist(employeeRes.data);
  }, [employeeId, evaluateContractualAfterPersist, updateEmployeeCache]);

  const companyAgreementsQuery = useQuery({
    queryKey: queryKeys.collectiveAgreements(activeCompanyId),
    queryFn: async () => {
      const res = await collectiveAgreementsApi.getMyCompanyAgreements();
      return res.data ?? [];
    },
    enabled: Boolean(activeCompanyId && employeeReady),
    staleTime: 5 * 60_000,
  });
  const companyAgreementsRaw = companyAgreementsQuery.data ?? [];
  const companyAgreements = useMemo(
    () => sortAffiliatedCompanyAgreements(companyAgreementsRaw),
    [companyAgreementsRaw],
  );

  useEffect(() => {
    if (employee?.collective_agreement_id === undefined) return;
    const resolved = resolveDefaultCollectiveAgreementId(
      companyAgreementsRaw,
      employee.collective_agreement_id,
    );
    setCollectiveAgreementId(resolved);
  }, [employee?.collective_agreement_id, companyAgreementsRaw]);

  const handleSaveCollectiveAgreement = async () => {
    if (!employeeId) return;
    setIsSavingCC(true);
    try {
      const updated = await updateEmployee(employeeId, {
        collective_agreement_id: collectiveAgreementId,
      });
      toast({ title: "Enregistré", description: "Convention collective mise à jour." });
      updateEmployeeCache(employeeId, updated);
      evaluateContractualAfterPersist(updated);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erreur";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    } finally {
      setIsSavingCC(false);
    }
  };

  const fetchSaisies = useCallback(async () => {
    if (!employeeId) return;
    const { year, month } = selectedDate;
    setIsLoadingSaisies(true);
    try {
      const res = await saisiesApi.getEmployeeMonthlyInputs(employeeId, year, month);
      setEmployeeSaisies(res.data || []);
    } catch (err) {
      log.error("❌ Erreur lors du chargement des saisies :", err);
    } finally {
      setIsLoadingSaisies(false);
    }
  }, [employeeId, selectedDate.year, selectedDate.month]);

  const handleDeleteSaisie = async (id: string) => {
    if (!window.confirm("Supprimer cette saisie ?")) return;
    try {
      await saisiesApi.deleteEmployeeMonthlyInput(employeeId!, id);
      toast({ title: "Supprimée", description: "La saisie a été supprimée." });
      fetchSaisies();
    } catch {
      toast({ title: "Erreur", description: "Impossible de supprimer la saisie.", variant: "destructive" });
    }
  };

  useEffect(() => {
    if (!employeeId || activeTab !== "saisie") return;
    fetchSaisies();
  }, [fetchSaisies, employeeId, activeTab]);

  const credentialsPdfQuery = useQuery({
    queryKey: ["employee", employeeId, "credentials-pdf"],
    queryFn: async () => {
      const res = await apiClient.get<{ url?: string | null }>(
        `/api/employees/${employeeId}/credentials-pdf`,
      );
      return res.data.url ?? null;
    },
    enabled: Boolean(employeeId),
    retry: false,
    staleTime: 5 * 60_000,
  });
  const credentialsPdfUrl = credentialsPdfQuery.data ?? null;

  const handleDeleteEmployee = async () => {
    if (!employeeId) return;
    try {
      await apiClient.delete(`/api/employees/${employeeId}`);
      toast({
        title: "Collaborateur supprimé",
        description: "Le collaborateur et son compte utilisateur ont été supprimés avec succès.",
      });
      navigate("/employees");
    } catch (error: unknown) {
      if (import.meta.env.DEV) {
        log.error("Erreur lors de la suppression du collaborateur", error);
      }
      const errorMessage =
        error && typeof error === "object" && "response" in error
          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Erreur de suppression",
        description:
          typeof errorMessage === "string" && errorMessage
            ? errorMessage
            : "Une erreur est survenue.",
        variant: "destructive",
      });
    }
  };

  const handleSaveTeamAssignment = async () => {
    if (!employeeId) return;
    setSavingTeam(true);
    try {
      const nextId = draftTeamId === "__none__" ? null : draftTeamId;
      await assignEmployeeTeam(employeeId, nextId);
      if (employee) {
        updateEmployeeCache(employeeId, { ...employee, team_id: nextId });
      }
      const employeeRes = await apiClient.get<Employee>(`/api/employees/${employeeId}`);
      updateEmployeeCache(employeeId, employeeRes.data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.employee(activeCompanyId, employeeId) });
      toast({ title: "Équipe mise à jour" });
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      toast({
        title: "Erreur",
        description: err.response?.data?.detail || "Impossible de mettre à jour l'équipe.",
        variant: "destructive",
      });
    } finally {
      setSavingTeam(false);
    }
  };

  const handleSaveSaisie = async (data: any[]) => {
    try {
      await saisiesApi.createMonthlyInputs(data);
      toast({ title: "Succès", description: "Saisie(s) enregistrée(s) avec succès." });
      fetchSaisies();
    } catch {
      toast({ title: "Erreur", description: "Échec de l'enregistrement.", variant: "destructive" });
    }
  };

  const isInitialLoad =
    Boolean(employeeId) && !employee && !employeeQuery.isError;

  const employeeDisplayName = employee
    ? `${employee.first_name ?? ""} ${employee.last_name ?? ""}`.trim()
    : "";
  const profileIncomplete = employee ? isProfileIncomplete(employee) : false;

  const handleProfileEditSuccess = useCallback(
    (updated: Employee) => {
      if (!employeeId) return;
      updateEmployeeCache(employeeId, updated);
      evaluateContractualAfterPersist(updated);
      if (updated.team_id) setDraftTeamId(updated.team_id);
      else setDraftTeamId("__none__");
      if (updated.collective_agreement_id !== undefined) {
        setCollectiveAgreementId(updated.collective_agreement_id || null);
      }
    },
    [employeeId, updateEmployeeCache, evaluateContractualAfterPersist],
  );

  if (isInitialLoad) {
    return <SharkFinLoader variant="fullPage" label="Chargement du collaborateur…" />;
  }
  if (employeeQuery.isError && !employee) {
    return (
      <div className="space-y-6">
        <Link to="/employees" className="flex items-center text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="mr-2 h-4 w-4" /> Retour à la liste des collaborateurs
        </Link>
        <p className="text-center text-muted-foreground">Employé non trouvé.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link to="/employees" className="flex items-center text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="mr-2 h-4 w-4" /> Retour à la liste des collaborateurs
      </Link>

      <EmployeeDetailHeaderCard
        employee={employee}
        credentialsPdfUrl={credentialsPdfUrl}
        onDelete={handleDeleteEmployee}
        onEditProfile={() => setProfileEditOpen(true)}
        activeTeams={activeTeamsSorted}
        teamsLoading={teamsActiveQuery.isLoading}
        draftTeamId={draftTeamId}
        onDraftTeamIdChange={setDraftTeamId}
        savedTeamSelectValue={savedTeamSelectValue}
        teamAssignmentDirty={teamAssignmentDirty}
        savingTeam={savingTeam}
        onSaveTeam={handleSaveTeamAssignment}
        onCancelTeam={() => setDraftTeamId(savedTeamSelectValue)}
        companyAgreements={companyAgreements}
        collectiveAgreementId={collectiveAgreementId}
        onCollectiveAgreementIdChange={setCollectiveAgreementId}
        isSavingCC={isSavingCC}
        onSaveCollectiveAgreement={handleSaveCollectiveAgreement}
        companyHasCollectiveAgreements={companyAgreements.length > 0}
      />

      {employeeId && employee && (
        <EmployeeDetailTrialPeriodCard
          employee={employee}
          onEmployeeUpdated={(updated) => updateEmployeeCache(employeeId, updated)}
        />
      )}

      {employeeId && employee && (
        <EmployeeProfileEditDialog
          open={profileEditOpen}
          onOpenChange={setProfileEditOpen}
          employeeId={employeeId}
          employee={employee}
          variant={profileIncomplete ? 'onboarding' : 'edit'}
          onSuccess={handleProfileEditSuccess}
        />
      )}

      {employeeId && employee && (
        <EmployeeOnboardingCompletion
          employeeId={employeeId}
          employee={employee}
          onOpenEdit={() => setProfileEditOpen(true)}
        />
      )}

      {employeeId && showEmployeeCSEBlock && (
        <EmployeeCSEBlock
          employeeId={employeeId}
          collegeElectoral={employee?.college_electoral}
          statutCse={employee?.statut_cse}
          heuresDelegationMensuelles={employee?.heures_delegation_mensuelles}
        />
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} defaultValue="documents" className="w-full">
        <TabsList
          className={cn(
            "grid h-auto min-h-10 w-full gap-0.5 p-1",
            medicalModuleEnabled
              ? "grid-cols-[minmax(0,0.85fr)_minmax(0,1.1fr)_minmax(0,0.85fr)_minmax(0,0.85fr)_minmax(0,0.85fr)_minmax(0,0.85fr)_minmax(0,0.8fr)]"
              : "grid-cols-[minmax(0,0.88fr)_minmax(0,1.14fr)_minmax(0,0.88fr)_minmax(0,0.88fr)_minmax(0,0.88fr)_minmax(0,0.82fr)]",
          )}
        >
          <TabsTrigger value="documents" className="px-2 py-1.5 text-[13px]">
            <FileText className="mr-1.5 h-4 w-4 shrink-0" />
            Documents
          </TabsTrigger>
          <TabsTrigger
            value={TAB_AUGMENTATIONS_PROMOTIONS}
            className="min-w-0 px-2 py-1.5 text-[13px] leading-snug"
            title="Augmentations et Promotions"
          >
            <TrendingUp className="mr-1.5 h-4 w-4 shrink-0" aria-hidden />
            <span className="whitespace-nowrap">Augmentations et Promotions</span>
          </TabsTrigger>
          <TabsTrigger value="saisie" className="px-2 py-1.5 text-[13px]">
            <ClipboardEdit className="mr-1.5 h-4 w-4 shrink-0" />
            Primes et autres
          </TabsTrigger>
          <TabsTrigger value="entretiens" className="relative gap-1.5 px-2 py-1.5 text-[13px]">
            <MessageSquare className="h-4 w-4 shrink-0" aria-hidden />
            Entretiens
            {annualReviewTabHasAlert && (
              <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-amber-500" aria-label="Entretien à traiter" />
            )}
          </TabsTrigger>
          {medicalModuleEnabled && (
            <TabsTrigger value="suivi_medical" className="relative gap-1.5 px-2 py-1.5 text-[13px]">
              <Stethoscope className="h-4 w-4 shrink-0" aria-hidden />
              Suivi médical
              {medicalTabHasOverdue && (
                <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-destructive" aria-label="Visite en retard" />
              )}
            </TabsTrigger>
          )}
          <TabsTrigger value="calendrier" className="px-2 py-1.5 text-[13px]">
            <CalendarIcon className="mr-1.5 h-4 w-4 shrink-0" />
            Calendrier
          </TabsTrigger>
          <TabsTrigger value="badgeuse" className="relative px-2 py-1.5 text-[13px]">
            <ScanLine className="mr-1.5 h-4 w-4 shrink-0" />
            Badgeuse
            {badgeuseTabHasAnomaly && (
              <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-destructive" aria-label="Anomalie de pointage sur les 7 derniers jours" />
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="documents" className="mt-4 space-y-4">
          {employeeId && employee ? (
            <>
              <EmployeeBoethCard employeeId={employeeId} />
              <EmployeeDetailDocumentsTab
                employeeId={employeeId}
                employee={employee}
              />
            </>
          ) : (
            <TabPanelSkeleton />
          )}
        </TabsContent>

        <TabsContent value={TAB_AUGMENTATIONS_PROMOTIONS} className="mt-4">
          <Suspense fallback={<TabPanelSkeleton />}>
            <EmployeeDetailAugmentationsPromotionsTab
              employeeId={employeeId!}
              employee={employee}
              activeCompanyId={activeCompanyId}
              onEmployeeUpdated={(emp) => {
                updateEmployeeCache(employeeId!, emp);
                evaluateContractualAfterPersist(emp);
              }}
            />
          </Suspense>
        </TabsContent>

        <TabsContent value="saisie" className="mt-4 space-y-4">
          {employeeId && employee ? (
            <>
              <EmployeePasSettingsCard
                employeeId={employeeId}
                employee={employee}
                canEdit={canEditEmployeePaySettings}
                onEmployeeUpdated={(updated) => updateEmployeeCache(employeeId, updated)}
              />
              <WorkMedalEmployeeSection
                employeeId={employeeId}
                priorServiceMonths={employee.prior_service_months}
                canEdit={user?.role === "admin" || user?.role === "rh"}
                onPriorServiceChange={async (months) => {
                  try {
                    const updated = await updateEmployee(employeeId, {
                      prior_service_months: months,
                    });
                    updateEmployeeCache(employeeId, updated);
                    toast({ title: "Ancienneté antérieure enregistrée" });
                  } catch {
                    toast({
                      title: "Erreur",
                      description: "Impossible d'enregistrer l'ancienneté antérieure.",
                      variant: "destructive",
                    });
                  }
                }}
              />
              <EmployeeLoansCard
                employeeId={employeeId}
                employeeName={`${employee.first_name ?? ""} ${employee.last_name ?? ""}`.trim()}
                canEdit={canEditEmployeePaySettings}
              />
            </>
          ) : null}
          <EmployeeDetailSaisiesTab
            selectedDate={selectedDate}
            isLoadingSaisies={isLoadingSaisies}
            employeeSaisies={employeeSaisies}
            onAddSaisie={() => setSaisieModalOpen(true)}
            onDeleteSaisie={handleDeleteSaisie}
          />
        </TabsContent>

        <TabsContent value="entretiens" className="mt-4">
          {employeeId && employee && (
            <EmployeeDetailAnnualReviewsTab
              employeeId={employeeId}
              employeeName={employeeDisplayName}
              canDeleteReview={canDeleteReview}
              onEmployeeRefresh={refreshEmployeeSnapshot}
            />
          )}
        </TabsContent>

        {medicalModuleEnabled && employeeId && employee && (
          <TabsContent value="suivi_medical" className="mt-4">
            <EmployeeDetailMedicalTab
              employeeId={employeeId}
              employeeName={employeeDisplayName}
            />
          </TabsContent>
        )}

        <TabsContent value="calendrier" className="mt-4">
          <Suspense fallback={<TabPanelSkeleton />}>
            <EmployeeDetailCalendarTab
              employee={employee}
              employeeId={employeeId!}
              activeCompanyId={activeCompanyId}
              isForfaitJour={isForfaitJour}
              calendarView={calendarView}
              setCalendarView={setCalendarView}
              selectedDate={selectedDate}
              setSelectedDate={setSelectedDate}
              plannedCalendar={plannedCalendar}
              actualHours={actualHours}
              isCalendarLoading={isCalendarLoading}
              isSaving={isSaving}
              saveAllCalendarData={saveAllCalendarData}
              updateDayData={updateDayData}
              weekTemplate={weekTemplate}
              setWeekTemplate={setWeekTemplate}
              applyWeekTemplate={applyWeekTemplate}
              applyWeekTemplateAndSave={applyWeekTemplateAndSave}
              selectedDays={selectedDays}
              handleDaySelection={handleDaySelection}
              bulkUpdateDays={bulkUpdateDays}
              bulkUpdateDaysAndSave={bulkUpdateDaysAndSave}
              updateSelection={updateSelection}
              isDirty={isDirty}
              monthCompletionStatus={monthCompletionStatus}
              copyPreviousMonthPlanned={copyPreviousMonthPlanned}
              copyPlannedToActualForDay={copyPlannedToActualForDay}
              bulkCopyPlannedToActual={bulkCopyPlannedToActual}
              isCopyingPrevMonth={isCopyingPrevMonth}
              reloadCalendar={refetchCalendar}
            />
          </Suspense>
        </TabsContent>

        <TabsContent value="badgeuse" className="mt-4">
          {employeeId && activeCompanyId && employee && (
            <EmployeeDetailBadgeuseSection
              employeeId={employeeId}
              companyId={activeCompanyId}
              employeeName={employeeDisplayName}
              isForfaitJour={isForfaitJour}
              isTabActive={activeTab === "badgeuse"}
            />
          )}
        </TabsContent>
      </Tabs>

      <ContractualChangeDialog
        open={contractualOpen}
        onOpenChange={setContractualOpen}
        employeeId={employeeId!}
        employee={employee}
        diffs={contractualDiffs}
        avenantType={contractualAvenantType}
        onAvenantTypeChange={setContractualAvenantType}
        template={contractualTemplate}
        onTemplateChange={setContractualTemplate}
        dateEffet={contractualDateEffet}
        onDateEffetChange={setContractualDateEffet}
        motifExtra={contractualMotifExtra}
        onMotifExtraChange={setContractualMotifExtra}
        onIgnore={() => {
          setContractualOpen(false);
          resetContractualBaselineFromEmployee(employee);
        }}
        onSuccess={(emp) => {
          updateEmployeeCache(employeeId!, emp);
          resetContractualBaselineFromEmployee(emp);
        }}
      />

      <SaisieModal
        isOpen={saisieModalOpen}
        onClose={() => setSaisieModalOpen(false)}
        onSave={handleSaveSaisie}
        employees={employee ? [employee] : []}
        employeeScopeId={employee?.id}
      />
    </div>
  );
}
