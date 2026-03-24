// frontend/src/pages/SaisiesEtAvances.tsx

import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Scale, Wallet, BarChart3 } from "lucide-react";
import { SalarySeizuresTab } from "@/components/saisies-avances/SalarySeizuresTab";
import { SalaryAdvancesTab } from "@/components/saisies-avances/SalaryAdvancesTab";
import { SaisiesAvancesDashboard } from "@/components/saisies-avances/SaisiesAvancesDashboard";

export default function SaisiesEtAvances() {
  const [activeTab, setActiveTab] = useState("dashboard");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Saisies et Avances</h1>
        <p className="text-muted-foreground">
          Gestion des saisies sur salaire (prélèvements obligatoires) et des avances sur salaire
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="dashboard" className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Tableau de bord
          </TabsTrigger>
          <TabsTrigger value="saisies" className="flex items-center gap-2">
            <Scale className="h-4 w-4" />
            Saisies
          </TabsTrigger>
          <TabsTrigger value="avances" className="flex items-center gap-2">
            <Wallet className="h-4 w-4" />
            Avances
          </TabsTrigger>
        </TabsList>

        <TabsContent value="dashboard" className="space-y-6 mt-6">
          <SaisiesAvancesDashboard />
        </TabsContent>

        <TabsContent value="saisies" className="space-y-6 mt-6">
          <SalarySeizuresTab />
        </TabsContent>

        <TabsContent value="avances" className="space-y-6 mt-6">
          <SalaryAdvancesTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
