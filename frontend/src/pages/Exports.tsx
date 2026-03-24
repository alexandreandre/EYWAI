// src/pages/Exports.tsx
// Onglet RH "Exports" - ÉTAPE 1 : Structure, UX & socle commun

import { useState, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, Calculator, Receipt, Users, History } from "lucide-react";
import { useHasActiveCompanyRhAccess } from "@/contexts/CompanyContext";
import { Navigate } from "react-router-dom";

// Composants des sous-onglets
import { PaieComptabiliteTab } from "@/components/exports/PaieComptabiliteTab";
import { DeclarationsTab } from "@/components/exports/DeclarationsTab";
import { PaiementsTab } from "@/components/exports/PaiementsTab";
import { ExportsRhTab } from "@/components/exports/ExportsRhTab";
import { ExportHistory } from "@/components/exports/ExportHistory";

export default function Exports() {
  const hasRhAccess = useHasActiveCompanyRhAccess();
  const [activeTab, setActiveTab] = useState("paie-comptabilite");
  const [historyFilter, setHistoryFilter] = useState<string | undefined>(undefined);

  // Positionnement automatique en haut lors du changement d'onglet ou au montage de la page
  useEffect(() => {
    window.scrollTo(0, 0);
    // Réinitialiser le filtre si on change d'onglet manuellement (pas via navigateToHistory)
    if (activeTab !== "historique") {
      setHistoryFilter(undefined);
    }
  }, [activeTab]);

  // Fonction pour naviguer vers l'historique avec un filtre
  const navigateToHistory = (exportType?: string) => {
    setHistoryFilter(exportType);
    setActiveTab("historique");
  };

  // Vérification des permissions RH
  if (!hasRhAccess) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="space-y-6">
      {/* En-tête */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Exports</h1>
        <p className="text-muted-foreground mt-2">
          Centre de production réglementaire pour transmettre des données à la comptabilité,
          produire des déclarations sociales et extraire des tableaux RH complets et auditables.
        </p>
      </div>

      {/* Onglets principaux */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="paie-comptabilite" className="flex items-center gap-2">
            <Calculator className="h-4 w-4" />
            <span className="hidden sm:inline">Paie & Comptabilité</span>
            <span className="sm:hidden">Paie</span>
          </TabsTrigger>
          <TabsTrigger value="declarations" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Déclarations
          </TabsTrigger>
          <TabsTrigger value="paiements" className="flex items-center gap-2">
            <Receipt className="h-4 w-4" />
            Paiements
          </TabsTrigger>
          <TabsTrigger value="exports-rh" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            <span className="hidden sm:inline">Exports RH</span>
            <span className="sm:hidden">RH</span>
          </TabsTrigger>
          <TabsTrigger value="historique" className="flex items-center gap-2">
            <History className="h-4 w-4" />
            <span className="hidden sm:inline">Historique</span>
            <span className="sm:hidden">Hist.</span>
          </TabsTrigger>
        </TabsList>

        {/* Sous-onglet : Paie & Comptabilité */}
        <TabsContent value="paie-comptabilite" className="space-y-6 mt-6">
          <PaieComptabiliteTab />
        </TabsContent>

        {/* Sous-onglet : Déclarations */}
        <TabsContent value="declarations" className="space-y-6 mt-6">
          <DeclarationsTab />
        </TabsContent>

        {/* Sous-onglet : Paiements */}
        <TabsContent value="paiements" className="space-y-6 mt-6">
          <PaiementsTab />
        </TabsContent>

        {/* Sous-onglet : Exports RH */}
        <TabsContent value="exports-rh" className="space-y-6 mt-6">
          <ExportsRhTab />
        </TabsContent>

        {/* Sous-onglet : Historique */}
        <TabsContent value="historique" className="space-y-6 mt-6">
          <ExportHistory exportType={historyFilter} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

