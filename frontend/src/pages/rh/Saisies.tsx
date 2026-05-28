// src/pages/Saisies.tsx - Page avec sous-onglets Primes et Participation & Intéressement

import { useState } from 'react';
import { RhPageHeader } from '@/components/layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Gift, Calculator } from "lucide-react";
import { PrimesTab } from "@/components/saisies/PrimesTab";
import { ParticipationInteressementTab } from "@/components/saisies/ParticipationInteressementTab";

export default function Saisies() {
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState<number>(new Date().getMonth() + 1);
  const [activeTab, setActiveTab] = useState("primes");

  return (
    <div className="space-y-6">
      <RhPageHeader
        title="Primes"
        description="Gestion des primes mensuelles et simulation de la participation & intéressement"
      />

      {/* Onglets principaux */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-1 gap-1 sm:grid-cols-2">
          <TabsTrigger value="primes" className="flex items-center gap-2">
            <Gift className="h-4 w-4" />
            Primes
          </TabsTrigger>
          <TabsTrigger value="participation" className="flex items-center gap-2">
            <Calculator className="h-4 w-4" />
            Participation & Intéressement
          </TabsTrigger>
        </TabsList>

        {/* Sous-onglet : Primes */}
        <TabsContent value="primes" className="space-y-6 mt-6">
          <PrimesTab
            selectedYear={selectedYear}
            selectedMonth={selectedMonth}
            onYearChange={setSelectedYear}
            onMonthChange={setSelectedMonth}
          />
        </TabsContent>

        {/* Sous-onglet : Participation & Intéressement */}
        <TabsContent value="participation" className="space-y-6 mt-6">
          <ParticipationInteressementTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}