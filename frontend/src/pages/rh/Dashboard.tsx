import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { useAuth } from '@/contexts/AuthContext';
import { isPayrollFocusActive } from '@/lib/payrollFocus';
import { useCompany } from '@/contexts/CompanyContext';
import {
  useDashboardAllQuery,
  useMedicalDashboardQuery,
  useOnboardingDashboardQuery,
  useResidencePermitStatsQuery,
  useRibAlertsDashboardQuery,
} from '@/hooks/queries/useDashboardQueries';
import { useRhPendingTasks } from '@/hooks/useRhPendingTasks';
import { DashboardSkeleton } from '@/components/skeletons/DashboardSkeleton';
import { PageFetchIndicator } from '@/components/skeletons/PageFetchIndicator';
import { CopilotModalAgent } from '@/components/CopilotModalAgent';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  AlertTriangle,
  Inbox,
  Stethoscope,
  BarChart3,
} from 'lucide-react';
import { CSEDashboardBlock } from '@/components/CSEDashboardBlock';
import { RhParticipationCampaignWidget } from '@/components/dashboard/RhParticipationCampaignWidget';
import { PendingSignaturesWidget } from '@/components/dashboard/PendingSignaturesWidget';
import TeamAnalyticsSection from '@/components/dashboard/TeamAnalyticsSection';
import { queryKeys } from '@/lib/queryKeys';
import { RIB_ALERTS_UI_ENABLED } from '@/lib/productFeatureFlags';
import { FormationTalentsDashboardWidget } from '@/features/dashboard/widgets/FormationTalentsDashboardWidget';
import { DashboardHeader } from '@/features/dashboard/widgets/DashboardHeader';
import { DashboardPriorityPanel } from '@/features/dashboard/widgets/DashboardPriorityPanel';
import { ResidencePermitCard } from '@/features/dashboard/widgets/ResidencePermitCard';
import { MedicalFollowUpCard } from '@/features/dashboard/widgets/MedicalFollowUpCard';
import { RibAlertsCard } from '@/features/dashboard/widgets/RibAlertsCard';
import { RecruitmentKpisCard } from '@/features/dashboard/widgets/RecruitmentKpisCard';
import { IncompleteEmployeesCard } from '@/features/dashboard/widgets/IncompleteEmployeesCard';
import { EffectifPanorama } from '@/features/dashboard/widgets/EffectifPanorama';
import { CoutsCard } from '@/features/dashboard/widgets/CoutsCard';
import type { DashboardData } from '@/features/dashboard/types';

export default function Dashboard() {
  const { user } = useAuth();
  // Mode démo paie : ne montrer que les cartes des modules présents dans le menu.
  const payrollFocus = isPayrollFocusActive(user);
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id;
  const queryClient = useQueryClient();

  const dashboardQuery = useDashboardAllQuery(Boolean(companyId));
  const residenceQuery = useResidencePermitStatsQuery(Boolean(companyId));
  const ribQuery = useRibAlertsDashboardQuery(Boolean(companyId));
  const medical = useMedicalDashboardQuery(Boolean(companyId));
  const onboardingQuery = useOnboardingDashboardQuery(Boolean(companyId));
  const pendingTasks = useRhPendingTasks(Boolean(companyId), companyId);

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
  const ribAlertsLoading = ribQuery.isLoading && !ribQuery.data;
  const medicalModuleEnabled = medical.medicalModuleEnabled;
  const medicalKpis = medical.medicalKpis;
  const medicalKpisLoading = medical.isLoading;

  const onboardingItems = useMemo(
    () => onboardingQuery.data?.items ?? [],
    [onboardingQuery.data],
  );
  const incompleteEmployees = useMemo(
    () => onboardingItems.filter((item) => !item.profile_complete),
    [onboardingItems],
  );
  const incompleteEmployeesLoading = onboardingQuery.isLoading && !onboardingQuery.data;

  const isFetching =
    dashboardQuery.isFetching ||
    residenceQuery.isFetching ||
    ribQuery.isFetching ||
    medical.isFetching ||
    onboardingQuery.isFetching;

  const [isCopilotOpen, setIsCopilotOpen] = useState(false);

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

  const todayLabelRaw = new Date().toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
  const todayLabel =
    todayLabelRaw.charAt(0).toUpperCase() + todayLabelRaw.slice(1);

  return (
    <div className="space-y-6 animate-fade-in">
      <PageFetchIndicator isFetching={isFetching} />
      <DashboardHeader
        firstName={user?.first_name || 'Utilisateur'}
        dateLabel={todayLabel}
        onCopilotClick={() => setIsCopilotOpen(true)}
      />
      <div className="space-y-6">
        <DashboardPriorityPanel
          items={pendingTasks.items}
          sidebarTotal={pendingTasks.sidebarTotal}
          loading={pendingTasks.isLoading}
          refreshing={pendingTasks.isRefreshing}
        />

        <section className="space-y-4 rounded-xl border bg-background p-4 md:p-5">
          <div>
            <h2 className="text-xl font-semibold">Détail par module</h2>
            <p className="text-sm text-muted-foreground">
              Signatures, alertes et conformité — complément au récapitulatif ci-dessus.
            </p>
          </div>

          {(incompleteEmployeesLoading || incompleteEmployees.length > 0) && (
            <IncompleteEmployeesCard
              items={onboardingItems}
              loading={incompleteEmployeesLoading}
            />
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {!payrollFocus && <PendingSignaturesWidget mode="rh" />}
            <RhParticipationCampaignWidget />
            {RIB_ALERTS_UI_ENABLED ? (
              <RibAlertsCard
                alerts={ribAlerts}
                loading={ribAlertsLoading}
                onRefresh={() => {
                  void queryClient.invalidateQueries({
                    queryKey: queryKeys.ribAlerts(companyId),
                  });
                }}
              />
            ) : null}
            {!payrollFocus &&
              (medicalModuleEnabled ? (
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
              ))}
          </div>

          {!payrollFocus && (
            <ResidencePermitCard stats={residencePermitStats} loading={residencePermitLoading} />
          )}
        </section>

        {!payrollFocus && <FormationTalentsDashboardWidget />}

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
            {!payrollFocus && <RecruitmentKpisCard />}
            {!payrollFocus && (
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
            )}
          </div>

          {!payrollFocus && <CSEDashboardBlock />}
        </section>
      </div>

      <CopilotModalAgent
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
      />
    </div>
  );
}
