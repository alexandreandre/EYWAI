import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart2,
  BookOpen,
  Building2,
  Calculator,
  HeartHandshake,
} from "lucide-react";
import { SharkFinLoader } from '@/components/SharkFinLoader';

import {
  downloadCompanyExport,
  fetchCompanyDetails,
  fetchCompanyOverview,
  patchCompanyDetails,
  type CompanyDetailsUpdate,
} from "@/api/company";
import { useAuth } from "@/contexts/AuthContext";
import { useActiveCompanyId } from "@/hooks/queries/useCompanyId";
import { useCompanyPlan } from "@/hooks/useCompanyPlan";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  CompanyPageHeader,
  CompanyComplianceBand,
  CompanyOverviewAlerts,
  CompanyRhStatsBand,
  CompanyPilotageSection,
  CompanyIdentityTab,
  CompanyPayrollTab,
  CompanyGroupPositionBand,
  MutuelleManagementTab,
  DocumentLibraryTab,
  useCompanyPeriod,
  computePeriodPayroll,
} from "@/features/company";
import { CompanyDsnCoverageBand } from "@/features/company/components/CompanyDsnCoverageBand";
import {
  isComplianceAnchor,
  type ComplianceAnchor,
} from "@/features/company/components/CompanyComplianceBand";
import {
  DEFAULT_COMPANY_PAGE_TAB,
  tabFromHash,
  tabFromSearchParam,
  type CompanyPageTab,
} from "@/features/company/lib/companyPageTabs";

