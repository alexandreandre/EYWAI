import { useEffect, useState } from "react";
import apiClient from '@/api/apiClient';
import { useAuth } from "@/contexts/AuthContext";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { CopilotModalAgent } from "@/components/CopilotModalAgent";

// --- Composants Shadcn/UI ---
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Checkbox } from "@/components/ui/checkbox";
import { Kbd } from "@/components/ui/kbd";
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartConfig } from "@/components/ui/chart";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis, Legend, Tooltip as RechartsTooltip } from "recharts";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

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
  FlaskConical,
  FileDown,
  TrendingUp,
  Clock,
  Users,
  UsersRound,
  SlidersHorizontal,
  GraduationCap,
  Calculator,
  MessageSquare,
  UserMinus,
  Building,
  Calendar,
  FileText,
  ShieldCheck,
  Target,
  BookOpen,
  Award,
  Handshake,
  UserCog,
  ChevronDown,
  ClipboardList,
  Wallet,
} from "lucide-react";

// --- Formulaires (que tu as fournis) ---
import { NewEmployeeForm } from "@/components/forms/NewEmployeeForm";
// --- Alertes RIB ---
import * as ribAlertsApi from "@/api/ribAlerts";
import { CSEDashboardBlock } from "@/components/CSEDashboardBlock";
import { PendingSignaturesWidget } from "@/components/dashboard/PendingSignaturesWidget";
import TeamAnalyticsSection from "@/components/dashboard/TeamAnalyticsSection";
import { getMedicalSettings, getKPIs, type KPIs } from "@/api/medicalFollowUp";
import {
  ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS,
  countUpcomingPlannedAnnualReviews,
  getAllAnnualReviews,
} from "@/api/annualReviews";
import {
  countRecruitmentPriorityCandidates,
  isRecruitmentPriorityCandidate,
  getCandidates,
  getJobs,
  getRecruitmentSettings,
} from "@/api/recruitment";
import { useQuery } from "@tanstack/react-query";
import type { LucideIcon } from "lucide-react";
import { useRhSidebarTaskBadges } from "@/hooks/useRhSidebarTaskBadges";
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

interface PayrollVariablesSummary {
  pending_expense_reports: number;
  primes_saisies_count: number;
  heures_sup_heures_reference_month: number;
}

interface PayrollAlertsSummary {
  employees_without_iban: number;
  payslips_negative_net: number;
}

interface SalaryAdvancesMonthSummary {
  pending_count: number;
  pending_requested_total_eur: number;
  requested_in_calendar_month_count: number;
  requested_in_calendar_month_total_eur: number;
}

interface HeuresSupMonthSummary {
  hours_reference_month: number;
  hours_previous_month: number;
}

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
  payrollVariables: PayrollVariablesSummary;
  payrollAlerts: PayrollAlertsSummary;
  salaryAdvancesMonth: SalaryAdvancesMonthSummary;
  heuresSupMonths: HeuresSupMonthSummary;
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

/**
 * Poids pour le score de priorité : `score = count × poids` (plus haut = affiché avant).
 * À égalité de score, l’ordre d’origine dans `mainFocusCandidates` sert de départage.
 */
const PRIORITY_SCORE_WEIGHTS: Record<string, number> = {
  rates: 100,
  rib: 92,
  payroll: 88,
  exports: 48,
  saisies: 50,
  "salary-seizures": 48,
  "salary-advances": 46,
  leaves: 78,
  expenses: 72,
  medical: 68,
  residence: 64,
  annualReviews: 52,
  recruitment: 48,
  employees: 42,
  "employee-exits": 38,
  promotions: 28,
  simulation: 26,
  schedules: 18,
  "badgeuse-rh": 18,
  company: 12,
  cse: 14,
  users: 14,
};

function priorityScore(key: string, count: number): number {
  const w = PRIORITY_SCORE_WEIGHTS[key] ?? 15;
  return count * w;
}

function sortFocusCandidatesByScore<T extends { key: string; count: number }>(
  items: T[],
  sourceOrder: { key: string }[],
): T[] {
  const orderIdx = new Map(sourceOrder.map((c, i) => [c.key, i]));
  return [...items].sort((a, b) => {
    const diff = priorityScore(b.key, b.count) - priorityScore(a.key, a.count);
    if (diff !== 0) return diff;
    return (orderIdx.get(a.key) ?? 999) - (orderIdx.get(b.key) ?? 999);
  });
}

