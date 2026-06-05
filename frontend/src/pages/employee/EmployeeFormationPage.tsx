// Page collaborateur unifiée « Ma formation » (Pack Talent T10)

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SharkFinLoader } from '@/components/SharkFinLoader';

import {
  EmployeePageHeader,
  EmployeePageShell,
} from "@/components/employee/EmployeePageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { useCompany } from "@/contexts/CompanyContext";
import { useCurrentEmployee } from "@/hooks/useCurrentEmployee";
import { useEmployeeFormationSummary } from "@/hooks/useEmployeeFormationSummary";
import {
  EMPLOYEE_FORMATION_TAB_IDS,
  EMPLOYEE_HASH_BY_TAB,
  type EmployeeFormationTabId,
  parseEmployeeFormationHashTab,
  persistEmployeeFormationTab,
} from "@/lib/employeeFormationUtils";

import EmployeeAnnualReviews from "@/pages/employee/AnnualReviews";
import { EmployeeFormationTabs } from "@/pages/employee/formation/EmployeeFormationTabs";
import { FormationCertificationsPanel } from "@/pages/employee/formation/FormationCertificationsPanel";
import { FormationCompetenciesPanel } from "@/pages/employee/formation/FormationCompetenciesPanel";
import { FormationLegalPanel } from "@/pages/employee/formation/FormationLegalPanel";
import { FormationObjectivesPanel } from "@/pages/employee/formation/FormationObjectivesPanel";
import { FormationOnboardingTabContent } from "@/pages/employee/formation/FormationOnboardingTabContent";
import { FormationSummaryBanner } from "@/pages/employee/formation/FormationSummaryBanner";
import { FormationTrainingPanel } from "@/pages/employee/formation/FormationTrainingPanel";

export default function EmployeeFormationPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<EmployeeFormationTabId>(() => parseEmployeeFormationHashTab());
  const { activeCompany } = useCompany();
  const { employee, isLoading, isError, notConfigured, error, refetch } = useCurrentEmployee();

  const companyId = activeCompany?.company_id;
  const employeeId = employee?.id;

  const summary = useEmployeeFormationSummary(employeeId, companyId);

  const syncTabFromLocation = useCallback(() => {
    setTab(parseEmployeeFormationHashTab());
  }, []);

  useEffect(() => {
    syncTabFromLocation();
  }, [syncTabFromLocation]);

  useEffect(() => {
    window.addEventListener("hashchange", syncTabFromLocation);
    return () => window.removeEventListener("hashchange", syncTabFromLocation);
  }, [syncTabFromLocation]);

  const navigateToTab = (next: EmployeeFormationTabId) => {
    if (!EMPLOYEE_FORMATION_TAB_IDS.includes(next)) return;
    setTab(next);
    persistEmployeeFormationTab(next);
    navigate({ pathname: "/employee/formation", hash: EMPLOYEE_HASH_BY_TAB[next] }, { replace: true });
  };

  const handleTabChange = (value: string) => {
    navigateToTab(value as EmployeeFormationTabId);
  };

  if (!companyId) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Sélectionnez une entreprise pour afficher votre espace formation.
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return <SharkFinLoader variant="fullPage" label="Chargement de votre profil…" />;
  }

  if (isError) {
    const msg =
      (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
      "Une erreur est survenue.";
    return (
      <Card className="border-destructive/40">
        <CardContent className="flex flex-col gap-3 py-6 text-sm">
          <p className="text-destructive">{msg}</p>
          <Button variant="outline" size="sm" className="w-fit" onClick={() => void refetch()}>
            Réessayer
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (notConfigured || !employeeId) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Votre profil collaborateur n&apos;est pas encore configuré. Contactez votre service RH.
        </CardContent>
      </Card>
    );
  }

  return (
    <EmployeePageShell>
      <div className="space-y-3">
        <EmployeePageHeader
          title="Ma formation"
          description="Consultez votre parcours et effectuez les actions qui vous sont demandées (entretiens, demandes de formation, évaluations)."
        />
        <FormationSummaryBanner counts={summary} onNavigateTab={navigateToTab} />
      </div>

      <Tabs value={tab} onValueChange={handleTabChange} className="w-full">
        <EmployeeFormationTabs counts={summary} />

        {tab === "entretiens" && (
          <TabsContent value="entretiens" className="mt-0">
            <EmployeeAnnualReviews embedded />
          </TabsContent>
        )}

        {tab === "objectifs" && (
          <TabsContent value="objectifs" className="mt-0">
            <FormationObjectivesPanel employeeId={employeeId} />
          </TabsContent>
        )}

        {tab === "habilitations" && (
          <TabsContent value="habilitations" className="mt-0">
            <FormationCertificationsPanel employeeId={employeeId} />
          </TabsContent>
        )}

        {tab === "formations" && (
          <TabsContent value="formations" className="mt-0">
            <FormationTrainingPanel employeeId={employeeId} />
          </TabsContent>
        )}

        {tab === "obligations" && (
          <TabsContent value="obligations" className="mt-0">
            <FormationLegalPanel employeeId={employeeId} />
          </TabsContent>
        )}

        {tab === "competences" && (
          <TabsContent value="competences" className="mt-0">
            <FormationCompetenciesPanel employeeId={employeeId} />
          </TabsContent>
        )}

        {tab === "onboarding" && (
          <TabsContent value="onboarding" className="mt-0">
            <FormationOnboardingTabContent companyId={companyId} />
          </TabsContent>
        )}
      </Tabs>
    </EmployeePageShell>
  );
}
