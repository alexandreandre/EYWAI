import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';

import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import {
  useAnnualReviewsPriorityQuery,
  useDashboardAllQuery,
  useMedicalDashboardQuery,
  useOnboardingDashboardQuery,
  usePendingSignaturesRhQuery,
  useRecruitmentPriorityQuery,
  useResidencePermitStatsQuery,
  useRibAlertsDashboardQuery,
} from '@/hooks/queries/useDashboardQueries';
import { DashboardSkeleton } from '@/components/skeletons/DashboardSkeleton';
import { PageFetchIndicator } from '@/components/skeletons/PageFetchIndicator';
import { CopilotModalAgent } from '@/components/CopilotModalAgent';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Progress } from '@/components/ui/progress';
import {
  AlertTriangle,
  Inbox,
  CalendarCheck,
  CreditCard,
  FileWarning,
  UserPlus,
  PartyPopper,
  Landmark,
  Stethoscope,
  TrendingUp,
  Mail,
  BarChart3,
  UserRoundPlus,
} from 'lucide-react';
import { CSEDashboardBlock } from '@/components/CSEDashboardBlock';
import { PendingSignaturesWidget } from '@/components/dashboard/PendingSignaturesWidget';
import TeamAnalyticsSection from '@/components/dashboard/TeamAnalyticsSection';
import { ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS } from '@/api/annualReviews';
import { isRecruitmentPriorityCandidate } from '@/api/recruitment';
import { queryKeys } from '@/lib/queryKeys';
import { FormationTalentsDashboardWidget } from '@/features/dashboard/widgets/FormationTalentsDashboardWidget';
import { DashboardHeader } from '@/features/dashboard/widgets/DashboardHeader';
import { ResidencePermitCard } from '@/features/dashboard/widgets/ResidencePermitCard';
import { MedicalFollowUpCard } from '@/features/dashboard/widgets/MedicalFollowUpCard';
import { RibAlertsCard } from '@/features/dashboard/widgets/RibAlertsCard';
import { RecruitmentKpisCard } from '@/features/dashboard/widgets/RecruitmentKpisCard';
import { IncompleteEmployeesCard } from '@/features/dashboard/widgets/IncompleteEmployeesCard';
import { EffectifPanorama } from '@/features/dashboard/widgets/EffectifPanorama';
import { CoutsCard } from '@/features/dashboard/widgets/CoutsCard';
import type {
  DashboardData,
  DashboardPriorityKey,
  PriorityValidationByCount,
} from '@/features/dashboard/types';

