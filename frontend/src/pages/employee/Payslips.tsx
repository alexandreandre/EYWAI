// src/pages/employee/Payslips.tsx (COMPLET, FONCTIONNEL AVEC BACKEND À JOUR)

import { useMemo } from 'react';
import {
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';
import { Download, BarChart2, Euro, CalendarDays, TrendingUp, LineChart } from 'lucide-react';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip as RechartsTooltip } from 'recharts';
import { useAuth } from '@/contexts/AuthContext';
import { Label } from '@/components/ui/label';
import {
  useEmployeeCumulsQuery,
  useEmployeePayslipsQuery,
  useEmployeeProfileQuery,
} from '@/hooks/queries/useEmployeeDashboardQueries';
import { formatCurrency } from '@/lib/employeeDashboardUtils';
import type { PayslipInfo } from '@/lib/employeeDashboardUtils';

const formatMonthYear = (month: number, year: number) => {
  return new Date(year, month - 1).toLocaleString('fr-FR', { month: 'long', year: 'numeric' });
};

function sortPayslips(items: PayslipInfo[]) {
  return [...items].sort((a, b) => {
    if (a.year !== b.year) return b.year - a.year;
    return b.month - a.month;
  });
}

export default function PayslipsPage() {
  const { user } = useAuth();
  const userId = user?.id;

  const payslipsQuery = useEmployeePayslipsQuery(userId);
  const profileQuery = useEmployeeProfileQuery(userId);
  const cumulsQuery = useEmployeeCumulsQuery(userId);

  const payslips = useMemo(
    () => sortPayslips(payslipsQuery.data ?? []),
    [payslipsQuery.data],
  );

  const partialError =
    payslipsQuery.isError || profileQuery.isError || cumulsQuery.isError;

  const salaryEvolutionData = payslips
    .filter((p) => p.net_a_payer != null && !Number.isNaN(p.net_a_payer))
    .slice(0, 6)
    .map((p) => ({
      name: new Date(p.year, p.month - 1).toLocaleString('fr-FR', { month: 'short' }),
      Net: p.net_a_payer,
    }))
    .reverse();

  const cumuls = cumulsQuery.data;
  const salaryInfo = profileQuery.data;

  return (
    <EmployeePageShell>
      <EmployeePageHeader title="Ma Rémunération" />

      {partialError && !payslipsQuery.isLoading && (
        <Card className="border-destructive bg-destructive/10">
          <CardContent className="pt-6 text-destructive text-sm font-medium">
            Certaines informations n&apos;ont pas pu être chargées.
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><Euro className="mr-2 h-5 w-5" />Mon Salaire Actuel</CardTitle>
          <CardDescription>Informations principales de votre rémunération contractuelle.</CardDescription>
        </CardHeader>
        <CardContent>
          {profileQuery.isLoading ? (
            <SharkFinLoader label="Chargement du salaire…" />
          ) : salaryInfo ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-muted-foreground">Salaire de base mensuel</Label>
                <p className="text-lg font-semibold">{formatCurrency(salaryInfo.salaire_de_base?.valeur)}</p>
              </div>
            </div>
          ) : !profileQuery.isError ? (
            <p className="text-sm text-muted-foreground">Informations salariales non disponibles.</p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><TrendingUp className="mr-2 h-5 w-5" />Cumuls Annuels</CardTitle>
          <CardDescription>
            Total de l&apos;année {cumuls?.periode?.annee_en_cours || new Date().getFullYear()}
            {cumuls?.periode?.dernier_mois_calcule
              ? ` (arrêtés fin ${formatMonthYear(cumuls.periode.dernier_mois_calcule, cumuls.periode.annee_en_cours || new Date().getFullYear())})`
              : ' (données non disponibles)'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {cumulsQuery.isLoading ? (
            <SharkFinLoader label="Chargement des cumuls…" />
          ) : cumuls?.cumuls ? (
            <div className="grid grid-cols-1 gap-y-4 gap-x-6 sm:grid-cols-3">
              <div>
                <Label className="text-xs text-muted-foreground">Brut Total</Label>
                <p className="font-semibold">{formatCurrency(cumuls.cumuls.brut_total)}</p>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Net Imposable</Label>
                <p className="font-semibold">{formatCurrency(cumuls.cumuls.net_imposable)}</p>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Impôt Prélevé (PAS)</Label>
                <p className="font-semibold">{formatCurrency(cumuls.cumuls.impot_preleve_a_la_source)}</p>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Heures Rémunérées</Label>
                <p className="font-semibold">{cumuls.cumuls.heures_remunerees?.toFixed(2) ?? 'N/A'} h</p>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Heures Supp. Rémunérées</Label>
                <p className="font-semibold">{cumuls.cumuls.heures_supplementaires_remunerees?.toFixed(2) ?? 'N/A'} h</p>
              </div>
            </div>
          ) : !cumulsQuery.isError ? (
            <p className="text-sm text-muted-foreground">
              Les cumuls annuels ne sont pas encore disponibles.
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><BarChart2 className="mr-2 h-5 w-5" />Évolution du Net à Payer (6 derniers mois)</CardTitle>
        </CardHeader>
        <CardContent className="h-[250px] w-full">
          {payslipsQuery.isLoading ? (
            <SharkFinLoader label="Chargement du graphique…" />
          ) : salaryEvolutionData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={salaryEvolutionData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                <XAxis dataKey="name" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis
                  stroke="#888888"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => `${value.toLocaleString('fr-FR')}€`}
                  width={80}
                />
                <RechartsTooltip
                  cursor={{ fill: 'hsl(var(--muted))' }}
                  contentStyle={{ backgroundColor: 'hsl(var(--background))', border: '1px solid hsl(var(--border))', borderRadius: 'var(--radius)', padding: '8px' }}
                  labelStyle={{ fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}
                  itemStyle={{ fontSize: '12px' }}
                  formatter={(value: number) => [formatCurrency(value), 'Net à payer']}
                />
                <Bar dataKey="Net" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : !payslipsQuery.isError ? (
            <p className="text-center text-sm text-muted-foreground pt-16">
              Données indisponibles pour afficher le graphique.
              <br />
              <span className="text-xs">(Vérifiez que les bulletins de paie récents contiennent le montant net à payer)</span>
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><CalendarDays className="mr-2 h-5 w-5" />Mes Bulletins de Paie</CardTitle>
          <CardDescription>Historique de vos bulletins disponibles en téléchargement.</CardDescription>
        </CardHeader>
        <CardContent>
          {payslipsQuery.isLoading ? (
            <SharkFinLoader label="Chargement des bulletins…" />
          ) : payslips.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Période</TableHead>
                  <TableHead className="text-right">Analyse</TableHead>
                  <TableHead className="text-right">Télécharger</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {payslips.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium capitalize">
                      {formatMonthYear(p.month, p.year)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" asChild title="Comparaison et tendance">
                        <Link to={`/employee/payslips/${p.id}`}>
                          <LineChart className="mr-1.5 h-4 w-4" />
                          Comparer
                        </Link>
                      </Button>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" asChild>
                        <a href={p.url} download={p.name} title={`Télécharger ${p.name}`}>
                          <Download className="h-4 w-4" />
                        </a>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : !payslipsQuery.isError ? (
            <p className="text-sm text-muted-foreground text-center py-8">Aucun bulletin de paie trouvé.</p>
          ) : null}
        </CardContent>
      </Card>
    </EmployeePageShell>
  );
}
