import { log } from '@/lib/logger';
import { useEffect, useMemo, useState } from "react";
import apiClient from '@/api/apiClient';
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import {
  useAnnualReviewsPriorityQuery,
  useDashboardAllQuery,
  useMedicalDashboardQuery,
  usePendingSignaturesRhQuery,
  useRecruitmentPriorityQuery,
  useResidencePermitStatsQuery,
  useRibAlertsDashboardQuery,
} from "@/hooks/queries/useDashboardQueries";
import { DashboardSkeleton } from "@/components/skeletons/DashboardSkeleton";
import { PageFetchIndicator } from "@/components/skeletons/PageFetchIndicator";
import { Link, useNavigate } from "react-router-dom";
import { CopilotModalAgent } from "@/components/CopilotModalAgent";

// --- Composants Shadcn/UI ---
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Checkbox } from "@/components/ui/checkbox";
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartConfig } from "@/components/ui/chart";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis, Legend, Tooltip as RechartsTooltip } from "recharts";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Progress } from "@/components/ui/progress";

// --- Icônes Lucide ---
import {
  Loader2,
  AlertTriangle,
  Inbox,
  Sparkles,
  ChevronRight,
  CalendarCheck,
  CreditCard,
  FileWarning,
  UserPlus,
  Briefcase,
  PartyPopper,
  Plane,
  HeartPulse,
  Landmark,
  Stethoscope,
  TrendingUp,
  Users,
  GraduationCap,
  Mail,
  BarChart3,
} from "lucide-react";

// --- Alertes RIB ---
import * as ribAlertsApi from "@/api/ribAlerts";
import { CSEDashboardBlock } from "@/components/CSEDashboardBlock";
import { PendingSignaturesWidget } from "@/components/dashboard/PendingSignaturesWidget";
import TeamAnalyticsSection from "@/components/dashboard/TeamAnalyticsSection";
import { type KPIs } from "@/api/medicalFollowUp";
import { ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS } from "@/api/annualReviews";
import { isRecruitmentPriorityCandidate, getJobs, getRecruitmentSettings } from "@/api/recruitment";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import { getDashboardCounts } from "@/api/certifications";
import { getOverdueCount } from "@/api/legalObligations";
import { getBudget, type TrainingBudgetAlertLevel } from "@/api/trainingBudget";
import { getAchievementRate } from "@/api/objectives";

// --- 1. Définition des Types de Données ---

interface KpiData {
  coutTotal: number;
  netVerse: number;
  effectifActif: number;
  tauxAbsenteisme: number;
  currentMonth: string;
  cdiCount: number;
  cddCount: number;
  contractDistribution?: Record<string, number>;
  hommesCount?: number | null;
  femmesCount?: number | null;
  handicapesCount?: number | null;
}

interface ChartDataPoint {
  name: string;
  Net_Verse: number;
  Charges: number;
}

interface ActionItems {
  pendingAbsences: number;
  pendingExpenses: number;
}

interface AlertItems {
  obsoleteRates: number;
  expiringContracts: number;
  endOfTrialPeriods: number;
}

interface TeamPulseEmployee {
  id: string;
  first_name: string;
  last_name: string;
  // avatar_url?: string; <-- Suppression
  status: string; 
}

interface TeamPulseEvent {
  id: string;
  type: 'birthday' | 'work_anniversary';
  employee_name: string;
  date: string; // ISO date
  detail: string; 
}

type SimpleEmployee = {
  id: string;
  first_name: string;
  last_name: string;
};

interface DashboardData {
  kpis: KpiData;
  chartData: ChartDataPoint[];
  actions: ActionItems;
  alerts: AlertItems;
  teamPulse: {
    absentToday: TeamPulseEmployee[];
    upcomingEvents: TeamPulseEvent[];
  };
  employees: SimpleEmployee[];
  payrollStatus: {
    currentMonth: string;
    step: number;
    totalSteps: number;
  };
}


// --- 2. Composant Principal: Dashboard ---

interface ResidencePermitStats {
  total_expire: number;
  total_a_renouveler: number;
  total_a_renseigner: number;
  total_valide: number;
}

type DashboardPriorityKey = string;
const PRIORITY_DAY_STORAGE_KEY = "eywai.dashboard.priority-day.validated.v1";
type PriorityValidationByCount = Record<string, number>;

