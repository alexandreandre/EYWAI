import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getMyCetMovements, getMyCetSummary } from '@/api/cet';
import { EmployeeCetPanel } from '@/components/cet/EmployeeCetPanel';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAuth } from '@/contexts/AuthContext';
import { queryKeys } from '@/lib/queryKeys';

const MOVEMENT_LABELS: Record<string, string> = {
  deposit_hs: 'Épargne HS',
  deposit_cp: 'Transfert CP',
  withdraw_rest: 'Congé CET',
  adjustment: 'Ajustement',
};

const WORKFLOW_LABELS: Record<string, string> = {
  pending_manager: 'En attente directeur',
  pending: 'En attente RH',
  approved_manager: 'Validé manager',
};

export default function MonCetPage() {
  const { user } = useAuth();
  const year = new Date().getFullYear();

  const { data: summary } = useQuery({
    queryKey: queryKeys.employeeCetSummary(user?.id, year),
    queryFn: () => getMyCetSummary({ year }),
    enabled: Boolean(user?.id),
  });

  const { data: movements = [] } = useQuery({
    queryKey: ['employee', user?.id ?? 'none', 'cet', 'movements', year],
    queryFn: () => getMyCetMovements(year),
    enabled: Boolean(user?.id),
  });

  if (!summary?.cet_enabled) {
    return (
      <div className="container max-w-3xl py-8">
        <p className="text-muted-foreground text-sm">
          Le compte épargne-temps n&apos;est pas activé pour votre entreprise.
        </p>
      </div>
    );
  }

  return (
    <div className="container max-w-3xl py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Mon compte épargne-temps</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Solde : {summary.balance_days.toFixed(1)} j ({summary.balance_hours.toFixed(1)} h)
        </p>
      </div>

      <EmployeeCetPanel variant="card" year={year} />

      {!summary.has_manager && summary.settings.validation_mode.includes('manager') ? (
        <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-md p-3">
          Aucun manager d&apos;équipe n&apos;est configuré : vos demandes seront transmises
          directement à la RH.
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Historique {year}</CardTitle>
        </CardHeader>
        <CardContent>
          {movements.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun mouvement cette année.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Montant</TableHead>
                  <TableHead>Statut</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[...movements].reverse().map((m) => (
                  <TableRow key={m.id}>
                    <TableCell>
                      {m.created_at
                        ? new Date(m.created_at).toLocaleDateString('fr-FR')
                        : '—'}
                    </TableCell>
                    <TableCell>{MOVEMENT_LABELS[m.movement_type] ?? m.movement_type}</TableCell>
                    <TableCell>
                      {m.movement_type === 'deposit_cp' ? `${m.days} j` : `${m.hours} h`}
                    </TableCell>
                    <TableCell>
                      {m.status === 'pending'
                        ? WORKFLOW_LABELS[m.workflow_step] ?? 'En attente'
                        : m.status}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Button variant="link" className="px-0" asChild>
        <Link to="/absences">Voir aussi mes absences</Link>
      </Button>
    </div>
  );
}
