// src/pages/Exports.tsx
// Onglet RH "Exports" — Paie, déclarations, historique, exports planifiés

import { RhPageHeader } from '@/components/layout';
import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Calculator, FileText, Receipt, Users, History, CalendarClock } from "lucide-react";
import { useCompany, useHasActiveCompanyRhAccess } from "@/contexts/CompanyContext";
import { Navigate, useSearchParams } from "react-router-dom";
import {
  refreshExportsPageQueries,
  useExportsPageAutoRefresh,
} from "@/lib/exportsQuery";

import { PaieComptabiliteTab } from "@/components/exports/PaieComptabiliteTab";
import { DeclarationsTab } from "@/components/exports/DeclarationsTab";
import { PaiementsTab } from "@/components/exports/PaiementsTab";
import { ExportsRhTab } from "@/components/exports/ExportsRhTab";
import { ExportHistory } from "@/components/exports/ExportHistory";
import { PlanifiesTab } from "@/components/exports/PlanifiesTab";

const EXPORT_TABS = [
  "paie-comptabilite",
  "declarations",
  "paiements",
  "exports-rh",
  "planifies",
  "historique",
] as const;

export default function Exports() {
  const hasRhAccess = useHasActiveCompanyRhAccess();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? null;
  const queryClient = useQueryClient();
  useExportsPageAutoRefresh(queryClient, companyId);
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const initialTab =
    tabParam && EXPORT_TABS.includes(tabParam as (typeof EXPORT_TABS)[number])
      ? tabParam
      : "paie-comptabilite";
  const [activeTab, setActiveTab] = useState(initialTab);
  const [historyFilter, setHistoryFilter] = useState<string | undefined>(undefined);
  const deepLinkExport = searchParams.get("export");

  useEffect(() => {
    if (tabParam && EXPORT_TABS.includes(tabParam as (typeof EXPORT_TABS)[number])) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  useEffect(() => {
    window.scrollTo(0, 0);
    if (activeTab !== "historique") {
      setHistoryFilter(undefined);
    }
    refreshExportsPageQueries(queryClient, companyId);
  }, [activeTab, queryClient, companyId]);

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    const next = new URLSearchParams(searchParams);
    if (tab === "paie-comptabilite") {
      next.delete("tab");
    } else {
      next.set("tab", tab);
    }
    if (tab !== "paie-comptabilite" && tab !== "paiements") {
      next.delete("export");
    }
    setSearchParams(next, { replace: true });
  };

  if (!hasRhAccess) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="space-y-6">
      <RhPageHeader
        title="Exports"
        description="Centre de production réglementaire pour transmettre des données à la comptabilité, produire des déclarations sociales et extraire des tableaux RH complets et auditables."
      />

      <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
        <TabsList className="grid h-auto w-full grid-cols-1 gap-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
          <TabsTrigger value="paie-comptabilite" className="flex items-center gap-2 text-xs sm:text-sm">
            <Calculator className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Paie & Comptabilité</span>
            <span className="sm:hidden">Paie</span>
          </TabsTrigger>
          <TabsTrigger value="declarations" className="flex items-center gap-2 text-xs sm:text-sm">
            <FileText className="h-4 w-4 shrink-0" />
            Déclarations
          </TabsTrigger>
          <TabsTrigger value="paiements" className="flex items-center gap-2 text-xs sm:text-sm">
            <Receipt className="h-4 w-4 shrink-0" />
            Paiements
          </TabsTrigger>
          <TabsTrigger value="exports-rh" className="flex items-center gap-2 text-xs sm:text-sm">
            <Users className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Exports RH</span>
            <span className="sm:hidden">RH</span>
          </TabsTrigger>
          <TabsTrigger value="planifies" className="flex items-center gap-2 text-xs sm:text-sm">
            <CalendarClock className="h-4 w-4 shrink-0" />
            Envois
          </TabsTrigger>
          <TabsTrigger value="historique" className="flex items-center gap-2 text-xs sm:text-sm">
            <History className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Historique</span>
            <span className="sm:hidden">Hist.</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="paie-comptabilite" className="space-y-6 mt-6">
          <PaieComptabiliteTab
            initialExportId={deepLinkExport}
            onOpenHistory={(filter) => {
              setHistoryFilter(filter);
              handleTabChange("historique");
            }}
          />
        </TabsContent>

        <TabsContent value="declarations" className="space-y-6 mt-6">
          <DeclarationsTab />
        </TabsContent>

        <TabsContent value="paiements" className="space-y-6 mt-6">
          <PaiementsTab initialExportId={activeTab === "paiements" ? deepLinkExport : null} />
        </TabsContent>

        <TabsContent value="exports-rh" className="space-y-6 mt-6">
          <ExportsRhTab />
        </TabsContent>

        <TabsContent value="planifies" className="space-y-6 mt-6">
          <PlanifiesTab />
        </TabsContent>

        <TabsContent value="historique" className="space-y-6 mt-6">
          <ExportHistory exportType={historyFilter} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