const PRIORITY_DAY_STORAGE_KEY = 'eywai.dashboard.priority-day.validated.v1';

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
  const onboardingQuery = useOnboardingDashboardQuery(Boolean(companyId));

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

  const onboardingItems = useMemo(
    () => onboardingQuery.data?.items ?? [],
    [onboardingQuery.data],
  );
  const incompleteEmployees = useMemo(
    () => onboardingItems.filter((item) => !item.profile_complete),
    [onboardingItems],
  );
  const incompleteEmployeesCount =
    onboardingQuery.data?.kpis.profile_incomplete ?? incompleteEmployees.length;
  const incompleteEmployeesLoading = onboardingQuery.isLoading && !onboardingQuery.data;
  const incompleteEmployeesPreview = useMemo(() => {
    if (incompleteEmployees.length === 0) return null;
    return incompleteEmployees
      .slice(0, 2)
      .map((item) => `${item.first_name} ${item.last_name}`.trim())
      .join(' · ');
  }, [incompleteEmployees]);

  const isFetching =
    dashboardQuery.isFetching ||
    residenceQuery.isFetching ||
    ribQuery.isFetching ||
    medical.isFetching ||
    onboardingQuery.isFetching;

  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const [selectedPriorityKey, setSelectedPriorityKey] = useState<DashboardPriorityKey | null>(null);
  const [validatedPriorityByCount, setValidatedPriorityByCount] = useState<PriorityValidationByCount>(() => {
    try {
      const raw = sessionStorage.getItem(PRIORITY_DAY_STORAGE_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw) as unknown;
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        const out: PriorityValidationByCount = {};
        for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
          if (typeof k === 'string' && typeof v === 'number') out[k] = v;
        }
        return out;
      }
      return {};
    } catch {
      return {};
    }
  });

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setIsCopilotOpen((open) => !open);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

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
      key: 'leaves',
      label: "Demandes d'absences",
      count: data.actions.pendingAbsences,
      href: '/leaves',
      icon: CalendarCheck,
      hint: "À valider aujourd'hui",
    },
    {
      key: 'expenses',
      label: 'Notes de frais',
      count: data.actions.pendingExpenses,
      href: '/expenses',
      icon: CreditCard,
      hint: 'En attente de traitement',
    },
    {
      key: 'rib',
      label: 'Alertes RIB',
      count: ribAlertTotal,
      href: '/employees',
      icon: Landmark,
      hint: 'Contrôles administratifs',
    },
    {
      key: 'medical',
      label: 'Suivi médical',
      count: medicalPendingTotal,
      href: '/medical-follow-up',
      icon: Stethoscope,
      hint: 'Visites à planifier',
    },
    {
      key: 'residence',
      label: 'Titres de séjour',
      count: residencePendingTotal,
      href: '/residence-permits',
      icon: FileWarning,
      hint: 'Échéances à surveiller',
    },
    {
      key: 'contracts',
      label: "Contrats & périodes d'essai",
      count: data.alerts.expiringContracts + data.alerts.endOfTrialPeriods,
      href: '/employees?alert=deadlines',
      icon: UserPlus,
      hint: 'Fin de CDD ou période d\'essai sous 15 jours',
    },
    {
      key: 'annualReviews',
      label: 'Entretiens planifiés',
      count: annualReviewsUpcomingCount,
      href: '/annual-reviews?focus=upcoming',
      icon: CalendarCheck,
      hint: `Planifiés dans ${ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS} jours`,
    },
    {
      key: 'recruitment',
      label: 'Recrutement',
      count: recruitmentPendingCount,
      href: '/recruitment',
      icon: UserPlus,
      hint: recruitmentPendingPreview
        ? `Candidats à traiter : ${recruitmentPendingPreview}`
        : 'Candidatures en cours',
    },
    {
      key: 'onboardingProfiles',
      label: 'Nouveaux salariés à compléter',
      count: incompleteEmployeesCount,
      href:
        incompleteEmployees.length === 1
          ? `/employees/${incompleteEmployees[0].employee_id}`
          : '/onboarding',
      icon: UserRoundPlus,
      hint: incompleteEmployeesPreview
        ? `Fiche paie à finaliser : ${incompleteEmployeesPreview}`
        : 'Fiches paie à finaliser',
    },
    {
      key: 'rates',
      label: 'Taux de cotisations',
      count: data.alerts.obsoleteRates,
      href: '/rates',
      icon: TrendingUp,
      hint: 'Mises à jour nécessaires',
    },
    {
      key: 'pendingSignatures',
      label: 'Signatures en attente',
      count: pendingSignaturesCount,
      href: '/annual-reviews?signature_status=pending',
      icon: Mail,
      hint: 'Procédures à relancer',
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
  const todayLabelRaw = new Date().toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
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
        firstName={user?.first_name || 'Utilisateur'}
        dateLabel={todayLabel}
        onCopilotClick={() => setIsCopilotOpen(true)}
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
                          Reste : {remainingMainFocus} tâche{remainingMainFocus > 1 ? 's' : ''}
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

          {(incompleteEmployeesLoading || incompleteEmployees.length > 0) && (
            <IncompleteEmployeesCard
              items={onboardingItems}
              loading={incompleteEmployeesLoading}
            />
          )}

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

      <CopilotModalAgent
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
      />
    </div>
  );
}