export default function Dashboard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id;
  const queryClient = useQueryClient();

  const dashboardQuery = useDashboardAllQuery(Boolean(companyId));
  const residenceQuery = useResidencePermitStatsQuery(Boolean(companyId));
  const ribQuery = useRibAlertsDashboardQuery(Boolean(companyId));
  const medical = useMedicalDashboardQuery(Boolean(companyId));
  const annualReviewsQuery = useAnnualReviewsPriorityQuery(Boolean(companyId));
  const recruitment = useRecruitmentPriorityQuery(Boolean(companyId));
  const pendingSignaturesQuery = usePendingSignaturesRhQuery(Boolean(companyId));

  const data = dashboardQuery.data as DashboardData | undefined;
  const loading = dashboardQuery.isLoading && !dashboardQuery.data;
  const error = dashboardQuery.error
    ? (dashboardQuery.error as { response?: { data?: { detail?: string } }; message?: string })
        .response?.data?.detail ||
      (dashboardQuery.error as Error).message ||
      'Une erreur est survenue.'
    : null;

  const residencePermitStats = residenceQuery.data ?? null;
  const residencePermitLoading = residenceQuery.isLoading && !residenceQuery.data;
  const ribAlerts = ribQuery.data?.alerts ?? [];
  const ribAlertTotal = ribQuery.data?.total ?? 0;
  const ribAlertsLoading = ribQuery.isLoading && !ribQuery.data;
  const medicalModuleEnabled = medical.medicalModuleEnabled;
  const medicalKpis = medical.medicalKpis;
  const medicalKpisLoading = medical.isLoading;
  const annualReviewsUpcomingCount = annualReviewsQuery.data ?? 0;
  const recruitmentPendingCount = recruitment.pendingCount;
  const recruitmentPendingPreview = useMemo(() => {
    const candidates = recruitment.candidatesQuery.data;
    if (!candidates?.length) return null;
    const pending = candidates.filter(isRecruitmentPriorityCandidate);
    if (pending.length === 0) return null;
    return pending
      .slice(0, 2)
      .map((c) => `${c.first_name} ${c.last_name}`)
      .join(' · ');
  }, [recruitment.candidatesQuery.data]);

  const pendingSignaturesCount = pendingSignaturesQuery.data?.total ?? 0;

  const isFetching =
    dashboardQuery.isFetching ||
    residenceQuery.isFetching ||
    ribQuery.isFetching ||
    medical.isFetching;

  const [isGeneratePayrollModalOpen, setIsGeneratePayrollModalOpen] = useState(false);
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const [selectedPriorityKey, setSelectedPriorityKey] = useState<DashboardPriorityKey | null>(null);
  const [validatedPriorityByCount, setValidatedPriorityByCount] = useState<PriorityValidationByCount>(() => {
    try {
      const raw = sessionStorage.getItem(PRIORITY_DAY_STORAGE_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw) as unknown;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        const out: PriorityValidationByCount = {};
        for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
          if (typeof k === "string" && typeof v === "number") out[k] = v;
        }
        return out;
      }
      // Ancien format tableau ignoré pour éviter un masquage permanent.
      return {};
    } catch {
      return {};
    }
  });

  // Gère le raccourci clavier global (Cmd+K) pour le Copilote
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setIsCopilotOpen((open) => !open) // Inverse l'état (ouvre ou ferme)
      }
    }
    document.addEventListener("keydown", down)
    return () => document.removeEventListener("keydown", down)
  }, []) // Le tableau de dépendances est vide, il est global

  // --- Rendu des États (Chargement, Erreur, Vide) ---
  if (!companyId) {
    return (
      <div className="flex flex-col justify-center items-center h-64 text-muted-foreground">
        <Inbox className="h-10 w-10" />
        <span className="mt-4 text-lg font-medium">Aucune entreprise active</span>
        <span className="text-sm">Sélectionnez une entreprise pour afficher le tableau de bord.</span>
      </div>
    );
  }

  if (loading) {
    return <DashboardSkeleton />;
  }

  if (error) {
    return (
      <Card className="border-red-500/50 bg-red-500/5">
        <CardHeader>
          <CardTitle className="flex items-center text-red-600"><AlertTriangle className="mr-2 h-5 w-5" />Échec du chargement</CardTitle>
        </CardHeader>
        <CardContent className="text-red-500">
          <p>L'API a retourné une erreur :</p>
          <p className="font-mono bg-red-500/10 p-2 rounded-md mt-2 text-sm">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <div className="flex flex-col justify-center items-center h-64 text-muted-foreground">
        <Inbox className="h-10 w-10" />
        <span className="mt-4 text-lg font-medium">Aucune donnée de dashboard</span>
        <span className="text-sm">Impossible de récupérer les informations de pilotage.</span>
      </div>
    );
  }

  // --- Rendu Principal du Dashboard ---

  const residencePendingTotal =
    (residencePermitStats?.total_expire || 0) +
    (residencePermitStats?.total_a_renouveler || 0) +
    (residencePermitStats?.total_a_renseigner || 0);
  const medicalPendingTotal =
    medicalModuleEnabled && medicalKpis
      ? medicalKpis.overdue_count + medicalKpis.due_within_30_count
      : 0;
  const mainFocusCandidates: Array<{
    key: DashboardPriorityKey;
    label: string;
    count: number;
    href: string;
    icon: typeof CalendarCheck;
    hint: string;
  }> = [
    {
      key: "leaves",
      label: "Demandes d'absences",
      count: data.actions.pendingAbsences,
      href: "/leaves",
      icon: CalendarCheck,
      hint: "À valider aujourd'hui",
    },
    {
      key: "expenses",
      label: "Notes de frais",
      count: data.actions.pendingExpenses,
      href: "/expenses",
      icon: CreditCard,
      hint: "En attente de traitement",
    },
    {
      key: "rib",
      label: "Alertes RIB",
      count: ribAlertTotal,
      href: "/employees",
      icon: Landmark,
      hint: "Contrôles administratifs",
    },
    {
      key: "medical",
      label: "Suivi médical",
      count: medicalPendingTotal,
      href: "/medical-follow-up",
      icon: Stethoscope,
      hint: "Visites à planifier",
    },
    {
      key: "residence",
      label: "Titres de séjour",
      count: residencePendingTotal,
      href: "/residence-permits",
      icon: FileWarning,
      hint: "Échéances à surveiller",
    },
    {
      key: "annualReviews",
      label: "Entretiens planifiés",
      count: annualReviewsUpcomingCount,
      href: "/annual-reviews?focus=upcoming",
      icon: CalendarCheck,
      hint: `Planifiés dans ${ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS} jours`,
    },
    {
      key: "recruitment",
      label: "Recrutement",
      count: recruitmentPendingCount,
      href: "/recruitment",
      icon: UserPlus,
      hint: recruitmentPendingPreview
        ? `Candidats à traiter : ${recruitmentPendingPreview}`
        : "Candidatures en cours",
    },
    {
      key: "rates",
      label: "Taux de cotisations",
      count: data.alerts.obsoleteRates,
      href: "/rates",
      icon: TrendingUp,
      hint: "Mises à jour nécessaires",
    },
    {
      key: "pendingSignatures",
      label: "Signatures en attente",
      count: pendingSignaturesCount,
      href: "/annual-reviews?signature_status=pending",
      icon: Mail,
      hint: "Procédures à relancer",
    },
  ];
  const availablePriorityItems = mainFocusCandidates.filter((item) => item.count > 0);
  const pendingPriorityItems = availablePriorityItems.filter(
    (item) => validatedPriorityByCount[item.key] !== item.count,
  );
  const selectedPriorityItem =
    pendingPriorityItems.find((item) => item.key === selectedPriorityKey) ||
    pendingPriorityItems[0] ||
    null;
  const mainFocus = selectedPriorityItem;
  const remainingMainFocus = pendingPriorityItems.length > 1 ? pendingPriorityItems.length - 1 : 0;
  const priorityProgressTotal = availablePriorityItems.length;
  const priorityProgressDone = availablePriorityItems.filter(
    (item) => validatedPriorityByCount[item.key] === item.count,
  ).length;
  const priorityProgressPct =
    priorityProgressTotal > 0
      ? Math.round((priorityProgressDone / priorityProgressTotal) * 100)
      : 100;
  const todayLabelRaw = new Date().toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  const todayLabel =
    todayLabelRaw.charAt(0).toUpperCase() + todayLabelRaw.slice(1);

  const handleValidateAndNext = () => {
    if (!selectedPriorityItem) return;
    const nextValidated: PriorityValidationByCount = {
      ...validatedPriorityByCount,
      [selectedPriorityItem.key]: selectedPriorityItem.count,
    };
    setValidatedPriorityByCount(nextValidated);
    sessionStorage.setItem(PRIORITY_DAY_STORAGE_KEY, JSON.stringify(nextValidated));
  };

  const handleResetPriorities = () => {
    setValidatedPriorityByCount({});
    sessionStorage.removeItem(PRIORITY_DAY_STORAGE_KEY);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <PageFetchIndicator isFetching={isFetching} />
      <DashboardHeader
        firstName={user?.first_name || "Utilisateur"}
        dateLabel={todayLabel}
        onCopilotClick={() => setIsCopilotOpen(true)}
        onGeneratePayrollClick={() => setIsGeneratePayrollModalOpen(true)}
      />
      <div className="space-y-6">
        <Card className="border-l-4 border-l-primary shadow-sm">
          <CardContent className="p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="space-y-2 min-w-0 flex-1">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Priorité du jour
                </p>
                {mainFocus ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <mainFocus.icon className="h-5 w-5 text-primary shrink-0" />
                    <p className="text-lg font-semibold text-foreground">
                      {mainFocus.label} ({mainFocus.count})
                    </p>
                    <Badge variant="secondary" className="max-w-full truncate">
                      {mainFocus.hint}
                    </Badge>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <PartyPopper className="h-5 w-5 text-emerald-600 shrink-0" />
                      <p className="text-lg font-semibold text-foreground">
                        Aucun blocage prioritaire détecté
                      </p>
                    </div>
                    <Button variant="link" className="h-auto p-0 text-sm" asChild>
                      <Link to="/analytics">Voir les indicateurs de pilotage →</Link>
                    </Button>
                  </div>
                )}
                {pendingPriorityItems.length > 0 && (
                  <div className="max-w-md space-y-2">
                    <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <span>
                        {priorityProgressDone}/{priorityProgressTotal} tâches traitées
                      </span>
                      {remainingMainFocus > 0 && (
                        <span>
                          Reste : {remainingMainFocus} tâche{remainingMainFocus > 1 ? "s" : ""}
                        </span>
                      )}
                    </div>
                    <Progress value={priorityProgressPct} className="h-1.5" />
                    <div>
                      <Label className="text-xs text-muted-foreground">Changer de tâche</Label>
                      <Select
                        value={selectedPriorityItem?.key}
                        onValueChange={(value) =>
                          setSelectedPriorityKey(value as DashboardPriorityKey)
                        }
                      >
                        <SelectTrigger className="mt-1 h-9">
                          <SelectValue placeholder="Choisir une tâche" />
                        </SelectTrigger>
                        <SelectContent>
                          {pendingPriorityItems.map((task) => (
                            <SelectItem key={task.key} value={task.key}>
                              {task.label} ({task.count})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )}
                {availablePriorityItems.length > 0 &&
                  Object.keys(validatedPriorityByCount).length > 0 &&
                  !mainFocus && (
                    <button
                      type="button"
                      className="text-xs text-muted-foreground underline-offset-4 hover:underline"
                      onClick={handleResetPriorities}
                    >
                      Reprendre la file depuis le début
                    </button>
                  )}
              </div>
              <div className="flex flex-wrap items-center gap-2 shrink-0">
                {mainFocus ? (
                  <>
                    <Button asChild>
                      <Link to={mainFocus.href}>Ouvrir le module</Link>
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={handleValidateAndNext}
                    >
                      Valider et passer à l&apos;étape suivante
                    </Button>
                  </>
                ) : null}
              </div>
            </div>
          </CardContent>
        </Card>

        <section className="space-y-4 rounded-xl border bg-background p-4 md:p-5">
          <div>
            <h2 className="text-xl font-semibold">À traiter aujourd&apos;hui</h2>
            <p className="text-sm text-muted-foreground">
              Détail des dossiers à traiter — signatures, alertes et conformité.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <PendingSignaturesWidget mode="rh" />
            <RibAlertsCard
              alerts={ribAlerts}
              loading={ribAlertsLoading}
              onRefresh={() => {
                void queryClient.invalidateQueries({
                  queryKey: queryKeys.ribAlerts(companyId),
                });
              }}
            />
            {medicalModuleEnabled ? (
              <MedicalFollowUpCard kpis={medicalKpis} loading={medicalKpisLoading} />
            ) : (
              <Card className="border-dashed">
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Stethoscope className="h-5 w-5 text-muted-foreground" />
                    Suivi médical
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Module non activé pour cette entreprise.
                  </p>
                </CardContent>
              </Card>
            )}
          </div>

          <ResidencePermitCard stats={residencePermitStats} loading={residencePermitLoading} />
        </section>

        <FormationTalentsDashboardWidget />

        <section className="space-y-4 rounded-xl border bg-background p-4 md:p-5">
          <div>
            <h2 className="text-xl font-semibold">Pilotage</h2>
            <p className="text-sm text-muted-foreground">
              Masse salariale, effectif et tendances pour piloter l&apos;entreprise.
            </p>
          </div>

          <div className="space-y-6">
            <CoutsCard kpis={data.kpis} chartData={data.chartData} />
            <EffectifPanorama
              kpis={data.kpis}
              absentsToday={data.teamPulse?.absentToday || []}
              upcomingEvents={data.teamPulse?.upcomingEvents || []}
            />
            <RecruitmentKpisCard />
            <Accordion type="single" collapsible defaultValue="">
              <AccordionItem value="team-analytics" className="border rounded-lg px-4">
                <AccordionTrigger className="text-base font-semibold hover:no-underline py-4">
                  <span className="flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-muted-foreground" />
                    Analytics par équipe
                  </span>
                </AccordionTrigger>
                <AccordionContent className="pb-4">
                  <TeamAnalyticsSection />
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>

          <CSEDashboardBlock />
        </section>
      </div>

      {/* --- Modaux --- */}
      <CopilotModalAgent
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
      />
      <GeneratePayrollModal
        isOpen={isGeneratePayrollModalOpen}
        onClose={() => setIsGeneratePayrollModalOpen(false)}
        employees={data.employees}
      />

    </div>
  );
}


// --- 3. Sous-Composants du Dashboard ---

function FormationTalentsCellLoader() {
  return (
    <div className="mt-3 flex min-h-[40px] items-center justify-center">
      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden />
    </div>
  );
}

function countBadgeClass(n: number, tone: "red" | "orange") {
  if (n <= 0) return "bg-muted text-muted-foreground";
  return tone === "red" ? "bg-red-600 text-white" : "bg-orange-500 text-white";
}

function budgetGaugeFillClass(level: TrainingBudgetAlertLevel) {
  if (level === "critical") return "bg-red-500";
  if (level === "warning") return "bg-orange-500";
  return "bg-emerald-500";
}

function FormationTalentsDashboardWidget() {
  const navigate = useNavigate();
  const year = new Date().getFullYear();

  const certsQuery = useQuery({
    queryKey: ["dashboard", "formation", "cert-counts"],
    queryFn: getDashboardCounts,
  });
  const overdueQuery = useQuery({
    queryKey: ["dashboard", "formation", "overdue"],
    queryFn: getOverdueCount,
  });
  const budgetQuery = useQuery({
    queryKey: ["dashboard", "formation", "budget", year],
    queryFn: () => getBudget(year),
  });
  const achievementQuery = useQuery({
    queryKey: ["dashboard", "formation", "achievement", year],
    queryFn: () => getAchievementRate(year),
  });

  const expired = certsQuery.isError ? null : (certsQuery.data?.expired ?? 0);
  const expiring = certsQuery.isError ? null : (certsQuery.data?.expiring ?? 0);
  const overdue = overdueQuery.isError ? null : (overdueQuery.data?.count ?? 0);
  const pct =
    budgetQuery.isError || !budgetQuery.data
      ? null
      : Math.min(100, Math.max(0, budgetQuery.data.consumption_pct));
  const alertLevel: TrainingBudgetAlertLevel | null = budgetQuery.isError
    ? null
    : (budgetQuery.data?.alert_level ?? "none");
  const rate =
    achievementQuery.isError || achievementQuery.data?.rate == null
      ? null
      : achievementQuery.data.rate;

  const rateColor =
    rate == null
      ? "text-muted-foreground"
      : rate >= 80
        ? "text-emerald-600"
        : rate >= 50
          ? "text-orange-600"
          : "text-red-600";

  return (
    <Card className="border-primary/15 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <GraduationCap className="h-5 w-5 text-primary" />
          Formation &amp; Talents
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Indicateurs Pack Talent — cliquez pour ouvrir le module.
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <button
            type="button"
            onClick={() =>
              navigate({ pathname: "/formation", hash: "conformite", search: "?sub=habilitations" })
            }
            className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
          >
            <span className="text-xs font-medium text-muted-foreground">Habilitations expirées</span>
            {certsQuery.isLoading ? (
              <FormationTalentsCellLoader />
            ) : (
              <div className="mt-2 flex flex-1 flex-col justify-center gap-2">
                <Badge
                  className={
                    expired == null ? "bg-muted text-muted-foreground" : countBadgeClass(expired, "red")
                  }
                >
                  {expired == null ? "—" : expired}
                </Badge>
              </div>
            )}
          </button>

          <button
            type="button"
            onClick={() =>
              navigate({ pathname: "/formation", hash: "conformite", search: "?sub=habilitations" })
            }
            className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
          >
            <span className="text-xs font-medium text-muted-foreground">Habilitations à échéance</span>
            {certsQuery.isLoading ? (
              <FormationTalentsCellLoader />
            ) : (
              <div className="mt-2 flex flex-1 flex-col justify-center gap-2">
                <Badge
                  className={
                    expiring == null ? "bg-muted text-muted-foreground" : countBadgeClass(expiring, "orange")
                  }
                >
                  {expiring == null ? "—" : expiring}
                </Badge>
              </div>
            )}
          </button>

          <button
            type="button"
            onClick={() =>
              navigate({ pathname: "/formation", hash: "formations", search: "?sub=budget" })
            }
            className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
          >
            <span className="text-xs font-medium text-muted-foreground">Budget formation consommé</span>
            {budgetQuery.isLoading ? (
              <FormationTalentsCellLoader />
            ) : pct == null || alertLevel == null ? (
              <p className="mt-3 text-sm text-muted-foreground">—</p>
            ) : (
              <div className="mt-3 space-y-1">
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full transition-all ${budgetGaugeFillClass(alertLevel)}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="text-xs tabular-nums text-muted-foreground">{pct.toFixed(0)} %</p>
              </div>
            )}
          </button>

          <button
            type="button"
            onClick={() =>
              navigate({ pathname: "/formation", hash: "conformite", search: "?sub=obligations" })
            }
            className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
          >
            <span className="text-xs font-medium text-muted-foreground">Retard entretien prof.</span>
            {overdueQuery.isLoading ? (
              <FormationTalentsCellLoader />
            ) : (
              <div className="mt-2 flex flex-1 flex-col justify-center gap-2">
                <Badge
                  className={
                    overdue == null ? "bg-muted text-muted-foreground" : countBadgeClass(overdue, "red")
                  }
                >
                  {overdue == null ? "—" : overdue}
                </Badge>
              </div>
            )}
          </button>

          <button
            type="button"
            onClick={() =>
              navigate({ pathname: "/formation", hash: "developpement", search: "?sub=objectifs" })
            }
            className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
          >
            <span className="text-xs font-medium text-muted-foreground">Taux d&apos;atteinte objectifs</span>
            {achievementQuery.isLoading ? (
              <FormationTalentsCellLoader />
            ) : (
              <p className={`mt-3 text-2xl font-bold tabular-nums ${rateColor}`}>
                {rate == null ? "—" : `${rate.toFixed(0)} %`}
              </p>
            )}
          </button>
        </div>
      </CardContent>
    </Card>
  );
}

// --- Section 1: Header & Copilote ---
function DashboardHeader({
  firstName,
  dateLabel,
  onCopilotClick,
  onGeneratePayrollClick,
}: {
  firstName: string;
  dateLabel: string;
  onCopilotClick: () => void;
  onGeneratePayrollClick: () => void;
}) {
  return (
    <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Bonjour {firstName},</h1>
        <p className="text-muted-foreground mt-1">{dateLabel}</p>
        <p className="text-sm text-muted-foreground">Cockpit de pilotage RH</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" onClick={onGeneratePayrollClick}>
          <Sparkles className="h-4 w-4 mr-2" />
          Générer la paie
        </Button>
        <Button onClick={onCopilotClick}>
          <Sparkles className="h-4 w-4 mr-2" />
          Demander à l&apos;IA
        </Button>
      </div>
    </div>
  );
}

function ResidencePermitCard({ stats, loading }: { stats: ResidencePermitStats | null, loading: boolean }) {
  const displayStats = stats || {
    total_expire: 0,
    total_a_renouveler: 0,
    total_a_renseigner: 0,
    total_valide: 0
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Titres de séjour</CardTitle>
        <p className="text-xs text-muted-foreground mt-1">Suivi des échéances administratives</p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex justify-center items-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-3">
            {/* Expiré */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-red-50 border border-red-200">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-red-500"></div>
                <span className="text-sm font-medium text-red-900">Expiré</span>
              </div>
              <span className="text-lg font-bold text-red-700">{displayStats.total_expire}</span>
            </div>

            {/* À renouveler */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-orange-50 border border-orange-200">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-orange-500"></div>
                <span className="text-sm font-medium text-orange-900">À renouveler</span>
              </div>
              <span className="text-lg font-bold text-orange-700">{displayStats.total_a_renouveler}</span>
            </div>

            {/* À renseigner */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-200">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-gray-500"></div>
                <span className="text-sm font-medium text-gray-900">À renseigner</span>
              </div>
              <span className="text-lg font-bold text-gray-700">{displayStats.total_a_renseigner}</span>
            </div>

            {/* Valide */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-green-50 border border-green-200">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-green-500"></div>
                <span className="text-sm font-medium text-green-900">Valide</span>
              </div>
              <span className="text-lg font-bold text-green-700">{displayStats.total_valide}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MedicalFollowUpCard({ kpis, loading }: { kpis: KPIs | null; loading: boolean }) {
  const navigate = useNavigate();
  const overdue = kpis?.overdue_count ?? 0;
  const due30 = kpis?.due_within_30_count ?? 0;
  const totalAVenir = overdue + due30;
  const hasAlert = totalAVenir > 0;

  return (
    <Card className={hasAlert ? "border-teal-200" : ""}>
      <CardHeader>
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <Stethoscope className="h-5 w-5 text-teal-600" />
          Suivi visites médicales
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-1">
          {loading ? (
            <Loader2 className="h-3 w-3 animate-spin inline" />
          ) : (
            <>
              <span className={totalAVenir > 0 ? "font-bold text-teal-700" : ""}>
                {totalAVenir > 0 ? `${totalAVenir} visite${totalAVenir > 1 ? "s" : ""} à venir` : "À jour"}
              </span>
            </>
          )}
        </p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex justify-center items-center py-6">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-3">
            {overdue > 0 && (
              <div className="flex items-center justify-between p-3 rounded-lg bg-red-50 border border-red-200">
                <span className="text-sm font-medium text-red-900">En retard</span>
                <span className="text-lg font-bold text-red-700">{overdue}</span>
              </div>
            )}
            {due30 > 0 && (
              <div className="flex items-center justify-between p-3 rounded-lg bg-orange-50 border border-orange-200">
                <span className="text-sm font-medium text-orange-900">Échéance &lt; 30 j</span>
                <span className="text-lg font-bold text-orange-700">{due30}</span>
              </div>
            )}
            {!hasAlert && (
              <p className="text-sm text-muted-foreground py-2">Aucune visite à planifier.</p>
            )}
            <Button variant="outline" size="sm" className="w-full mt-2" onClick={() => navigate("/medical-follow-up")}>
              Voir le suivi médical
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RibAlertsCard({
  alerts,
  loading,
  onRefresh,
}: {
  alerts: ribAlertsApi.RibAlert[];
  loading: boolean;
  onRefresh: () => void;
}) {
  const navigate = useNavigate();

  const handleMarkRead = async (id: string) => {
    try {
      await ribAlertsApi.markRibAlertRead(id);
      onRefresh();
    } catch (e) {
      log.error(e);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Landmark className="h-5 w-5" />
            Alertes RIB
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex justify-center py-6">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Landmark className="h-5 w-5" />
          Alertes RIB
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-1">Modification ou doublon de RIB</p>
      </CardHeader>
      <CardContent className="space-y-2">
        {alerts.length === 0 ? (
          <p className="text-sm text-muted-foreground py-2">Aucune alerte RIB.</p>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              className={`p-3 rounded-lg border text-sm ${alert.is_read ? "bg-muted/50 border-muted" : "bg-amber-50/50 border-amber-200"}`}
            >
              <div className="font-medium text-foreground">{alert.title}</div>
              <p className="text-muted-foreground mt-1 line-clamp-2">{alert.message}</p>
              <div className="flex items-center justify-between mt-2 gap-2">
                <span className="text-xs text-muted-foreground">
                  {new Date(alert.created_at).toLocaleDateString("fr-FR")}
                </span>
                <div className="flex gap-1">
                  {alert.employee_id && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => navigate(`/employees/${alert.employee_id}`)}
                    >
                      Fiche
                    </Button>
                  )}
                  {!alert.is_read && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => handleMarkRead(alert.id)}
                    >
                      Marquer lu
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

const CONTRACT_LABELS: Record<string, string> = {
  CDI: "CDI",
  CDD: "CDD",
  Alternance: "Alternant",
  Stage: "Stagiaire",
  Intérim: "Intérim",
  Freelance: "Freelance",
  Autre: "Autre",
};

// --- KPIs Recrutement ---
function RecruitmentKpisCard() {
  const navigate = useNavigate();
  const { data: settings } = useQuery({ queryKey: ["recruitment", "settings"], queryFn: getRecruitmentSettings });
  const { data: jobs = [] } = useQuery({ queryKey: ["recruitment", "jobs"], queryFn: () => getJobs("active"), enabled: !!settings?.enabled });
  const { data: candidates = [] } = useQuery({ queryKey: ["recruitment", "candidates"], queryFn: () => getCandidates(), enabled: !!settings?.enabled });
  const inProgress = candidates.filter((c) => c.current_stage_type !== "hired" && c.current_stage_type !== "rejected").length;
  const hired = candidates.filter((c) => c.current_stage_type === "hired").length;
  if (!settings?.enabled) return null;
  return (
    <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate("/recruitment")}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <UserPlus className="h-4 w-4 text-muted-foreground" />
          Recrutement
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <p className="text-muted-foreground">Offres actives</p>
            <p className="font-bold text-foreground">{jobs.length}</p>
          </div>
          <div>
            <p className="text-muted-foreground">En cours</p>
            <p className="font-bold text-foreground">{inProgress}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Embauchés</p>
            <p className="font-bold text-foreground">{hired}</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" className="mt-2 w-full" onClick={(e) => { e.stopPropagation(); navigate("/recruitment"); }}>
          Voir le recrutement <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </CardContent>
    </Card>
  );
}

function EffectifPanorama({
  kpis,
  absentsToday,
  upcomingEvents,
}: {
  kpis: KpiData;
  absentsToday: TeamPulseEmployee[];
  upcomingEvents: TeamPulseEvent[];
}) {
  const hommes = kpis.hommesCount ?? null;
  const femmes = kpis.femmesCount ?? null;
  const hasGenderData = hommes != null && femmes != null;
  const dist = kpis.contractDistribution || {};
  const handicap = kpis.handicapesCount ?? 0;
  const contractTypes = ["CDI", "CDD", "Alternance", "Stage"].filter((t) => (dist[t] ?? 0) > 0);
  const otherContractKeys = Object.keys(dist).filter(
    (k) => !["CDI", "CDD", "Alternance", "Stage"].includes(k),
  );
  const hasContractData =
    contractTypes.length > 0 || otherContractKeys.length > 0 || handicap > 0;

  const getAbsenceIcon = (status: string) => {
    if (status.includes("Maladie")) return <HeartPulse className="h-3 w-3 text-red-500" />;
    if (status.includes("Congé")) return <Plane className="h-3 w-3 text-blue-500" />;
    if (status.includes("RTT")) return <CalendarCheck className="h-3 w-3 text-purple-500" />;
    return <CalendarCheck className="h-3 w-3 text-muted-foreground" />;
  };

  const getEventIcon = (type: TeamPulseEvent["type"]) => {
    if (type === "birthday") return <PartyPopper className="h-4 w-4 text-pink-500" />;
    return <Briefcase className="h-4 w-4 text-primary" />;
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold">Effectif &amp; absentéisme</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border bg-muted/20 p-4 text-center">
            <p className="text-xs font-medium text-muted-foreground mb-1">Effectif actif</p>
            <p className="text-3xl font-bold tabular-nums">{kpis.effectifActif}</p>
            <div className="mt-2 flex justify-center gap-4 text-xs text-muted-foreground border-t pt-2">
              <span>
                CDI <span className="font-bold text-foreground">{kpis.cdiCount}</span>
              </span>
              <span>
                CDD <span className="font-bold text-foreground">{kpis.cddCount}</span>
              </span>
            </div>
          </div>

          <div className="rounded-lg border bg-muted/20 p-4">
            <p className="text-xs font-medium text-muted-foreground mb-2 text-center">
              Répartition H / F
            </p>
            {!hasGenderData ? (
              <p className="text-sm text-muted-foreground text-center">Non renseigné</p>
            ) : (
              <div className="flex flex-col gap-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-blue-500" />
                    Hommes
                  </span>
                  <span className="font-bold tabular-nums">{hommes}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-pink-500" />
                    Femmes
                  </span>
                  <span className="font-bold tabular-nums">{femmes}</span>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-lg border bg-muted/20 p-4">
            <p className="text-xs font-medium text-muted-foreground mb-2 text-center">Contrats</p>
            {!hasContractData ? (
              <p className="text-sm text-muted-foreground text-center">Aucune donnée</p>
            ) : (
              <div className="space-y-1 text-xs">
                {contractTypes.map((t) => (
                  <div key={t} className="flex justify-between">
                    <span className="text-muted-foreground">{CONTRACT_LABELS[t] ?? t}</span>
                    <span className="font-bold tabular-nums">{dist[t] ?? 0}</span>
                  </div>
                ))}
                {otherContractKeys.map((t) => (
                  <div key={t} className="flex justify-between">
                    <span className="text-muted-foreground">{CONTRACT_LABELS[t] ?? t}</span>
                    <span className="font-bold tabular-nums">{dist[t] ?? 0}</span>
                  </div>
                ))}
                {handicap > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">RQTH</span>
                    <span className="font-bold tabular-nums">{handicap}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="rounded-lg border bg-muted/20 p-4 text-center">
            <p className="text-xs font-medium text-muted-foreground mb-1">Absentéisme (30j)</p>
            <p
              className={`text-3xl font-bold tabular-nums ${
                kpis.tauxAbsenteisme > 5 ? "text-amber-600" : "text-foreground"
              }`}
            >
              {kpis.tauxAbsenteisme.toFixed(1)}%
            </p>
            <p className="text-[10px] text-muted-foreground mt-1">Seuil d&apos;alerte : 5 %</p>
            <p className="text-xs font-medium text-muted-foreground mt-3 mb-1">
              Absents aujourd&apos;hui
            </p>
            <p
              className={`text-xl font-bold tabular-nums ${
                absentsToday.length > 0 ? "text-red-600" : "text-emerald-600"
              }`}
            >
              {absentsToday.length}
            </p>
            {absentsToday.length > 0 && absentsToday.length <= 2 && (
              <div className="mt-2 space-y-1 border-t pt-2">
                {absentsToday.map((emp) => (
                  <div
                    key={emp.id}
                    className="flex items-center justify-center gap-1 text-[10px] text-muted-foreground"
                  >
                    {getAbsenceIcon(emp.status)}
                    <span>
                      {emp.first_name} {emp.last_name}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {upcomingEvents.length > 0 && (
          <div className="rounded-lg border border-dashed p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
              Cette semaine
            </p>
            <ul className="space-y-2">
              {upcomingEvents.slice(0, 3).map((event) => (
                <li key={event.id} className="flex items-center gap-2 text-sm">
                  {getEventIcon(event.type)}
                  <span className="font-medium">{event.employee_name}</span>
                  <span className="text-muted-foreground text-xs">— {event.detail}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const chartConfig = {
  "Net_Verse": {
    label: "Net Versé",
    color: "hsl(142, 76%, 36%)", // Vert
  },
  "Charges": {
    label: "Charges",
    color: "hsl(0, 80%, 50%)", // Rouge
  },
} satisfies ChartConfig;

// --- Grande carte Coûts combinant Masse Salariale et Evolution ---

function formatMonthOverMonthDelta(pct: number | null): string | null {
  if (pct == null || Number.isNaN(pct)) return null;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)} % vs mois précédent`;
}

function CoutsCard({ kpis, chartData }: { kpis: KpiData; chartData: ChartDataPoint[] }) {
  let coutDeltaPct: number | null = null;
  let netDeltaPct: number | null = null;
  if (chartData.length >= 2) {
    const prev = chartData[chartData.length - 2];
    const last = chartData[chartData.length - 1];
    const prevCout = prev.Net_Verse + prev.Charges;
    const lastCout = last.Net_Verse + last.Charges;
    if (prevCout > 0) {
      coutDeltaPct = ((lastCout - prevCout) / prevCout) * 100;
    }
    if (prev.Net_Verse > 0) {
      netDeltaPct = ((last.Net_Verse - prev.Net_Verse) / prev.Net_Verse) * 100;
    }
  }
  const coutDeltaLabel = formatMonthOverMonthDelta(coutDeltaPct);
  const netDeltaLabel = formatMonthOverMonthDelta(netDeltaPct);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold">Coûts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">
            Masse salariale {kpis.currentMonth}
          </h3>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div className="text-center">
              <p className="text-xs text-muted-foreground font-medium mb-1">Coût total</p>
              <div className="text-2xl font-bold text-foreground tabular-nums">
                {kpis.coutTotal.toLocaleString("fr-FR")} €
              </div>
              {coutDeltaLabel && (
                <p className="text-xs text-muted-foreground mt-1">{coutDeltaLabel}</p>
              )}
            </div>
            <div className="text-center">
              <p className="text-xs text-muted-foreground font-medium mb-1">Net versé</p>
              <div className="text-2xl font-bold text-foreground tabular-nums">
                {kpis.netVerse.toLocaleString("fr-FR")} €
              </div>
              {netDeltaLabel && (
                <p className="text-xs text-muted-foreground mt-1">{netDeltaLabel}</p>
              )}
            </div>
          </div>
        </div>

        {/* Evolution des Coûts */}
        <div className="pt-4 border-t">
          <h3 className="text-sm font-medium text-muted-foreground mb-4">Évolution (12 derniers mois)</h3>
          <ChartContainer config={chartConfig} className="h-[250px] w-full">
            <BarChart data={chartData}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis
                dataKey="name"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `${(value / 1000).toFixed(0)}k€`}
              />
              <RechartsTooltip
                content={<ChartTooltipContent />}
                formatter={(value: number) => `${value.toLocaleString('fr-FR')} €`}
              />
              <Legend />
              <Bar
                dataKey="Net_Verse"
                stackId="a"
                fill="var(--color-Net_Verse)"
                radius={[0, 0, 0, 0]}
                name="Net Versé"
              />
              <Bar
                dataKey="Charges"
                stackId="a"
                fill="var(--color-Charges)"
                radius={[4, 4, 0, 0]}
                name="Charges"
              />
            </BarChart>
          </ChartContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// --- Modal de Génération de Paie ---

function GeneratePayrollModal({ isOpen, onClose, employees }: { isOpen: boolean, onClose: () => void, employees: SimpleEmployee[] }) {
  const [selectedEmployees, setSelectedEmployees] = useState<Set<string>>(new Set());
  const [selectedMonth, setSelectedMonth] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<{ success: string[], errors: { id: string, name: string, error: string }[] }>({ success: [], errors: [] });

  // Générer les options de mois (12 derniers mois + mois actuel + 2 mois futurs)
  const generateMonthOptions = () => {
    const options = [];
    const now = new Date();

    // Générer 12 mois précédents + mois actuel + 2 mois futurs
    for (let i = -12; i <= 2; i++) {
      const date = new Date(now.getFullYear(), now.getMonth() + i, 1);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const value = `${year}-${month}`;
      const label = date.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
      options.push({ value, label: label.charAt(0).toUpperCase() + label.slice(1) });
    }

    return options;
  };

  const monthOptions = generateMonthOptions();

  // Initialiser avec le mois actuel
  useEffect(() => {
    const now = new Date();
    const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    setSelectedMonth(currentMonth);
  }, []);

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedEmployees(new Set(employees.map(e => e.id)));
    } else {
      setSelectedEmployees(new Set());
    }
  };

  const handleSelect = (id: string, checked: boolean) => {
    const newSet = new Set(selectedEmployees);
    if (checked) {
      newSet.add(id);
    } else {
      newSet.delete(id);
    }
    setSelectedEmployees(newSet);
  };

  const handleGenerate = async () => {
    setIsLoading(true);
    setResults({ success: [], errors: [] });

    const [yearStr, monthStr] = selectedMonth.split('-');
    const year = parseInt(yearStr);
    const month = parseInt(monthStr);

    const successList: string[] = [];
    const errorsList: { id: string, name: string, error: string }[] = [];

    // Générer la paie pour chaque employé sélectionné
    for (const employeeId of Array.from(selectedEmployees)) {
      const employee = employees.find(e => e.id === employeeId);
      const employeeName = employee ? `${employee.first_name} ${employee.last_name}` : employeeId;

      try {
        const response = await apiClient.post('/api/actions/generate-payslip', {
          employee_id: employeeId,
          year,
          month
        });

        if (response.data.status === 'success') {
          successList.push(employeeName);
        } else {
          errorsList.push({
            id: employeeId,
            name: employeeName,
            error: response.data.message || 'Erreur inconnue'
          });
        }
      } catch (error: any) {
        const errorMessage = error.response?.data?.detail || error.message || 'Erreur inconnue';
        errorsList.push({
          id: employeeId,
          name: employeeName,
          error: errorMessage
        });
      }
    }

    setResults({ success: successList, errors: errorsList });
    setIsLoading(false);

    // Si toutes les générations ont réussi, fermer le modal après 2 secondes
    if (errorsList.length === 0) {
      setTimeout(() => {
        onClose();
      }, 2000);
    }
  };

  const isAllSelected = employees.length > 0 && selectedEmployees.size === employees.length;

  // Réinitialiser les résultats quand le modal s'ouvre
  useEffect(() => {
    if (isOpen) {
      setResults({ success: [], errors: [] });
    }
  }, [isOpen]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md p-0">
        <DialogHeader className="p-6 pb-4">
          <DialogTitle>Générer la Paie</DialogTitle>
        </DialogHeader>

        {/* Sélection du mois */}
        <div className="px-6 pb-4">
          <Label htmlFor="month-select" className="text-sm font-medium mb-2 block">
            Mois de paie
          </Label>
          <Select value={selectedMonth} onValueChange={setSelectedMonth}>
            <SelectTrigger id="month-select">
              <SelectValue placeholder="Sélectionner un mois" />
            </SelectTrigger>
            <SelectContent>
              {monthOptions.map(option => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Liste des employés */}
        <Command className="p-2">
          <CommandInput placeholder="Rechercher un employé..." />
          <CommandList className="max-h-[300px] overflow-y-auto">
            <CommandEmpty>Aucun employé trouvé.</CommandEmpty>
            <CommandGroup>
              <CommandItem
                onSelect={() => handleSelectAll(!isAllSelected)}
                className="flex items-center gap-3"
              >
                <Checkbox
                  checked={isAllSelected}
                  onCheckedChange={handleSelectAll}
                />
                <label className="font-medium">Tout sélectionner</label>
              </CommandItem>
              {employees.map(emp => (
                <CommandItem
                  key={emp.id}
                  value={`${emp.first_name} ${emp.last_name}`}
                  onSelect={() => handleSelect(emp.id, !selectedEmployees.has(emp.id))}
                  className="flex items-center gap-3"
                >
                  <Checkbox
                    checked={selectedEmployees.has(emp.id)}
                    onCheckedChange={(checked) => handleSelect(emp.id, !!checked)}
                  />
                  <label>{emp.first_name} {emp.last_name}</label>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>

        {/* Affichage des résultats */}
        {(results.success.length > 0 || results.errors.length > 0) && (
          <div className="px-6 pb-4 space-y-3">
            {results.success.length > 0 && (
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-sm font-semibold text-green-800 mb-2">
                  ✓ Générations réussies ({results.success.length})
                </p>
                <ul className="text-xs text-green-700 space-y-1">
                  {results.success.map((name, idx) => (
                    <li key={idx}>• {name}</li>
                  ))}
                </ul>
              </div>
            )}
            {results.errors.length > 0 && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm font-semibold text-red-800 mb-2">
                  ✗ Erreurs ({results.errors.length})
                </p>
                <ul className="text-xs text-red-700 space-y-2">
                  {results.errors.map((err, idx) => (
                    <li key={idx}>
                      <span className="font-medium">{err.name}:</span> {err.error}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <div className="p-6 pt-2 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            {results.success.length > 0 || results.errors.length > 0 ? 'Fermer' : 'Annuler'}
          </Button>
          <Button
            className="bg-cyan-500 hover:bg-cyan-600 text-white"
            onClick={handleGenerate}
            disabled={isLoading || selectedEmployees.size === 0 || !selectedMonth || results.success.length > 0 || results.errors.length > 0}
          >
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Générer ({selectedEmployees.size})
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}