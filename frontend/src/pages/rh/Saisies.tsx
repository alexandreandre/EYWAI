// src/pages/Saisies.tsx - Page avec sous-onglets Primes et Participation & Intéressement

import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { moisDePaieParDefaut } from '@/features/payroll/utils/payrollMonth';
import { RhPageHeader } from '@/components/layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Gift, Calculator } from "lucide-react";
import { PrimesTab } from "@/components/saisies/PrimesTab";
import { ParticipationInteressementTab } from "@/components/saisies/ParticipationInteressementTab";

export default function Saisies() {
  // Mois de PAIE par défaut (≤ 15 → mois précédent), pas le mois calendaire :
  // une prime saisie « pour la paie en cours » doit tomber sur le mois du
  // bulletin — une PPV saisie sur le mauvais mois n'atteint jamais le
  // bulletin (retour Gaëlle 07/09).
  const moisPaie = moisDePaieParDefaut(new Date());

  // Arrivée depuis un bulletin (« Corriger la variable ») : le mois et le
  // salarié sont dans l'URL, sinon on retombe sur le mois de paie par défaut.
  const [searchParams, setSearchParams] = useSearchParams();
  const anneeUrl = Number(searchParams.get('year'));
  const moisUrl = Number(searchParams.get('month'));
  const employeUrl = searchParams.get('employee') || undefined;

  const [selectedYear, setSelectedYear] = useState<number>(
    Number.isInteger(anneeUrl) && anneeUrl > 1900 ? anneeUrl : moisPaie.year
  );
  const [selectedMonth, setSelectedMonth] = useState<number>(
    Number.isInteger(moisUrl) && moisUrl >= 1 && moisUrl <= 12 ? moisUrl : moisPaie.month
  );
  const [activeTab, setActiveTab] = useState("primes");

  // Changer de mois ou lever le filtre nettoie l'URL : le lien d'origine ne
  // doit pas ramener l'ancien salarié au rechargement.
  const oublierFiltreSalarie = () => {
    const suivant = new URLSearchParams(searchParams);
    suivant.delete('employee');
    setSearchParams(suivant, { replace: true });
  };

  return (
    <div className="space-y-6">
      <RhPageHeader
        title="Primes"
        description="Gestion des primes mensuelles, simulation et validation de la participation & intéressement"
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
            focusEmployeeId={employeUrl}
            onClearFocusEmployee={oublierFiltreSalarie}
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