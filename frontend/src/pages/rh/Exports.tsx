// src/pages/Exports.tsx
// Onglet RH "Exports" — Paie, déclarations, historique, exports planifiés

import { RhPageHeader } from '@/components/layout';
import { useState, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Calculator, FileText, Receipt, Users, History, CalendarClock } from "lucide-react";
import { useHasActiveCompanyRhAccess } from "@/contexts/CompanyContext";
import { Navigate } from "react-router-dom";

import { PaieComptabiliteTab } from "@/components/exports/PaieComptabiliteTab";
import { DeclarationsTab } from "@/components/exports/DeclarationsTab";
import { PaiementsTab } from "@/components/exports/PaiementsTab";
import { ExportsRhTab } from "@/components/exports/ExportsRhTab";
import { ExportHistory } from "@/components/exports/ExportHistory";
import { PlanifiesTab } from "@/components/exports/PlanifiesTab";

export default function Exports() {
  const hasRhAccess = useHasActiveCompanyRhAccess();
  const [activeTab, setActiveTab] = useState("paie-comptabilite");
  const [historyFilter, setHistoryFilter] = useState<string | undefined>(undefined);

  useEffect(() => {
    window.scrollTo(0, 0);
    if (activeTab !== "historique") {
      setHistoryFilter(undefined);
    }
  }, [activeTab]);

  if (!hasRhAccess) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="space-y-6">
      <RhPageHeader
        title="Exports"
        description="Centre de production réglementaire pour transmettre des données à la comptabilité, produire des déclarations sociales et extraire des tableaux RH complets et auditables."
      />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
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
            <span className="hidden sm:inline">Planifiés</span>
            <span className="sm:hidden">Planif.</span>
          </TabsTrigger>
          <TabsTrigger value="historique" className="flex items-center gap-2 text-xs sm:text-sm">
            <History className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Historique</span>
            <span className="sm:hidden">Hist.</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="paie-comptabilite" className="space-y-6 mt-6">
          <PaieComptabiliteTab />
        </TabsContent>

        <TabsContent value="declarations" className="space-y-6 mt-6">
          <DeclarationsTab />
        </TabsContent>

        <TabsContent value="paiements" className="space-y-6 mt-6">
          <PaiementsTab />
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
