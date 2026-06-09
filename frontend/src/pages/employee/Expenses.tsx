import { log } from '@/lib/logger';
import { useState, useEffect, useMemo, useCallback, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { PlusCircle, AlertCircle, RefreshCw } from 'lucide-react';
import {
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';
import { useToast } from '@/components/ui/use-toast';
import { NewExpenseModal } from '@/components/NewExpenseModal';
import { useAuth } from '@/contexts/AuthContext';
import { useEmployeeExpensesQuery } from '@/hooks/queries/useEmployeeDashboardQueries';
import { queryKeys } from '@/lib/queryKeys';
import { formatCurrency } from '@/lib/employeeDashboardUtils';
import {
  countExpensesByStatus,
  formatExpenseDate,
  truncateDescription,
} from '@/lib/employeeExpensesUtils';
import { EmployeeExpensesKpiBand } from '@/components/expenses/EmployeeExpensesKpiBand';
import { EmployeeExpenseReceiptActions } from '@/components/expenses/EmployeeExpenseReceiptActions';
import { ExpenseStatusBadge } from '@/components/expenses/ExpenseStatusBadge';
import type { Expense, ExpenseStatus } from '@/api/expenses';
import { formatExpenseVatSummary } from '@/lib/expenseVat';
import { downloadBlob, openBlobInNewTab } from '@/lib/downloadBlob';

const VALID_STATUS_FILTERS: ExpenseStatus[] = ['pending', 'validated', 'rejected'];

function FilterButton({
  active,
  onClick,
  children,
  count,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  count?: number;
}) {
  return (
    <Button type="button" size="sm" variant={active ? 'default' : 'outline'} onClick={onClick}>
      {children}
      {count !== undefined && count > 0 && (
        <Badge variant={active ? 'secondary' : 'outline'} className="ml-2 tabular-nums">
          {count}
        </Badge>
      )}
    </Button>
  );
}

function ExpenseMobileCard({
  expense,
  onDownload,
}: {
  expense: Expense;
  onDownload: (expense: Expense) => void;
}) {
  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium">{formatExpenseDate(expense.date)}</p>
          <p className="text-sm text-muted-foreground">{expense.type}</p>
        </div>
        <ExpenseStatusBadge status={expense.status} />
      </div>
      <p className="text-lg font-semibold tabular-nums">{formatCurrency(expense.amount)} TTC</p>
      {(() => {
        const vatLine = formatExpenseVatSummary(expense, { includeTtc: false });
        return vatLine ? (
          <p className="text-xs text-muted-foreground tabular-nums">{vatLine}</p>
        ) : null;
      })()}
      {expense.description?.trim() && (
        <p className="text-sm text-muted-foreground">{expense.description}</p>
      )}
      <p className="text-xs text-muted-foreground">
        Soumis le {formatExpenseDate(expense.created_at)}
      </p>
      <EmployeeExpenseReceiptActions expense={expense} onDownload={onDownload} compact />
    </div>
  );
}

function ExpensesTableSkeleton() {
  return (
    <>
      {Array.from({ length: 4 }).map((_, i) => (
        <TableRow key={i}>
          {Array.from({ length: 7 }).map((__, j) => (
            <TableCell key={j}>
              <Skeleton className="h-4 w-full max-w-[120px]" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  );
}

export default function ExpensesPage() {
  const { toast } = useToast();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [isModalOpen, setIsModalOpen] = useState(false);

  const {
    data: expenses = [],
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useEmployeeExpensesQuery(user?.id);

  const statusFilter = useMemo(() => {
    const raw = searchParams.get('status');
    if (raw && VALID_STATUS_FILTERS.includes(raw as ExpenseStatus)) {
      return raw as ExpenseStatus;
    }
    return null;
  }, [searchParams]);

  const statusCounts = useMemo(() => countExpensesByStatus(expenses), [expenses]);

  const displayedExpenses = useMemo(() => {
    if (!statusFilter) return expenses;
    return expenses.filter((e) => e.status === statusFilter);
  }, [expenses, statusFilter]);

  useEffect(() => {
    if (searchParams.get('action') === 'new') {
      setIsModalOpen(true);
      const next = new URLSearchParams(searchParams);
      next.delete('action');
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const invalidateExpenses = useCallback(() => {
    void queryClient.invalidateQueries({
      queryKey: queryKeys.employeeDashboard(user?.id),
    });
  }, [queryClient, user?.id]);

  const handleDownload = async (expense: Expense) => {
    const signedUrl = expense.receipt_url;
    if (!signedUrl) {
      toast({
        title: 'Erreur',
        description: 'Aucun justificatif associé à cette dépense.',
        variant: 'destructive',
      });
      return;
    }

    try {
      const response = await fetch(signedUrl);
      if (!response.ok) {
        throw new Error(`Erreur réseau: ${response.statusText}`);
      }
      const blob = await response.blob();
      downloadBlob(blob, expense.filename || 'justificatif');
    } catch (error) {
      log.error('Erreur lors de la tentative de téléchargement:', error);
      toast({
        title: 'Erreur',
        description: 'Impossible de lancer le téléchargement.',
        variant: 'destructive',
      });
    }
  };

  const setStatusFilter = (status: ExpenseStatus | null) => {
    if (status === null) {
      setSearchParams({});
    } else {
      setSearchParams({ status });
    }
  };

  const renderEmptyState = () => {
    if (expenses.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
          <p className="text-muted-foreground">Vous n&apos;avez pas encore déclaré de note de frais.</p>
          <Button onClick={() => setIsModalOpen(true)}>
            <PlusCircle className="mr-2 h-4 w-4" />
            Déclarer ma première note
          </Button>
        </div>
      );
    }
    return (
      <p className="py-12 text-center text-muted-foreground">
        Aucune note pour ce filtre.
      </p>
    );
  };

  return (
    <>
      <EmployeePageShell>
        <EmployeePageHeader
          title="Mes notes de frais"
          description="Déclarez vos frais professionnels et suivez leur validation par les RH."
          actions={
            <Button onClick={() => setIsModalOpen(true)}>
              <PlusCircle className="mr-2 h-4 w-4" />
              Nouvelle dépense
            </Button>
          }
        />

        {!isLoading && !isError && expenses.length > 0 && (
          <EmployeeExpensesKpiBand
            pending={statusCounts.pending}
            rejected={statusCounts.rejected}
            validated={statusCounts.validated}
          />
        )}

        {isError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Chargement impossible</AlertTitle>
            <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <span>Impossible de charger vos notes de frais.</span>
              <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
                <RefreshCw className={`mr-2 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
                Réessayer
              </Button>
            </AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader className="space-y-3">
            <CardTitle>Suivi des dépenses</CardTitle>
            <div className="flex flex-wrap gap-2">
              <FilterButton active={statusFilter === null} onClick={() => setStatusFilter(null)}>
                Toutes
              </FilterButton>
              <FilterButton
                active={statusFilter === 'pending'}
                onClick={() => setStatusFilter('pending')}
                count={statusCounts.pending}
              >
                En attente
              </FilterButton>
              <FilterButton
                active={statusFilter === 'rejected'}
                onClick={() => setStatusFilter('rejected')}
                count={statusCounts.rejected}
              >
                Refusées
              </FilterButton>
              <FilterButton
                active={statusFilter === 'validated'}
                onClick={() => setStatusFilter('validated')}
                count={statusCounts.validated}
              >
                Validées
              </FilterButton>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {statusFilter === 'rejected' && statusCounts.rejected > 0 && (
              <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                {statusCounts.rejected} note{statusCounts.rejected > 1 ? 's' : ''} refusée
                {statusCounts.rejected > 1 ? 's' : ''} — vérifiez le justificatif ou contactez les RH.
              </div>
            )}

            {/* Mobile: cartes */}
            <div className="space-y-3 md:hidden">
              {isLoading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-36 w-full rounded-lg" />
                ))
              ) : isError ? null : displayedExpenses.length === 0 ? (
                renderEmptyState()
              ) : (
                displayedExpenses.map((e) => (
                  <ExpenseMobileCard key={e.id} expense={e} onDownload={handleDownload} />
                ))
              )}
            </div>

            {/* Desktop: table */}
            <div className="hidden md:block">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Soumis le</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Montant TTC</TableHead>
                    <TableHead>Justificatif</TableHead>
                    <TableHead className="text-right">Statut</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    <ExpensesTableSkeleton />
                  ) : isError ? (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                        Utilisez le bouton Réessayer ci-dessus.
                      </TableCell>
                    </TableRow>
                  ) : displayedExpenses.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7}>{renderEmptyState()}</TableCell>
                    </TableRow>
                  ) : (
                    displayedExpenses.map((e) => (
                      <TableRow key={e.id}>
                        <TableCell className="font-medium whitespace-nowrap">
                          {formatExpenseDate(e.date)}
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-muted-foreground">
                          {formatExpenseDate(e.created_at)}
                        </TableCell>
                        <TableCell>{e.type}</TableCell>
                        <TableCell className="max-w-[200px]">
                          {e.description?.trim() ? (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <span className="block truncate cursor-default">
                                    {truncateDescription(e.description, 40)}
                                  </span>
                                </TooltipTrigger>
                                {e.description.length > 40 && (
                                  <TooltipContent side="top" className="max-w-xs">
                                    {e.description}
                                  </TooltipContent>
                                )}
                              </Tooltip>
                            </TooltipProvider>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="tabular-nums whitespace-nowrap">
                          <div>{formatCurrency(e.amount)}</div>
                          {(() => {
                            const vatSummary = formatExpenseVatSummary(e, {
                              includeTtc: false,
                            });
                            return vatSummary ? (
                              <div className="text-xs text-muted-foreground font-normal">
                                {vatSummary}
                              </div>
                            ) : null;
                          })()}
                        </TableCell>
                        <TableCell>
                          <EmployeeExpenseReceiptActions
                            expense={e}
                            onDownload={handleDownload}
                          />
                        </TableCell>
                        <TableCell className="text-right">
                          <ExpenseStatusBadge status={e.status} />
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </EmployeePageShell>

      <NewExpenseModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={invalidateExpenses}
      />
    </>
  );
}
