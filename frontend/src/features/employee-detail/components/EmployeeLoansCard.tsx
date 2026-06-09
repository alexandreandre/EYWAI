import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Landmark, Plus, Eye } from 'lucide-react';
import {
  LOAN_STATUS_COLORS,
  LOAN_STATUS_LABELS,
  getEmployeeLoans,
  type EmployeeLoan,
} from '@/api/employeeLoans';
import { EmployeeLoanFormModal } from '@/components/employee-loans/EmployeeLoanFormModal';
import { EmployeeLoanDetailDrawer } from '@/components/employee-loans/EmployeeLoanDetailDrawer';

interface EmployeeLoansCardProps {
  employeeId: string;
  employeeName?: string;
  canEdit?: boolean;
}

const formatEuro = (value: number) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(value);

export function EmployeeLoansCard({
  employeeId,
  employeeName,
  canEdit = true,
}: EmployeeLoansCardProps) {
  const [showForm, setShowForm] = useState(false);
  const [selectedLoan, setSelectedLoan] = useState<EmployeeLoan | null>(null);

  const { data: loans = [], isLoading, refetch } = useQuery({
    queryKey: ['employee-loans', employeeId],
    queryFn: () => getEmployeeLoans(employeeId),
    enabled: Boolean(employeeId),
  });

  const activeLoans = loans.filter((l) => l.status === 'active');
  const totalRemaining = activeLoans.reduce((s, l) => s + l.remaining_capital, 0);

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <Landmark className="h-4 w-4" />
            Prêts employeur
          </CardTitle>
          {canEdit && (
            <Button size="sm" variant="outline" onClick={() => setShowForm(true)}>
              <Plus className="mr-1 h-4 w-4" />
              Nouveau
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Chargement…</p>
          ) : loans.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun prêt enregistré.</p>
          ) : (
            <>
              {activeLoans.length > 0 && (
                <p className="text-sm">
                  Capital restant dû :{' '}
                  <span className="font-semibold">{formatEuro(totalRemaining)}</span>
                </p>
              )}
              <ul className="space-y-2">
                {loans.slice(0, 5).map((loan) => (
                  <li
                    key={loan.id}
                    className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                  >
                    <div>
                      <span className="font-medium">{formatEuro(loan.principal_amount)}</span>
                      <Badge className={`ml-2 ${LOAN_STATUS_COLORS[loan.status]}`}>
                        {LOAN_STATUS_LABELS[loan.status]}
                      </Badge>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setSelectedLoan(loan)}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </CardContent>
      </Card>

      <EmployeeLoanFormModal
        open={showForm}
        onOpenChange={setShowForm}
        employeeId={employeeId}
        employeeName={employeeName}
        onSuccess={() => refetch()}
      />

      <EmployeeLoanDetailDrawer
        loan={selectedLoan}
        open={Boolean(selectedLoan)}
        onOpenChange={(open) => !open && setSelectedLoan(null)}
        onRefresh={() => refetch()}
      />
    </>
  );
}
