// frontend/src/components/saisies-avances/SaisiesAvancesDashboard.tsx

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, AlertCircle, CheckCircle, Clock, Scale, Wallet } from "lucide-react";
import { getSalarySeizures, getSalaryAdvances } from '@/api/saisiesAvances';
import type { SalarySeizure, SalaryAdvance } from '@/api/saisiesAvances';

export function SaisiesAvancesDashboard() {
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState({
    activeSeizures: 0,
    pendingAdvances: 0,
    totalSeizures: 0,
    totalAdvances: 0,
  });

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [seizures, advances] = await Promise.all([
          getSalarySeizures(),
          getSalaryAdvances(),
        ]);

        setStats({
          activeSeizures: seizures.filter(s => s.status === 'active').length,
          pendingAdvances: advances.filter(a => a.status === 'pending').length,
          totalSeizures: seizures.length,
          totalAdvances: advances.length,
        });
      } catch (error) {
        console.error('Erreur lors du chargement des statistiques:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchStats();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Saisies actives</CardTitle>
          <Scale className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.activeSeizures}</div>
          <p className="text-xs text-muted-foreground">
            sur {stats.totalSeizures} saisies au total
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Avances en attente</CardTitle>
          <Clock className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.pendingAdvances}</div>
          <p className="text-xs text-muted-foreground">
            nécessitent une validation
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total saisies</CardTitle>
          <AlertCircle className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.totalSeizures}</div>
          <p className="text-xs text-muted-foreground">
            toutes périodes confondues
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total avances</CardTitle>
          <Wallet className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.totalAdvances}</div>
          <p className="text-xs text-muted-foreground">
            toutes périodes confondues
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