export default function CompanyPage() {
  const { user } = useAuth();
  const companyId = useActiveCompanyId();
  const { toast } = useToast();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { period, setPeriod, periodBounds } = useCompanyPeriod();
  const { isPremium } = useCompanyPlan();

  const [activeTab, setActiveTab] = useState<CompanyPageTab>(() => {
    const params = new URLSearchParams(window.location.search);
    return (
      tabFromSearchParam(params.get("tab")) ??
      tabFromHash(window.location.hash) ??
      DEFAULT_COMPANY_PAGE_TAB
    );
  });
  const [editOpen, setEditOpen] = useState(false);
  const [draft, setDraft] = useState<CompanyDetailsUpdate>({});
  const [exporting, setExporting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [payrollScrollAnchor, setPayrollScrollAnchor] = useState<ComplianceAnchor | null>(null);

  useEffect(() => {
    const fromQuery = tabFromSearchParam(searchParams.get("tab"));
    const fromHash = tabFromHash(location.hash);
    const next = fromQuery ?? fromHash;
    if (next && next !== activeTab) {
      setActiveTab(next);
    }
  }, [location.hash, searchParams, activeTab]);

  useEffect(() => {
    const section = searchParams.get("section");
    if (!isComplianceAnchor(section)) return;
    setActiveTab("paie");
    setPayrollScrollAnchor(section);
  }, [searchParams]);

  const handleTabChange = useCallback(
    (value: string) => {
      const tab = value as CompanyPageTab;
      setActiveTab(tab);
      setPayrollScrollAnchor(null);
      const params = new URLSearchParams(searchParams);
      params.set("tab", tab);
      if (tab !== "paie") {
        params.delete("section");
      }
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const goToPayrollTab = useCallback(
    (anchor?: ComplianceAnchor) => {
      setActiveTab("paie");
      if (anchor) setPayrollScrollAnchor(anchor);
      const params = new URLSearchParams(searchParams);
      params.set("tab", "paie");
      if (anchor) {
        params.set("section", anchor);
      } else {
        params.delete("section");
      }
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const detailsQuery = useQuery({
    queryKey: ["company-details", companyId],
    queryFn: fetchCompanyDetails,
    enabled: Boolean(companyId),
  });

  const overviewQuery = useQuery({
    queryKey: ["company-overview", companyId],
    queryFn: fetchCompanyOverview,
    enabled: Boolean(companyId),
  });

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === "admin" || r === "rh" || r === "admin";
  }, [user?.role]);

  const company = detailsQuery.data?.company_data;
  const kpis = detailsQuery.data?.kpis;
  const overview = overviewQuery.data;

  const payrollPeriod = useMemo(
    () => (kpis ? computePeriodPayroll(kpis, period) : null),
    [kpis, period],
  );

  const populateDraft = useCallback(() => {
    if (!company) return;
    setDraft({
      company_name: company.company_name,
      raison_sociale: company.raison_sociale ?? undefined,
      siret: company.siret ?? undefined,
      siren: company.siren ?? undefined,
      legal_form: company.legal_form ?? undefined,
      phone: company.phone ?? undefined,
      email: company.email ?? undefined,
      website: company.website ?? undefined,
      adresse_rue: company.adresse_rue ?? undefined,
      adresse_code_postal: company.adresse_code_postal ?? undefined,
      adresse_ville: company.adresse_ville ?? undefined,
      nom_signataire_rh: company.nom_signataire_rh ?? undefined,
      qualite_signataire_rh: company.qualite_signataire_rh ?? undefined,
    });
  }, [company]);

  const handleEditOpenChange = useCallback(
    (open: boolean) => {
      if (open) populateDraft();
      setEditOpen(open);
    },
    [populateDraft],
  );

  const handleSaveIdentity = async () => {
    try {
      setSaving(true);
      await patchCompanyDetails(draft);
      await queryClient.invalidateQueries({ queryKey: ["company-details", companyId] });
      toast({ title: "Enregistré", description: "Identité mise à jour." });
      setEditOpen(false);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: "Erreur",
        description: err.response?.data?.detail ?? "Échec de la mise à jour",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    try {
      setExporting(true);
      await downloadCompanyExport();
      toast({ title: "Export", description: "Fichier CSV téléchargé." });
    } catch {
      toast({
        title: "Erreur",
        description: "Impossible d'exporter les données",
        variant: "destructive",
      });
    } finally {
      setExporting(false);
    }
  };

  if (detailsQuery.isLoading) {
    return <SharkFinLoader variant="fullPage" label="Chargement de l'entreprise…" />;
  }

  if (detailsQuery.error) {
    const msg =
      (detailsQuery.error as { response?: { data?: { detail?: string } } })?.response
        ?.data?.detail ?? "Erreur de chargement";
    return (
      <Card className="border-red-500/50 bg-red-500/5">
        <CardHeader>
          <CardTitle className="flex items-center text-red-600">
            <AlertTriangle className="mr-2 h-5 w-5" />
            Échec du chargement
          </CardTitle>
        </CardHeader>
        <CardContent className="text-red-600 text-sm">{msg}</CardContent>
      </Card>
    );
  }

  if (!company || !kpis) {
    return (
      <div className="text-center text-muted-foreground py-10">
        Aucune donnée d&apos;entreprise trouvée.
      </div>
    );
  }

  const avgCostPerEmployee =
    kpis.total_employees > 0 && payrollPeriod
      ? payrollPeriod.totalCost / kpis.total_employees
      : 0;

  const showComplianceBand =
    overview && (activeTab === "indicateurs" || activeTab === "paie");

  return (
    <div className="space-y-6 animate-fade-in pb-8">
      <CompanyPageHeader
        company={company}
        isPremium={isPremium}
        onExport={handleExport}
        exporting={exporting}
        onGoToPayrollTab={() => goToPayrollTab("convention-collective")}
      />

      <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-4">
        <TabsList className="grid h-auto w-full grid-cols-2 gap-1 p-1 sm:grid-cols-3 lg:grid-cols-5">
          <TabsTrigger value="indicateurs" className="flex items-center gap-2 text-xs sm:text-sm">
            <BarChart2 className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Indicateurs</span>
            <span className="sm:hidden">Indic.</span>
          </TabsTrigger>
          <TabsTrigger value="fiche" className="flex items-center gap-2 text-xs sm:text-sm">
            <Building2 className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Fiche entreprise</span>
            <span className="sm:hidden">Fiche</span>
          </TabsTrigger>
          <TabsTrigger value="paie" className="flex items-center gap-2 text-xs sm:text-sm">
            <Calculator className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Paramètres paie</span>
            <span className="sm:hidden">Paie</span>
          </TabsTrigger>
          <TabsTrigger value="mutuelle" className="flex items-center gap-2 text-xs sm:text-sm">
            <HeartHandshake className="h-4 w-4 shrink-0" />
            Mutuelle
          </TabsTrigger>
          <TabsTrigger
            value="modeles"
            className="col-span-2 flex items-center gap-2 text-xs sm:col-span-1 sm:text-sm"
          >
            <BookOpen className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Modèles documents</span>
            <span className="sm:hidden">Modèles</span>
          </TabsTrigger>
        </TabsList>

        {showComplianceBand ? (
          <CompanyComplianceBand
            compliance={overview.compliance}
            company={company}
            onGoToPayrollSection={(anchor) => goToPayrollTab(anchor)}
          />
        ) : null}

        <TabsContent value="indicateurs" className="space-y-4 mt-0">
          <CompanyPilotageSection
            kpis={kpis}
            period={period}
            onPeriodChange={setPeriod}
            periodLabel={periodBounds.label}
          />
          {overview && payrollPeriod ? (
            <CompanyRhStatsBand
              overview={overview}
              kpis={kpis}
              periodExtras={{
                net: payrollPeriod.net,
                payrollTaxRate: payrollPeriod.payrollTaxRate,
                avgCostPerEmployee,
              }}
            />
          ) : overviewQuery.isLoading ? (
            <div className="h-16 rounded-lg border bg-muted/30 animate-pulse" />
          ) : null}
          <CompanyGroupPositionBand />
          {overview?.dsn_coverage ? (
            <CompanyDsnCoverageBand coverage={overview.dsn_coverage} />
          ) : null}
          {overview?.alerts?.length ? (
            <CompanyOverviewAlerts
              alerts={overview.alerts}
              onGoToPayrollSection={(anchor) => goToPayrollTab(anchor)}
            />
          ) : null}
        </TabsContent>

        <TabsContent value="fiche" className="mt-0">
          <CompanyIdentityTab
            company={company}
            canEdit={canEdit}
            editOpen={editOpen}
            onEditOpenChange={handleEditOpenChange}
            draft={draft}
            onDraftChange={setDraft}
            onSave={handleSaveIdentity}
            saving={saving}
            onGoToPayrollTab={() => goToPayrollTab("convention-collective")}
          />
        </TabsContent>

        <TabsContent value="paie" className="mt-0">
          <CompanyPayrollTab
            company={company}
            scrollAnchor={payrollScrollAnchor}
            cseObligation={overview?.compliance.cse_obligation}
            dsnCoverage={overview?.dsn_coverage ?? null}
            canEditDsn={canEdit}
            onDsnUpdated={() => void overviewQuery.refetch()}
          />
        </TabsContent>

        <TabsContent value="mutuelle" className="mt-0">
          <MutuelleManagementTab />
        </TabsContent>

        <TabsContent value="modeles" className="mt-0">
          <DocumentLibraryTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
