import CatalogueTab from "@/pages/formation/tabs/CatalogueTab";
import BudgetTab from "@/pages/formation/tabs/BudgetTab";
import ObligationsLegalesTab from "@/pages/formation/tabs/ObligationsLegalesTab";
import CompetencesTab from "@/pages/formation/tabs/CompetencesTab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { useViewOptional } from "@/contexts/ViewContext";

export default function CatalogueFormationsPage() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const viewOpt = useViewOptional();

  const isRh =
    Boolean(user?.is_super_admin) ||
    activeCompany?.role === "admin" ||
    activeCompany?.role === "rh" ||
    activeCompany?.role === "collaborateur_rh";

  const showBudgetTab = Boolean(
    isRh && !(viewOpt?.isCollaborateurRh && viewOpt.viewMode === "collaborateur"),
  );

  const canUseLegalTabs = Boolean(activeCompany);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Catalogue des formations</h1>
        <p className="text-sm text-muted-foreground">
          Formations, inscriptions, budget, obligations légales et référentiel habilitations.
        </p>
      </div>

      {canUseLegalTabs ? (
        <Tabs defaultValue="catalogue" className="w-full">
          <TabsList className="flex h-auto min-h-10 flex-wrap gap-1">
            <TabsTrigger value="catalogue">Catalogue & inscriptions</TabsTrigger>
            {showBudgetTab ? <TabsTrigger value="budget">Budget</TabsTrigger> : null}
            <TabsTrigger value="obligations">Obligations légales</TabsTrigger>
            <TabsTrigger value="competences">Compétences</TabsTrigger>
          </TabsList>
          <TabsContent value="catalogue" className="mt-4">
            <CatalogueTab />
          </TabsContent>
          {showBudgetTab ? (
            <TabsContent value="budget" className="mt-4">
              <BudgetTab />
            </TabsContent>
          ) : null}
          <TabsContent value="obligations" className="mt-4">
            <ObligationsLegalesTab />
          </TabsContent>
          <TabsContent value="competences" className="mt-4">
            <CompetencesTab />
          </TabsContent>
        </Tabs>
      ) : (
        <CatalogueTab />
      )}
    </div>
  );
}