/** Tâches avec compteur > 0 triées par score, puis les entrées à 0 dans l’ordre d’origine (liste déroulante). */
function splitCandidatesForSelect<T extends { key: string; count: number }>(candidates: T[]): T[] {
  const positives = candidates.filter((c) => c.count > 0);
  const zeros = candidates.filter((c) => c.count <= 0);
  return [...sortFocusCandidatesByScore(positives, candidates), ...zeros];
}

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [residencePermitStats, setResidencePermitStats] = useState<ResidencePermitStats | null>(null);
  const [residencePermitLoading, setResidencePermitLoading] = useState(true);
  const [ribAlerts, setRibAlerts] = useState<ribAlertsApi.RibAlert[]>([]);
  const [ribAlertTotal, setRibAlertTotal] = useState(0);
  const [ribAlertsLoading, setRibAlertsLoading] = useState(true);
  const [medicalModuleEnabled, setMedicalModuleEnabled] = useState(false);
  const [medicalKpis, setMedicalKpis] = useState<KPIs | null>(null);
  const [medicalKpisLoading, setMedicalKpisLoading] = useState(true);
  const [annualReviewsUpcomingCount, setAnnualReviewsUpcomingCount] = useState(0);
  const [recruitmentPendingCount, setRecruitmentPendingCount] = useState(0);
  const [recruitmentPendingPreview, setRecruitmentPendingPreview] = useState<string | null>(null);

  const [isGeneratePayrollModalOpen, setIsGeneratePayrollModalOpen] = useState(false);
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const [selectedPriorityKey, setSelectedPriorityKey] = useState<DashboardPriorityKey | null>(null);
  const { getCount } = useRhSidebarTaskBadges(true);
  const location = useLocation();
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

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.get<DashboardData>('/api/dashboard/all');
        setData(response.data);
      } catch (e: any) {
        const errorMsg = e.response?.data?.detail || e.message || "Une erreur est survenue.";
        setError(errorMsg);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  useEffect(() => {
    if (loading || !data) return;
    if (location.hash !== "#paie-gestion") return;
    const timer = window.setTimeout(() => {
      document.getElementById("paie-gestion")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 150);
    return () => window.clearTimeout(timer);
  }, [loading, data, location.hash]);

  useEffect(() => {
    const fetchResidencePermitStats = async () => {
      try {
        setResidencePermitLoading(true);
        const response = await apiClient.get<ResidencePermitStats>('/api/dashboard/residence-permit-stats');
        setResidencePermitStats(response.data);
      } catch (e: any) {
        // En cas d'erreur, on garde les stats à null (la carte affichera 0)
        console.error("Erreur lors de la récupération des stats de titres de séjour:", e);
        setResidencePermitStats({
          total_expire: 0,
          total_a_renouveler: 0,
          total_a_renseigner: 0,
          total_valide: 0
        });
      } finally {
        setResidencePermitLoading(false);
      }
    };
    fetchResidencePermitStats();
  }, []);

  useEffect(() => {
    const fetchMedical = async () => {
      try {
        setMedicalKpisLoading(true);
        const settings = await getMedicalSettings();
        setMedicalModuleEnabled(settings.enabled);
        if (settings.enabled) {
          const kpis = await getKPIs();
          setMedicalKpis(kpis);
        } else {
          setMedicalKpis(null);
        }
      } catch {
        setMedicalModuleEnabled(false);
        setMedicalKpis(null);
      } finally {
        setMedicalKpisLoading(false);
      }
    };
    fetchMedical();
  }, []);

  useEffect(() => {
    const fetchRibAlerts = async () => {
      try {
        setRibAlertsLoading(true);
        const response = await ribAlertsApi.getRibAlerts({
          is_read: false,
          is_resolved: false,
          limit: 5,
        });
        setRibAlerts(response.data.alerts || []);
        setRibAlertTotal(typeof response.data.total === "number" ? response.data.total : (response.data.alerts || []).length);
      } catch (e: any) {
        console.error("Erreur lors de la récupération des alertes RIB:", e);
        setRibAlerts([]);
        setRibAlertTotal(0);
      } finally {
        setRibAlertsLoading(false);
      }
    };
    fetchRibAlerts();
  }, []);

  useEffect(() => {
    const fetchAnnualReviewsPriority = async () => {
      try {
        const response = await getAllAnnualReviews();
        setAnnualReviewsUpcomingCount(
          countUpcomingPlannedAnnualReviews(
            response.data || [],
            ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS,
          ),
        );
      } catch {
        setAnnualReviewsUpcomingCount(0);
      }
    };
    fetchAnnualReviewsPriority();
  }, []);

  useEffect(() => {
    const fetchRecruitmentPriority = async () => {
      try {
        const settings = await getRecruitmentSettings();
        if (!settings.enabled) {
          setRecruitmentPendingCount(0);
          setRecruitmentPendingPreview(null);
          return;
        }

        const candidates = await getCandidates();
        const pendingCount = countRecruitmentPriorityCandidates(candidates);
        const pending = candidates.filter(isRecruitmentPriorityCandidate);
        setRecruitmentPendingCount(pendingCount);

        if (pending.length > 0) {
          const preview = pending
            .slice(0, 2)
            .map((c) => `${c.first_name} ${c.last_name}`)
            .join(" · ");
          setRecruitmentPendingPreview(preview);
        } else {
          setRecruitmentPendingPreview(null);
        }
      } catch {
        setRecruitmentPendingCount(0);
        setRecruitmentPendingPreview(null);
      }
    };
    fetchRecruitmentPriority();
  }, []);

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
  if (loading) {
    return (
      <div className="flex justify-center items-center h-[calc(100vh-200px)]">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      </div>
    );
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
  const teamPendingTotal =
    data.alerts.expiringContracts + data.alerts.endOfTrialPeriods;
  const urgentTotal =
    data.actions.pendingAbsences +
    data.actions.pendingExpenses +
    data.alerts.obsoleteRates +
    teamPendingTotal +
    residencePendingTotal +
    annualReviewsUpcomingCount +
    recruitmentPendingCount +
    medicalPendingTotal +
    ribAlertTotal;

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
      href: "/annual-reviews",
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
    // Sous-parties connectées (même avec 0) pour préparer l’extension complète sidebar -> priorité du jour.
    {
      key: "employees",
      label: "Collaborateurs",
      count: getCount("/employees"),
      href: "/employees",
      icon: Users,
      hint: "Suivi des collaborateurs",
    },
    {
      key: "employee-exits",
      label: "Départs & sorties",
      count: getCount("/employee-exits"),
      href: "/employee-exits",
      icon: Users,
      hint: "Sorties à traiter",
    },
    {
      key: "schedules",
      label: "Calendriers",
      count: getCount("/schedules"),
      href: "/schedules",
      icon: Clock,
      hint: "Planning & suivi",
    },
    {
      key: "badgeuse-rh",
      label: "Badgeuse",
      count: getCount("/badgeuse-rh"),
      href: "/badgeuse-rh",
      icon: Clock,
      hint: "Pointages à vérifier",
    },
    {
      key: "company",
      label: "Mon Entreprise",
      count: getCount("/company"),
      href: "/company",
      icon: Briefcase,
      hint: "Paramètres société",
    },
    {
      key: "promotions",
      label: "Promotions",
      count: getCount("/promotions"),
      href: "/promotions",
      icon: TrendingUp,
      hint: "Dossiers de promotion",
    },
    {
      key: "cse",
      label: "CSE & Dialogue Social",
      count: getCount("/cse"),
      href: "/cse",
      icon: Users,
      hint: "Sujets sociaux",
    },
    {
      key: "users",
      label: "Gestion des Utilisateurs",
      count: getCount("/users"),
      href: "/users",
      icon: Users,
      hint: "Comptes et accès",
    },
    {
      key: "saisies",
      label: "Primes",
      count: getCount("/saisies"),
      href: "/saisies",
      icon: CreditCard,
      hint: "Éléments variables",
    },
    {
      key: "salary-seizures",
      label: "Saisies sur salaire",
      count: getCount("/salary-seizures"),
      href: "/salary-seizures",
      icon: CreditCard,
      hint: "Dossiers de saisies",
    },
    {
      key: "salary-advances",
      label: "Avances sur salaire",
      count: getCount("/salary-advances"),
      href: "/salary-advances",
      icon: CreditCard,
      hint: "Demandes d’avances",
    },
    {
      key: "simulation",
      label: "Simulation",
      count: getCount("/simulation"),
      href: "/simulation",
      icon: FlaskConical,
      hint: "Simulations bulletin",
    },
    {
      key: "exports",
      label: "Exports",
      count: getCount("/exports"),
      href: "/exports",
      icon: FileDown,
      hint: "Exports paie/RH",
    },
    {
      key: "payroll",
      label: "Paie",
      count: getCount("/payroll"),
      href: "/payroll",
      icon: CreditCard,
      hint: "Cycle de paie",
    },
  ];
  const availablePriorityItems = mainFocusCandidates.filter((item) => item.count > 0);
  const pendingPriorityItemsRaw = availablePriorityItems.filter(
    (item) => validatedPriorityByCount[item.key] !== item.count,
  );
  const pendingPriorityItems = sortFocusCandidatesByScore(pendingPriorityItemsRaw, mainFocusCandidates);
  const prioritySelectOrdered = splitCandidatesForSelect(mainFocusCandidates);
  const selectedPriorityItem =
    pendingPriorityItems.find((item) => item.key === selectedPriorityKey) ||
    pendingPriorityItems[0] ||
    null;
  const mainFocus = selectedPriorityItem;
  const remainingMainFocus = pendingPriorityItems.length > 1 ? pendingPriorityItems.length - 1 : 0;

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
    <div className="space-y-8 animate-fade-in motion-reduce:animate-none">
      <DashboardHeader
        firstName={user?.first_name || "Utilisateur"}
        onCopilotClick={() => setIsCopilotOpen(true)}
      />
      <div className="space-y-8">
        <Card className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
          <CardContent className="border-l-[3px] border-l-primary p-5 md:p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Priorité du jour
                </p>
                {mainFocus ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <mainFocus.icon className="h-5 w-5 text-primary" />
                    <p className="text-lg font-semibold tracking-tight text-foreground">
                      {mainFocus.label} ({mainFocus.count})
                    </p>
                    <Badge variant="secondary">{mainFocus.hint}</Badge>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center gap-2">
                    <PartyPopper className="h-5 w-5 text-accent" aria-hidden />
                    <p className="text-lg font-semibold tracking-tight text-foreground">
                      Aucun blocage prioritaire détecté
                    </p>
                  </div>
                )}
                <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
                  Traitez d’abord ce qui bloque la paie, les demandes ou la conformité — le reste peut attendre.
                  L’ordre affiché combine le <span className="font-medium text-foreground/90">nombre de dossiers</span> et une{" "}
                  <span className="font-medium text-foreground/90">pondération métier</span> (taux et paie en tête, puis
                  validations courantes, etc.).
                </p>
                {pendingPriorityItems.length > 0 && (
                  <div className="pt-1 max-w-md">
                    <Label className="text-xs text-muted-foreground">Voir toutes les tâches</Label>
                    <Select
                      value={selectedPriorityItem?.key}
                      onValueChange={(value) => setSelectedPriorityKey(value as DashboardPriorityKey)}
                    >
                      <SelectTrigger className="mt-1 h-9">
                        <SelectValue placeholder="Choisir une tâche" />
                      </SelectTrigger>
                      <SelectContent>
                        {prioritySelectOrdered.map((task) => (
                          <SelectItem key={task.key} value={task.key} disabled={task.count <= 0}>
                            {task.label} ({task.count})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                {mainFocus && (
                  <p className="text-xs text-muted-foreground pt-1">
                    {remainingMainFocus > 0
                      ? `${remainingMainFocus} étape${remainingMainFocus > 1 ? "s" : ""} restante${remainingMainFocus > 1 ? "s" : ""}.`
                      : "Dernière étape restante."}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {mainFocus ? (
                  <>
                    <Button asChild>
                      <Link to={mainFocus.href}>Ouvrir le module</Link>
                    </Button>
                    <Button
                      type="button"
                      className="bg-accent text-accent-foreground hover:bg-accent/90"
                      onClick={handleValidateAndNext}
                    >
                      Valider et passer à l'étape suivante
                    </Button>
                  </>
                ) : (
                  <Button variant="outline" type="button" onClick={handleResetPriorities}>
                    Réinitialiser les priorités
                  </Button>
                )}
                {availablePriorityItems.length > 0 && Object.keys(validatedPriorityByCount).length > 0 && (
                  <Button variant="ghost" type="button" onClick={handleResetPriorities}>
                    Reprendre depuis le début
                  </Button>
                )}
                <Button
                  variant="ghost"
                  type="button"
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => setIsCopilotOpen(true)}
                >
                  <Sparkles className="mr-1.5 h-4 w-4 text-primary" />
                  Aide IA
                </Button>
              </div>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border bg-border md:grid-cols-4">
              <div className="bg-muted/40 px-3 py-3 md:px-4">
                <p className="text-xs font-medium text-muted-foreground">Total à traiter</p>
                <p className="mt-1 text-xl font-semibold tabular-nums text-foreground">{urgentTotal}</p>
              </div>
              <div className="bg-muted/40 px-3 py-3 md:px-4">
                <p className="text-xs font-medium text-muted-foreground">Paie &amp; conformité</p>
                <p className="mt-1 text-xl font-semibold tabular-nums text-foreground">
                  {data.actions.pendingAbsences + data.actions.pendingExpenses + data.alerts.obsoleteRates}
                </p>
              </div>
              <div className="bg-muted/40 px-3 py-3 md:px-4">
                <p className="text-xs font-medium text-muted-foreground">Équipe</p>
                <p className="mt-1 text-xl font-semibold tabular-nums text-foreground">{teamPendingTotal}</p>
              </div>
              <div className="bg-muted/40 px-3 py-3 md:px-4">
                <p className="text-xs font-medium text-muted-foreground">Admin RH</p>
                <p className="mt-1 text-xl font-semibold tabular-nums text-foreground">
                  {residencePendingTotal + ribAlertTotal + medicalPendingTotal}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* EYWAI Team : à traiter, accès modules, synthèse, formation (accordéon), pilotage, dialogue social */}
        <section className="space-y-5 rounded-lg border border-border bg-card p-5 md:p-6">
          <header className="space-y-1 border-b border-border/80 pb-4">
            <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
              <Users className="h-5 w-5 shrink-0 text-primary" aria-hidden />
              EYWAI Team
            </h2>
            <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Suivi des collaborateurs, validations, titres, suivi médical, formation et dialogue social.
            </p>
          </header>

          <TeamSectionHeading
            title="À traiter"
            description="Demandes d’absences et de notes de frais, puis alertes RIB, titres de séjour et suivi des visites médicales. Les taux de cotisations obsolètes sont indiqués dans la zone EYWAI Paie."
          />
          <div className="space-y-4 rounded-lg border border-border/80 bg-muted/20 p-4 md:p-5">
            <NotificationsCard actions={data.actions} alerts={data.alerts} showRatesLink={false} />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <RibAlertsCard
                alerts={ribAlerts}
                loading={ribAlertsLoading}
                onRefresh={() => {
                  ribAlertsApi
                    .getRibAlerts({ is_read: false, is_resolved: false, limit: 5 })
                    .then((r) => {
                      setRibAlerts(r.data.alerts || []);
                      setRibAlertTotal(
                        typeof r.data.total === "number" ? r.data.total : (r.data.alerts || []).length,
                      );
                    });
                }}
              />
              <ResidencePermitCard stats={residencePermitStats} loading={residencePermitLoading} />
            </div>
            {medicalModuleEnabled ? (
              <MedicalFollowUpCard kpis={medicalKpis} loading={medicalKpisLoading} />
            ) : (
              <Card className="border-dashed">
                <CardHeader>
                  <CardTitle className="text-base">Suivi médical</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">Module non activé pour cette entreprise.</p>
                </CardContent>
              </Card>
            )}
          </div>

          <TeamSectionHeading
            title="Accès modules"
            description="Raccourcis vers les écrans EYWAI Team, regroupés par pôle (administratif, temps et activité, développement, relations)."
          />
          <TeamQuickAccessCard />

          <TeamSectionHeading
            title="Synthèse collaborateurs"
            description="Effectif actif et alertes administratives prioritaires sur la liste des collaborateurs."
          />
          <CollaborateursKpiCard kpis={data.kpis} alerts={data.alerts} />

          <FormationTalentsDashboardWidget />

          <TeamSectionHeading
            title="Pilotage équipe"
            description="Répartition, effectif du jour, recrutement actif et analyses d’équipe."
          />
          <div className="space-y-6">
            <EffectifCard kpis={data.kpis} absentsToday={data.teamPulse?.absentToday || []} />
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <GenderSplitCard kpis={data.kpis} />
              <ContractSplitCard kpis={data.kpis} />
            </div>
            <RecruitmentKpisCard />
            <TeamAnalyticsSection />
          </div>

          <TeamSectionHeading
            title="Dialogue social et personnalisation"
            description="Instance du personnel, CSE et réglages d’affichage de votre tableau de bord."
          />
          <div className="space-y-6">
            <CSEDashboardBlock />
            <DashboardPersonnalisationCard />
          </div>
        </section>

        {/* EYWAI Paie : gestion → blocages (signatures, taux, variables) → coûts & analyses → raccourcis */}
        <section className="space-y-5 rounded-lg border border-border bg-card p-5 md:p-6">
          <header className="space-y-1 border-b border-border/80 pb-4">
            <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
              <Calculator className="h-5 w-5 shrink-0 text-primary" aria-hidden />
              EYWAI Paie
            </h2>
            <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Cycle de paie, signatures et taux à jour, variables et alertes, puis pilotage des coûts et raccourcis en bas de page.
            </p>
          </header>

          <div id="paie-gestion" className="scroll-mt-24">
            <PayrollCard
              status={data.payrollStatus}
              onGenerateClick={() => setIsGeneratePayrollModalOpen(true)}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <PendingSignaturesWidget mode="rh" />
            <PaieRatesAlertCard obsoleteRates={data.alerts.obsoleteRates} />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <PayrollVariablesCard data={data} />
            <PayrollAlertsDashboardCard data={data} />
            <SalaryAdvancesDashboardCard data={data} />
          </div>

          <div className="space-y-6">
            <CoutsCard kpis={data.kpis} chartData={data.chartData} />
            <PrevisionMasseSalarialeCard kpis={data.kpis} />
            <HeuresSupKpiCard hs={data.heuresSupMonths} variablesHsHours={data.payrollVariables.heures_sup_heures_reference_month} />
            <ShortcutsCard />
          </div>
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
  const [open, setOpen] = useState(false);
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
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className="overflow-hidden border-border shadow-none">
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-start justify-between gap-3 px-6 py-5 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <div className="min-w-0 space-y-1">
              <div className="flex items-center gap-2 text-base font-semibold tracking-tight text-foreground">
                <GraduationCap className="h-5 w-5 shrink-0 text-primary" aria-hidden />
                Formation et talents
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                Indicateurs Pack Talent — cliquez pour afficher ou masquer le détail, ou ouvrez le module formation.
              </p>
            </div>
            <ChevronDown
              className={cn(
                "mt-0.5 h-5 w-5 shrink-0 text-muted-foreground transition-transform duration-200",
                open && "rotate-180",
              )}
              aria-hidden
            />
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="border-t pt-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <button
            type="button"
            onClick={() => navigate("/formation#habilitations")}
            className="flex flex-col rounded-lg border border-border bg-background p-3 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
            onClick={() => navigate("/formation#habilitations")}
            className="flex flex-col rounded-lg border border-border bg-background p-3 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
            onClick={() => navigate("/formation#budget")}
            className="flex flex-col rounded-lg border border-border bg-background p-3 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
            onClick={() => navigate("/formation#obligations")}
            className="flex flex-col rounded-lg border border-border bg-background p-3 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
            onClick={() => navigate("/formation#objectifs")}
            className="flex flex-col rounded-lg border border-border bg-background p-3 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

// --- Section 1: Header & Copilote ---
function DashboardHeader({ firstName, onCopilotClick }: { firstName: string; onCopilotClick: () => void }) {
  const dateLabel = new Intl.DateTimeFormat("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date());

  return (
    <header className="flex flex-col gap-6 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div className="space-y-1">
        <p className="text-xs font-medium capitalize text-muted-foreground">{dateLabel}</p>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          Bonjour {firstName}
        </h1>
        <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
          Synthèse des tâches, alertes et indicateurs pour votre périmètre RH.
        </p>
      </div>
      <Button
        variant="outline"
        size="default"
        className="shrink-0 gap-2 border-primary/25 bg-background hover:bg-primary/5 hover:border-primary/40"
        onClick={onCopilotClick}
      >
        <Sparkles className="h-4 w-4 text-primary" aria-hidden />
        <span className="font-medium">Assistant IA</span>
        <Kbd className="pointer-events-none hidden sm:inline-flex text-[10px]">⌘K</Kbd>
      </Button>
    </header>
  );
}

// --- Section 2: Centre d'Actions ---

function PayrollCard({ status, onGenerateClick }: { status: DashboardData['payrollStatus'], onGenerateClick: () => void }) {
  return (
    <Card className="border-border shadow-none">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold tracking-tight">Gestion de la paie</CardTitle>
      </CardHeader>
      <CardContent>
        <button
          type="button"
          onClick={onGenerateClick}
          className="group flex w-full items-center justify-center gap-2 rounded-md border border-border bg-background px-4 py-3 transition-colors hover:border-primary/35 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          <Sparkles className="h-5 w-5 shrink-0 text-primary transition-colors group-hover:text-primary/90" aria-hidden />
          <span className="text-sm font-medium text-foreground">Générer la paie</span>
        </button>
        <p className="mt-3 text-xs text-muted-foreground">
          Période <span className="font-medium text-foreground">{status.currentMonth}</span>
          {" · "}
          Étape {status.step}/{status.totalSteps}
        </p>
      </CardContent>
    </Card>
  );
}

function NotificationsCard({
  actions,
  alerts,
  showRatesLink = true,
}: {
  actions: ActionItems;
  alerts: AlertItems;
  showRatesLink?: boolean;
}) {
  const navigate = useNavigate();
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Demandes à valider</CardTitle>
        <p className="text-xs text-muted-foreground">
          Absences et notes de frais en attente de validation. Les autres alertes (RIB, titres, visites médicales, taux de cotisations…) sont affichées dans ce bloc ou sous EYWAI Paie.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <button
          type="button"
          onClick={() => navigate("/leaves")}
          className="flex w-full items-center justify-between rounded-lg p-3 transition-colors hover:bg-muted"
        >
          <div className="flex items-center">
            <CalendarCheck
              className={`mr-3 h-5 w-5 ${actions.pendingAbsences > 0 ? "text-red-500" : "text-foreground"}`}
            />
            <span
              className={`font-medium ${actions.pendingAbsences > 0 ? "text-red-500" : "text-foreground"}`}
            >
              Demandes d'absences
            </span>
          </div>
          <div className="flex items-center">
            <Badge
              className={actions.pendingAbsences > 0 ? "bg-red-500 text-white" : "bg-muted text-foreground"}
            >
              {actions.pendingAbsences}
            </Badge>
            <ChevronRight className="ml-2 h-4 w-4 text-muted-foreground" />
          </div>
        </button>
        <button
          type="button"
          onClick={() => navigate("/expenses")}
          className="flex w-full items-center justify-between rounded-lg p-3 transition-colors hover:bg-muted"
        >
          <div className="flex items-center">
            <CreditCard
              className={`mr-3 h-5 w-5 ${actions.pendingExpenses > 0 ? "text-red-500" : "text-foreground"}`}
            />
            <span className={`font-medium ${actions.pendingExpenses > 0 ? "text-red-500" : "text-foreground"}`}>
              Notes de frais
            </span>
          </div>
          <div className="flex items-center">
            <Badge
              className={actions.pendingExpenses > 0 ? "bg-red-500 text-white" : "bg-muted text-foreground"}
            >
              {actions.pendingExpenses}
            </Badge>
            <ChevronRight className="ml-2 h-4 w-4 text-muted-foreground" />
          </div>
        </button>
        {showRatesLink && (
          <button
            type="button"
            onClick={() => navigate("/rates")}
            className="flex w-full items-center justify-between rounded-lg p-3 transition-colors hover:bg-muted"
          >
            <div className="flex items-center">
              <FileWarning
                className={`mr-3 h-5 w-5 ${alerts.obsoleteRates > 0 ? "text-red-500" : "text-foreground"}`}
              />
              <span className={`font-medium ${alerts.obsoleteRates > 0 ? "text-red-500" : "text-foreground"}`}>
                Taux de cotisations
              </span>
            </div>
            <div className="flex items-center">
              <Badge
                className={alerts.obsoleteRates > 0 ? "bg-red-500 text-white" : "bg-muted text-foreground"}
              >
                {alerts.obsoleteRates}
              </Badge>
              <ChevronRight className="ml-2 h-4 w-4 text-muted-foreground" />
            </div>
          </button>
        )}
      </CardContent>
    </Card>
  );
}

/** Carte « taux obsolètes » — affichée dans EYWAI Paie lorsque les notifications Team masquent le lien taux. */
function PaieRatesAlertCard({ obsoleteRates }: { obsoleteRates: number }) {
  const navigate = useNavigate();
  const hasAlert = obsoleteRates > 0;
  const allUp = obsoleteRates <= 0;
  return (
    <Card
      className={
        hasAlert
          ? "border-orange-200 bg-orange-50/30"
          : allUp
            ? "border-emerald-200 bg-emerald-50/35"
            : ""
      }
    >
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <TrendingUp className="h-4 w-4 text-primary" aria-hidden />
          Taux de cotisations
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {allUp ? "Aucun taux obsolète détecté." : "Taux obsolètes à mettre à jour avant clôture."}
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {allUp ? (
          <p className="text-sm font-semibold text-emerald-800">Tout est à jour</p>
        ) : (
          <Badge className="w-fit bg-red-600 text-white">{obsoleteRates}</Badge>
        )}
        <Button type="button" size="sm" variant="outline" onClick={() => navigate("/rates")}>
          Ouvrir le module
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </CardContent>
    </Card>
  );
}

function formatEurCompact(amount: number) {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function PayrollVariablesCard({ data }: { data: DashboardData }) {
  const navigate = useNavigate();
  const v = data.payrollVariables;
  const moisCourant = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" }).format(new Date());
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <ClipboardList className="h-4 w-4 text-primary" aria-hidden />
          Variables de paie à suivre
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Notes de frais, primes saisies et heures sup. sur les bulletins du mois {data.kpis.currentMonth}.
        </p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <button
          type="button"
          onClick={() => navigate("/expenses")}
          className="flex w-full items-center justify-between rounded-lg border border-border/80 bg-muted/20 px-3 py-2 text-left transition-colors hover:bg-muted/50"
        >
          <span className="text-muted-foreground">Notes de frais à valider</span>
          <span className="font-semibold tabular-nums text-foreground">{v.pending_expense_reports}</span>
        </button>
        <button
          type="button"
          onClick={() => navigate("/saisies")}
          className="flex w-full items-center justify-between rounded-lg border border-border/80 bg-muted/20 px-3 py-2 text-left transition-colors hover:bg-muted/50"
        >
          <span className="text-muted-foreground">Primes saisies ({moisCourant})</span>
          <span className="font-semibold tabular-nums text-foreground">{v.primes_saisies_count}</span>
        </button>
        <div className="flex items-center justify-between rounded-lg border border-border/80 bg-muted/20 px-3 py-2">
          <span className="text-muted-foreground">Heures sup. (bulletins {data.kpis.currentMonth})</span>
          <span className="font-semibold tabular-nums text-foreground">
            {v.heures_sup_heures_reference_month.toLocaleString("fr-FR", {
              minimumFractionDigits: 0,
              maximumFractionDigits: 1,
            })}{" "}
            h
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function PayrollAlertsDashboardCard({ data }: { data: DashboardData }) {
  const navigate = useNavigate();
  const a = data.payrollAlerts;
  const hasIssue = a.employees_without_iban > 0 || a.payslips_negative_net > 0;
  return (
    <Card className={hasIssue ? "border-red-200 bg-red-50/25" : ""}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <AlertTriangle className={`h-4 w-4 ${hasIssue ? "text-red-600" : "text-muted-foreground"}`} aria-hidden />
          Alertes paie
        </CardTitle>
        <p className="text-xs text-muted-foreground">Points bloquants avant exports ou génération.</p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center justify-between rounded-lg border border-border/80 px-3 py-2">
          <span className="text-muted-foreground">Salariés sans RIB</span>
          <span className={a.employees_without_iban > 0 ? "font-bold text-red-600 tabular-nums" : "font-semibold tabular-nums"}>
            {a.employees_without_iban}
          </span>
        </div>
        <div className="flex items-center justify-between rounded-lg border border-border/80 px-3 py-2">
          <span className="text-muted-foreground">Bulletins au net négatif</span>
          <span className={a.payslips_negative_net > 0 ? "font-bold text-red-600 tabular-nums" : "font-semibold tabular-nums"}>
            {a.payslips_negative_net}
          </span>
        </div>
        <Button type="button" size="sm" variant="outline" className="w-full" onClick={() => navigate("/exports")}>
          Exports et anomalies
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </CardContent>
    </Card>
  );
}

function SalaryAdvancesDashboardCard({ data }: { data: DashboardData }) {
  const navigate = useNavigate();
  const s = data.salaryAdvancesMonth;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <Wallet className="h-4 w-4 text-primary" aria-hidden />
          Acomptes et avances
        </CardTitle>
        <p className="text-xs text-muted-foreground">Demandes en attente et volume demandé sur le mois civil.</p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center justify-between rounded-lg border border-border/80 px-3 py-2">
          <span className="text-muted-foreground">Demandes en attente</span>
          <span className="font-semibold tabular-nums">{s.pending_count}</span>
        </div>
        <div className="flex items-center justify-between rounded-lg border border-border/80 px-3 py-2">
          <span className="text-muted-foreground">Montant demandé (en attente)</span>
          <span className="font-semibold tabular-nums">{formatEurCompact(s.pending_requested_total_eur)}</span>
        </div>
        <div className="flex items-center justify-between rounded-lg border border-border/80 px-3 py-2">
          <span className="text-muted-foreground">Demandes créées ce mois</span>
          <span className="font-semibold tabular-nums">
            {s.requested_in_calendar_month_count} · {formatEurCompact(s.requested_in_calendar_month_total_eur)}
          </span>
        </div>
        <Button type="button" size="sm" variant="outline" className="w-full" onClick={() => navigate("/salary-advances")}>
          Ouvrir les avances sur salaire
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </CardContent>
    </Card>
  );
}

/** Synthèse collaborateurs alignée avec la sidebar (effectif + alertes contrats / fins d'essai). */
function CollaborateursKpiCard({ kpis, alerts }: { kpis: KpiData; alerts: AlertItems }) {
  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 space-y-0 pb-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="text-lg font-semibold">Collaborateurs</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            Effectif actif et alertes administratives (contrats, fins d&apos;essai).
          </p>
        </div>
        <Button size="sm" asChild className="shrink-0">
          <Link to="/employees">Voir la liste</Link>
        </Button>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-muted/30 px-3 py-3 text-center">
            <p className="text-xs font-medium text-muted-foreground">Effectif actif</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{kpis.effectifActif}</p>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 px-3 py-3 text-center">
            <p className="text-xs font-medium text-muted-foreground">Contrats à surveiller</p>
            <p
              className={`mt-1 text-2xl font-semibold tabular-nums ${alerts.expiringContracts > 0 ? "text-orange-600" : "text-foreground"}`}
            >
              {alerts.expiringContracts}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 px-3 py-3 text-center">
            <p className="text-xs font-medium text-muted-foreground">Fins d&apos;essai</p>
            <p
              className={`mt-1 text-2xl font-semibold tabular-nums ${alerts.endOfTrialPeriods > 0 ? "text-orange-600" : "text-foreground"}`}
            >
              {alerts.endOfTrialPeriods}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

type TeamQuickLink = { to: string; label: string; icon: LucideIcon };

type TeamQuickAccessBlock =
  | { type: "buttons"; links: TeamQuickLink[] }
  | { type: "formationCatalogue"; label: string; links: [TeamQuickLink, TeamQuickLink] };

type TeamQuickAccessPole = {
  title: string;
  description: string;
  blocks: TeamQuickAccessBlock[];
};

const TEAM_QUICK_ACCESS_POLES: TeamQuickAccessPole[] = [
  {
    title: "Gestion administrative et vie du salarié",
    description: "Identité, dossiers et mouvements de personnel (tâches de fond).",
    blocks: [
      {
        type: "buttons",
        links: [
          { to: "/employees", label: "Collaborateurs", icon: Users },
          { to: "/teams", label: "Équipes", icon: UsersRound },
          { to: "/employee-exits", label: "Départs & sorties", icon: UserMinus },
          { to: "/documents", label: "Documents", icon: FileText },
          { to: "/company", label: "Mon entreprise", icon: Building },
        ],
      },
    ],
  },
  {
    title: "Temps, activité et opérationnel",
    description: "Suivi du temps, des plannings et des habilitations au quotidien.",
    blocks: [
      {
        type: "buttons",
        links: [
          { to: "/badgeuse-rh", label: "Badgeuse", icon: Clock },
          { to: "/schedules", label: "Calendriers", icon: Calendar },
          { to: "/habilitations", label: "Habilitations", icon: ShieldCheck },
        ],
      },
    ],
  },
  {
    title: "Développement et performance",
    description: "Développement des compétences, pilotage de la performance et évolution des collaborateurs.",
    blocks: [
      {
        type: "buttons",
        links: [
          { to: "/annual-reviews", label: "Entretiens", icon: MessageSquare },
          { to: "/objectives", label: "Objectifs & KPI", icon: Target },
        ],
      },
      {
        type: "formationCatalogue",
        label: "Formation et catalogue",
        links: [
          { to: "/formation", label: "Formation", icon: GraduationCap },
          { to: "/catalogue-formations", label: "Catalogue formations", icon: BookOpen },
        ],
      },
      {
        type: "buttons",
        links: [{ to: "/promotions", label: "Promotions", icon: Award }],
      },
    ],
  },
  {
    title: "Relations et recrutement",
    description: "Candidats, dialogue social et droits d’accès à la plateforme.",
    blocks: [
      {
        type: "buttons",
        links: [
          { to: "/recruitment", label: "Recrutement", icon: UserPlus },
          { to: "/cse", label: "CSE & Dialogue social", icon: Handshake },
          { to: "/users", label: "Utilisateurs", icon: UserCog },
        ],
      },
    ],
  },
];

function TeamQuickLinkButton({ to, label, icon: Icon, navigate }: TeamQuickLink & { navigate: ReturnType<typeof useNavigate> }) {
  return (
    <Button
      type="button"
      variant="outline"
      className="h-auto justify-between gap-2 py-3 font-normal"
      onClick={() => navigate(to)}
    >
      <span className="flex min-w-0 items-center gap-2">
        <Icon className="h-4 w-4 shrink-0 text-primary" aria-hidden />
        <span className="truncate text-left text-sm font-medium">{label}</span>
      </span>
      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
    </Button>
  );
}

function TeamSectionHeading({ title, description }: { title: string; description: string }) {
  return (
    <div className="space-y-1 border-b border-border/60 pb-2">
      <h3 className="text-sm font-semibold tracking-tight text-foreground">{title}</h3>
      <p className="max-w-3xl text-xs leading-relaxed text-muted-foreground">{description}</p>
    </div>
  );
}

function TeamQuickAccessCard() {
  const navigate = useNavigate();
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold">Accès rapides équipe</CardTitle>
        <p className="text-xs text-muted-foreground">
          Raccourcis regroupés par pôle : administratif, temps et activité, développement, relations et recrutement.
        </p>
      </CardHeader>
      <CardContent className="space-y-8">
        {TEAM_QUICK_ACCESS_POLES.map((pole) => (
          <div key={pole.title} className="space-y-3">
            <div className="space-y-1">
              <h4 className="text-sm font-semibold tracking-tight text-foreground">{pole.title}</h4>
              <p className="max-w-3xl text-xs leading-relaxed text-muted-foreground">{pole.description}</p>
            </div>
            <div className="space-y-3">
              {pole.blocks.map((block, blockIndex) => {
                if (block.type === "formationCatalogue") {
                  return (
                    <div
                      key={`${pole.title}-formation-${blockIndex}`}
                      className="rounded-lg border border-border/80 bg-muted/20 p-3"
                    >
                      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                        {block.label}
                      </p>
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        {block.links.map((link) => (
                          <TeamQuickLinkButton key={link.to} {...link} navigate={navigate} />
                        ))}
                      </div>
                    </div>
                  );
                }
                return (
                  <div
                    key={`${pole.title}-grid-${blockIndex}`}
                    className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
                  >
                    {block.links.map((link) => (
                      <TeamQuickLinkButton key={link.to} {...link} navigate={navigate} />
                    ))}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
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
      {!loading && (
        <CardFooter className="border-t pt-4">
          <Button variant="outline" size="sm" className="w-full sm:w-auto" asChild>
            <Link to="/residence-permits">
              Ouvrir les titres et documents
              <ChevronRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
        </CardFooter>
      )}
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
      console.error(e);
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

// --- Répartition Homme / Femme ---
function GenderSplitCard({ kpis }: { kpis: KpiData }) {
  const hommes = kpis.hommesCount ?? null;
  const femmes = kpis.femmesCount ?? null;
  const hasData = hommes != null && femmes != null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Users className="h-4 w-4 text-muted-foreground" />
          Répartition Homme / Femme
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!hasData ? (
          <p className="text-sm text-muted-foreground">Non renseigné</p>
        ) : (
          <div className="flex gap-6">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-blue-500" />
              <span className="text-sm font-medium">Hommes</span>
              <span className="font-bold text-foreground">{hommes}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-pink-500" />
              <span className="text-sm font-medium">Femmes</span>
              <span className="font-bold text-foreground">{femmes}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// --- Répartition CDD / CDI / Alternant / Stagiaire / Handicapé ---
const CONTRACT_LABELS: Record<string, string> = {
  CDI: "CDI",
  CDD: "CDD",
  Alternance: "Alternant",
  Stage: "Stagiaire",
  Intérim: "Intérim",
  Freelance: "Freelance",
  Autre: "Autre",
};

function ContractSplitCard({ kpis }: { kpis: KpiData }) {
  const dist = kpis.contractDistribution || {};
  const handicap = kpis.handicapesCount ?? 0;
  const types = ["CDI", "CDD", "Alternance", "Stage"].filter((t) => (dist[t] ?? 0) > 0);
  const otherKeys = Object.keys(dist).filter((k) => !["CDI", "CDD", "Alternance", "Stage"].includes(k));
  const hasAny = types.length > 0 || otherKeys.length > 0 || handicap > 0;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Briefcase className="h-4 w-4 text-muted-foreground" />
          Répartition contrats
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!hasAny ? (
          <p className="text-sm text-muted-foreground">Aucune donnée</p>
        ) : (
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
            {types.map((t) => (
              <span key={t} className="font-medium text-foreground">
                {CONTRACT_LABELS[t] ?? t}: <span className="font-bold">{dist[t] ?? 0}</span>
              </span>
            ))}
            {otherKeys.map((t) => (
              <span key={t} className="font-medium text-foreground">
                {CONTRACT_LABELS[t] ?? t}: <span className="font-bold">{dist[t] ?? 0}</span>
              </span>
            ))}
            {handicap > 0 && (
              <span className="font-medium text-foreground">
                Handicapé: <span className="font-bold">{handicap}</span>
              </span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// --- KPI Heures sup. (volume sur bulletins, comparaison M vs M-1) ---
function HeuresSupKpiCard({
  hs,
  variablesHsHours,
}: {
  hs: HeuresSupMonthSummary;
  variablesHsHours: number;
}) {
  const ref = hs.hours_reference_month;
  const prev = hs.hours_previous_month;
  const diff = ref - prev;
  const pct = prev !== 0 ? (diff / prev) * 100 : null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          Heures supplémentaires (bulletins)
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Somme des heures sur les lignes « heures suppl. » des bulletins — même base que la carte variables.
        </p>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-2xl font-bold tabular-nums text-foreground">
          {ref.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} h
        </p>
        <p className="text-xs text-muted-foreground">
          Mois précédent (M-1) :{" "}
          <span className="font-medium text-foreground">
            {prev.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} h
          </span>
          {pct != null && Number.isFinite(pct) ? (
            <>
              {" "}
              · variation{" "}
              <span className={diff > 0 ? "text-orange-600" : diff < 0 ? "text-emerald-700" : "text-foreground"}>
                {diff >= 0 ? "+" : ""}
                {pct.toFixed(0)} %
              </span>
            </>
          ) : prev === 0 && ref > 0 ? (
            <span className="text-orange-600"> · nouveau volume sur M-1</span>
          ) : null}
        </p>
        <p className="text-[11px] text-muted-foreground">
          Recoupement variables : {variablesHsHours.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} h (mois
          KPI).
        </p>
      </CardContent>
    </Card>
  );
}

// --- KPIs Recrutement ---
function RecruitmentKpisCard() {
  const navigate = useNavigate();
  const { data: settings } = useQuery({ queryKey: ["recruitment", "settings"], queryFn: getRecruitmentSettings });
  const enabled = !!settings?.enabled;
  const { data: jobs = [], isSuccess: jobsOk } = useQuery({
    queryKey: ["recruitment", "jobs"],
    queryFn: () => getJobs("active"),
    enabled,
  });
  const { data: candidates = [], isSuccess: candidatesOk } = useQuery({
    queryKey: ["recruitment", "candidates"],
    queryFn: () => getCandidates(),
    enabled,
  });
  const inProgress = candidates.filter((c) => c.current_stage_type !== "hired" && c.current_stage_type !== "rejected").length;
  const hired = candidates.filter((c) => c.current_stage_type === "hired").length;
  if (!settings?.enabled) return null;
  if (jobsOk && candidatesOk && jobs.length === 0 && candidates.length === 0) return null;
  return (
    <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate("/recruitment")}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <UserPlus className="h-4 w-4 text-muted-foreground" />
          Recrutement
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2 text-sm">
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

// --- Prévision masse salariale ---
function PrevisionMasseSalarialeCard({ kpis }: { kpis: KpiData }) {
  const navigate = useNavigate();
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
          Prévision masse salariale
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-2">
          Évolution et pilotage de la masse salariale (effectif, coûts).
        </p>
        <Button variant="outline" size="sm" onClick={() => navigate("/company")}>
          Voir la fiche entreprise
          <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </CardContent>
    </Card>
  );
}

function ShortcutsCard() {
  const navigate = useNavigate();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4" />
          Raccourcis paie
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-1">
          Simulation, saisie bulletin, exports. Les taux de cotisations sont rappelés dans le bloc du dessus.
        </p>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <button
          type="button"
          onClick={() => navigate("/simulation")}
          className="flex w-full items-center justify-between rounded-lg border border-border/60 p-3 text-left transition-colors hover:bg-muted"
        >
          <span className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 shrink-0 text-indigo-500" />
            <span className="font-medium text-sm">Simulation bulletin</span>
          </span>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        </button>
        <button
          type="button"
          onClick={() => navigate("/payroll")}
          className="flex w-full items-center justify-between rounded-lg border border-border/60 p-3 text-left transition-colors hover:bg-muted"
        >
          <span className="flex items-center gap-2">
            <CreditCard className="h-4 w-4 shrink-0 text-cyan-500" />
            <span className="font-medium text-sm">Saisie paie</span>
          </span>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        </button>
        <button
          type="button"
          onClick={() => navigate("/exports")}
          className="flex w-full items-center justify-between rounded-lg border border-border/60 p-3 text-left transition-colors hover:bg-muted"
        >
          <span className="flex items-center gap-2">
            <FileDown className="h-4 w-4 shrink-0 text-emerald-500" />
            <span className="font-medium text-sm">Exports et anomalies</span>
          </span>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        </button>
      </CardContent>
    </Card>
  );
}

// --- Personnalisation dashboard ---
function DashboardPersonnalisationCard() {
  return (
    <Card className="border-dashed">
      <CardContent className="p-4 flex items-center gap-3">
        <SlidersHorizontal className="h-5 w-5 text-muted-foreground" />
        <div>
          <p className="font-medium text-sm text-foreground">Personnalisation du dashboard</p>
          <p className="text-xs text-muted-foreground">Choisir les blocs affichés (bientôt)</p>
        </div>
      </CardContent>
    </Card>
  );
}

// --- Section 3: Carte Effectif condensée ---

function EffectifCard({ kpis, absentsToday }: { kpis: KpiData, absentsToday: TeamPulseEmployee[] }) {
  const getAbsenceIcon = (status: string) => {
    if (status.includes('Maladie')) return <HeartPulse className="h-3 w-3 text-red-500" />;
    if (status.includes('Congé')) return <Plane className="h-3 w-3 text-blue-500" />;
    if (status.includes('RTT')) return <CalendarCheck className="h-3 w-3 text-purple-500" />;
    return <CalendarCheck className="h-3 w-3 text-gray-500" />;
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold">Effectif</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-4 gap-6">
          {/* Effectif Actif */}
          <div className="text-center">
            <p className="text-xs text-muted-foreground font-medium mb-2">Effectif Actif</p>
            <div className="text-3xl font-bold">{kpis.effectifActif}</div>
            {/* Répartition CDI/CDD */}
            <div className="flex items-center justify-center gap-3 pt-2 mt-2 border-t">
              <div className="text-center">
                <p className="text-[10px] text-muted-foreground font-medium">CDI</p>
                <p className="text-sm font-bold text-blue-600">{kpis.cdiCount}</p>
              </div>
              <div className="h-6 w-px bg-border"></div>
              <div className="text-center">
                <p className="text-[10px] text-muted-foreground font-medium">CDD</p>
                <p className="text-sm font-bold text-orange-600">{kpis.cddCount}</p>
              </div>
            </div>
          </div>

          {/* Absents Aujourd'hui */}
          <div className="text-center">
            <p className="text-xs text-muted-foreground font-medium mb-2">Absents Aujourd'hui</p>
            <div className={`text-3xl font-bold ${absentsToday.length > 0 ? 'text-red-500' : 'text-green-600'}`}>
              {absentsToday.length}
            </div>
            {absentsToday.length > 0 && absentsToday.length <= 2 && (
              <div className="space-y-1 pt-2 mt-2 border-t">
                {absentsToday.map((emp) => (
                  <div key={emp.id} className="flex items-center justify-center gap-1.5 text-[10px] text-muted-foreground">
                    {getAbsenceIcon(emp.status)}
                    <span className="font-medium">{emp.first_name} {emp.last_name}</span>
                  </div>
                ))}
              </div>
            )}
            {absentsToday.length > 2 && (
              <div className="text-[10px] text-muted-foreground pt-2 mt-2 border-t">
                {absentsToday.slice(0, 2).map((emp) => emp.first_name).join(', ')}...
              </div>
            )}
          </div>

          {/* Absentéisme (30j) */}
          <div className="text-center col-span-2">
            <p className="text-xs text-muted-foreground font-medium mb-2">Absentéisme (30j)</p>
            <div className={`text-3xl font-bold ${kpis.tauxAbsenteisme > 5 ? 'text-amber-500' : 'text-foreground'}`}>
              {kpis.tauxAbsenteisme.toFixed(1)}%
            </div>
          </div>
        </div>
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

function CoutsCard({ kpis, chartData }: { kpis: KpiData, chartData: ChartDataPoint[] }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold">Coûts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Masse Salariale du mois précédent */}
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Masse Salariale {kpis.currentMonth}</h3>
          <div className="grid grid-cols-2 gap-6">
            <div className="text-center">
              <p className="text-xs text-red-500 font-medium mb-1">Coût Total</p>
              <div className="text-2xl font-bold text-foreground">{kpis.coutTotal.toLocaleString('fr-FR')} €</div>
            </div>
            <div className="text-center">
              <p className="text-xs text-green-600 font-medium mb-1">Net Versé</p>
              <div className="text-2xl font-bold text-foreground">{kpis.netVerse.toLocaleString('fr-FR')} €</div>
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

// --- Section 4: Pouls de l'Équipe ---

function AbsenteesCard({ employees }: { employees: TeamPulseEmployee[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Absents Aujourd'hui</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {employees.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun absent aujourd'hui.</p>
        ) : (
          employees.map(emp => (
            <div key={emp.id} className="flex items-center gap-3">
              <Avatar className="h-9 w-9">
                {/* ✅ CORRECTION: AvatarImage supprimé, Fallback utilisé */}
                <AvatarFallback>{emp.first_name[0]}{emp.last_name[0]}</AvatarFallback>
              </Avatar>
              <div>
                <p className="font-medium text-sm">{emp.first_name} {emp.last_name}</p>
                <Badge variant="outline" className="text-xs">
                  {emp.status === 'Maladie' ? <HeartPulse className="h-3 w-3 mr-1 text-red-500" /> : <Plane className="h-3 w-3 mr-1 text-blue-500" />}
                  {emp.status}
                </Badge>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function EventsCard({ events }: { events: TeamPulseEvent[] }) {
  const getIcon = (type: TeamPulseEvent['type']) => {
    if (type === 'birthday') return <PartyPopper className="h-5 w-5 text-pink-500" />;
    return <Briefcase className="h-5 w-5 text-indigo-500" />;
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>Événements & Anniversaires (7j)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {events.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun événement à venir.</p>
        ) : (
          events.map(event => (
            <div key={event.id} className="flex items-center gap-3">
              <div className="p-2 bg-muted rounded-full">{getIcon(event.type)}</div>
              <div>
                <p className="font-medium text-sm">{event.employee_name}</p>
                <p className="text-xs text-muted-foreground">{event.detail}</p>
              </div>
            </div>
          ))
        )}
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