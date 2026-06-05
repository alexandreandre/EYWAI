import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  CompanyPageHeader,
  CompanyComplianceBand,
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

export default function CompanyPage() {
  const { user } = useAuth();
  const companyId = useActiveCompanyId();
  const { toast } = useToast();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { period, setPeriod, periodBounds } = useCompanyPeriod();
  const { isPremium } = useCompanyPlan();

  const [activeTab, setActiveTab] = useState("pilotage");
  const [editOpen, setEditOpen] = useState(false);
  const [draft, setDraft] = useState<CompanyDetailsUpdate>({});
  const [exporting, setExporting] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const h = (location.hash || "").replace(/^#/, "");
    if (h === "bibliotheque") setActiveTab("bibliotheque");
    if (h === "paie" || h === "parametres") setActiveTab("paie");
    if (h === "mutuelle") setActiveTab("mutuelle");
    if (h === "identite" || h === "informations" || h === "coordonnees") {
      setActiveTab("identite");
    }
  }, [location.hash]);

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

  const openEdit = useCallback(() => {
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
    setEditOpen(true);
  }, [company]);

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

  return (
    <div className="space-y-6 animate-fade-in pb-8">
      <CompanyPageHeader
        company={company}
        period={period}
        onPeriodChange={setPeriod}
        periodLabel={periodBounds.label}
        isPremium={isPremium}
        canEdit={canEdit}
        onEdit={openEdit}
        onExport={handleExport}
        exporting={exporting}
      />

      {overview ? (
        <CompanyComplianceBand
          compliance={overview.compliance}
          onGoToPayrollTab={() => setActiveTab("paie")}
        />
      ) : null}

      <CompanyGroupPositionBand />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="flex w-full max-w-3xl flex-wrap h-auto gap-1 p-1">
          <TabsTrigger value="pilotage">Pilotage</TabsTrigger>
          <TabsTrigger value="identite">Identité</TabsTrigger>
          <TabsTrigger value="paie">Paie</TabsTrigger>
          <TabsTrigger value="mutuelle">Mutuelle</TabsTrigger>
          <TabsTrigger value="bibliotheque">Bibliothèque</TabsTrigger>
        </TabsList>

        <TabsContent value="pilotage" className="space-y-4 mt-0">
          <CompanyPilotageSection kpis={kpis} period={period} />
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
          {overview?.alerts?.length ? (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <ul className="list-disc pl-4 space-y-1">
                  {overview.alerts.map((a) => (
                    <li key={a.code}>{a.label}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          ) : null}
        </TabsContent>

        <TabsContent value="identite" className="mt-0">
          <CompanyIdentityTab
            company={company}
            canEdit={canEdit}
            editOpen={editOpen}
            onEditOpenChange={setEditOpen}
            draft={draft}
            onDraftChange={setDraft}
            onSave={handleSaveIdentity}
            saving={saving}
          />
        </TabsContent>

        <TabsContent value="paie" className="mt-0">
          <CompanyPayrollTab company={company} />
        </TabsContent>

        <TabsContent value="mutuelle" className="mt-0">
          <MutuelleManagementTab />
        </TabsContent>

        <TabsContent value="bibliotheque" className="mt-0">
          <DocumentLibraryTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
