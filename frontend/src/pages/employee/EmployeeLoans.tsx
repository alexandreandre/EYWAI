import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Landmark } from 'lucide-react';
import {
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';
import { EmployeeLoanDetailDrawer } from '@/components/employee-loans/EmployeeLoanDetailDrawer';
import { Badge } from '@/components/ui/badge';
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
import { Alert, AlertDescription } from '@/components/ui/alert';
import { TableSkeleton } from '@/components/skeletons/TableSkeleton';
import { useAuth } from '@/contexts/AuthContext';
import { queryKeys } from '@/lib/queryKeys';
import {
  LOAN_STATUS_COLORS,
  LOAN_STATUS_LABELS,
  getMyEmployeeLoans,
  type EmployeeLoan,
  type LoanStatus,
} from '@/api/employeeLoans';

const formatEuro = (value: number) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(value);

export default function EmployeeLoansPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selectedLoan, setSelectedLoan] = useState<EmployeeLoan | null>(null);
  const [filter, setFilter] = useState<LoanStatus | 'all'>('all');

  const loansQuery = useQuery({
    queryKey: queryKeys.employeeLoansSelf(user?.id),
    queryFn: getMyEmployeeLoans,
    enabled: Boolean(user?.id),
  });

  const loans = loansQuery.data ?? [];
  const filtered = useMemo(
    () => (filter === 'all' ? loans : loans.filter((l) => l.status === filter)),
    [loans, filter],
  );

  const activeTotal = loans
    .filter((l) => l.status === 'active')
    .reduce((s, l) => s + l.remaining_capital, 0);

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.employeeLoansSelf(user?.id) });

  return (
    <EmployeePageShell>
      <EmployeePageHeader
        title="Mes prêts employeur"
        description="Consultez vos prêts, l'échéancier et téléchargez votre contrat."
        icon={<Landmark className="h-6 w-6" />}
      />

      {activeTotal > 0 && (
        <Alert className="mb-4">
          <AlertDescription>
            Capital restant dû sur vos prêts actifs :{' '}
            <strong>{formatEuro(activeTotal)}</strong>. Les mensualités sont prélevées sur votre
            bulletin de paie.
          </AlertDescription>
        </Alert>
      )}

      <Card className="mb-4">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Mes prêts</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-wrap gap-2">
            {(['all', 'active', 'repaid', 'suspended'] as const).map((status) => (
              <Button
                key={status}
                size="sm"
                variant={filter === status ? 'default' : 'outline'}
                onClick={() => setFilter(status)}
              >
                {status === 'all' ? 'Tous' : LOAN_STATUS_LABELS[status]}
              </Button>
            ))}
          </div>

          {loansQuery.isLoading ? (
            <TableSkeleton rows={4} cols={5} />
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucun prêt employeur enregistré pour votre compte.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Montant initial</TableHead>
                  <TableHead>Reste dû</TableHead>
                  <TableHead>Mensualité</TableHead>
                  <TableHead>Début</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((loan) => (
                  <TableRow key={loan.id}>
                    <TableCell>{formatEuro(loan.principal_amount)}</TableCell>
                    <TableCell>{formatEuro(loan.remaining_capital)}</TableCell>
                    <TableCell>{formatEuro(loan.monthly_payment)}</TableCell>
                    <TableCell>
                      {new Date(loan.start_date).toLocaleDateString('fr-FR')}
                    </TableCell>
                    <TableCell>
                      <Badge className={LOAN_STATUS_COLORS[loan.status]}>
                        {LOAN_STATUS_LABELS[loan.status]}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="ghost" onClick={() => setSelectedLoan(loan)}>
                        Détails
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <EmployeeLoanDetailDrawer
        loan={selectedLoan}
        open={Boolean(selectedLoan)}
        onOpenChange={(open) => !open && setSelectedLoan(null)}
        onRefresh={refresh}
        mode="employee"
      />
    </EmployeePageShell>
  );
}
