import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { RhPageHeader } from '@/components/layout';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { TableSkeleton } from '@/components/skeletons/TableSkeleton';
import { PageFetchIndicator } from '@/components/skeletons/PageFetchIndicator';
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
import { Badge } from '@/components/ui/badge';
import { Plus, Eye, Landmark, AlertTriangle } from 'lucide-react';
import {
  LOAN_STATUS_COLORS,
  LOAN_STATUS_LABELS,
  listEmployeeLoans,
  type EmployeeLoan,
  type LoanStatus,
} from '@/api/employeeLoans';
import { EmployeeLoanFormModal } from '@/components/employee-loans/EmployeeLoanFormModal';
import { EmployeeLoanDetailDrawer } from '@/components/employee-loans/EmployeeLoanDetailDrawer';

const formatEuro = (value: number) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(value);

export default function EmployeeLoans() {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [selectedLoan, setSelectedLoan] = useState<EmployeeLoan | null>(null);
  const [filterStatus, setFilterStatus] = useState<LoanStatus | 'all'>('all');

  const loansQuery = useQuery({
    queryKey: queryKeys.employeeLoans(companyId),
    queryFn: () => listEmployeeLoans(),
    enabled: Boolean(companyId),
  });

  const loans = loansQuery.data ?? [];
  const filtered =
    filterStatus === 'all' ? loans : loans.filter((l) => l.status === filterStatus);

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.employeeLoans(companyId) });

  const stats = {
    active: loans.filter((l) => l.status === 'active').length,
    totalOutstanding: loans
      .filter((l) => l.status === 'active')
      .reduce((s, l) => s + l.remaining_capital, 0),
    needs2062: loans.filter((l) => l.requires_2062_declaration && !l.declared_2062).length,
  };

  return (
    <div className="space-y-6">
      <PageFetchIndicator isFetching={loansQuery.isFetching} />
      <RhPageHeader
        title="Prêts employeur"
        icon={<Landmark />}
        description="Prêts d'argent de l'entreprise aux salariés — échéancier, retenue paie, contrat"
        actions={
          <Button onClick={() => setShowForm(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Nouveau prêt
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Prêts actifs</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats.active}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Capital restant dû</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{formatEuro(stats.totalOutstanding)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium" title="Prêts ≥ 5 000 € non encore déclarés au formulaire 2062">
              Déclarations 2062 à faire
            </CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-2">
            <p className="text-2xl font-bold">{stats.needs2062}</p>
            {stats.needs2062 > 0 && <AlertTriangle className="h-5 w-5 text-amber-500" />}
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-wrap gap-2">
        {(['all', 'active', 'draft', 'repaid', 'suspended', 'cancelled', 'defaulted'] as const).map(
          (status) => (
            <Button
              key={status}
              size="sm"
              variant={filterStatus === status ? 'default' : 'outline'}
              onClick={() => setFilterStatus(status)}
            >
              {status === 'all' ? 'Tous' : LOAN_STATUS_LABELS[status]}
            </Button>
          ),
        )}
      </div>

      <Card>
        <CardContent className="pt-6">
          {loansQuery.isLoading ? (
            <TableSkeleton rows={5} cols={7} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Montant</TableHead>
                  <TableHead>Reste dû</TableHead>
                  <TableHead>Mensualité</TableHead>
                  <TableHead>Début</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground">
                      Aucun prêt
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((loan) => (
                    <TableRow key={loan.id}>
                      <TableCell>{loan.employee_name ?? loan.employee_id}</TableCell>
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
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setSelectedLoan(loan)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <EmployeeLoanFormModal
        open={showForm}
        onOpenChange={setShowForm}
        onSuccess={refresh}
      />

      <EmployeeLoanDetailDrawer
        loan={selectedLoan}
        open={Boolean(selectedLoan)}
        onOpenChange={(open) => !open && setSelectedLoan(null)}
        onRefresh={refresh}
      />
    </div>
  );
}
