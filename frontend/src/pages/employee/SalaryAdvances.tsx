// frontend/src/pages/employee/SalaryAdvances.tsx

import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Clock, Plus } from 'lucide-react';
import type { SalaryAdvance } from '@/api/saisiesAvances';
import {
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';
import { EmployeeSalaryAdvanceStatusBadge } from '@/components/employee-salary-advances/EmployeeSalaryAdvanceStatusBadge';
import { AdvanceAvailableSummary } from '@/components/saisies-avances/AdvanceAvailableSummary';
import { SalaryAdvanceDetail } from '@/components/saisies-avances/SalaryAdvanceDetail';
import { SalaryAdvanceRequestForm } from '@/components/saisies-avances/SalaryAdvanceRequestForm';
import { EmployeeSalaryAdvancesSkeleton } from '@/components/skeletons/EmployeeSalaryAdvancesSkeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useEmployeeProfileQuery } from '@/hooks/queries/useEmployeeDashboardQueries';
import { useEmployeeSalaryAdvancesQuery } from '@/hooks/queries/useEmployeeSalaryAdvancesQuery';
import { queryKeys } from '@/lib/queryKeys';
import { formatCurrency } from '@/lib/employeeDashboardUtils';
import {
  getAdvanceTypeLabel,
  filterAdvancesByStatus,
  formatAdvanceDate,
  hasApprovedAmountDiff,
  showRemainingRepayment,
  type SalaryAdvanceStatusFilter,
  VALID_STATUS_FILTERS,
} from '@/lib/employeeSalaryAdvancesUtils';

const STATUS_FILTER_LABELS: Record<SalaryAdvanceStatusFilter, string> = {
  all: 'Toutes',
  pending: 'En attente',
  approved: 'À verser',
  paid: 'Versées',
  rejected: 'Rejetées',
};

function todayIsoDate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function AdvanceRowActions({
  onView,
}: {
  onView: () => void;
}) {
  return (
    <Button variant="ghost" size="sm" onClick={onView}>
      Voir détails
    </Button>
  );
}

function AdvanceMobileCard({
  advance,
  onView,
}: {
  advance: SalaryAdvance;
  onView: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onView}
      className="w-full rounded-lg border bg-card p-4 text-left transition-colors hover:bg-muted/50"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs text-muted-foreground">
            {getAdvanceTypeLabel(advance.advance_type, advance.prime_label)}
          </p>
          <p className="text-lg font-semibold">
            {formatCurrency(advance.requested_amount)}
          </p>
          {hasApprovedAmountDiff(advance) && (
            <p className="text-sm text-muted-foreground">
              Approuvé : {formatCurrency(advance.approved_amount)}
            </p>
          )}
        </div>
        <EmployeeSalaryAdvanceStatusBadge status={advance.status} />
      </div>
      <div className="mt-2 space-y-1 text-sm text-muted-foreground">
        <p>Versement souhaité : {formatAdvanceDate(advance.requested_date)}</p>
        <p>Déposée le : {formatAdvanceDate(advance.created_at)}</p>
        {showRemainingRepayment(advance) && (
          <p className="text-foreground">
            Reste à rembourser : {formatCurrency(advance.remaining_amount)}
          </p>
        )}
      </div>
    </button>
  );
}

export default function SalaryAdvances() {
  const { toast } = useToast();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const userId = user?.id;
  const { data: employeeProfile } = useEmployeeProfileQuery(userId);
  const resolvedEmployeeId = employeeProfile?.id;
  const salaryAdvancesQuery = useEmployeeSalaryAdvancesQuery(userId);
  const [searchParams, setSearchParams] = useSearchParams();
  const [showForm, setShowForm] = useState(false);
  const [selectedAdvance, setSelectedAdvance] = useState<SalaryAdvance | null>(null);
  const requestsListRef = useRef<HTMLDivElement>(null);

  const advances = salaryAdvancesQuery.data?.advances ?? [];
  const availableAmount = salaryAdvancesQuery.data?.available ?? null;
  const isLoading = salaryAdvancesQuery.isLoading;
  const loadError = salaryAdvancesQuery.isError;

  const refreshAdvances = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.employeeSalaryAdvances(userId) });

  const statusFilter = useMemo((): SalaryAdvanceStatusFilter => {
    const raw = searchParams.get('status');
    if (raw && VALID_STATUS_FILTERS.has(raw as SalaryAdvanceStatusFilter)) {
      return raw as SalaryAdvanceStatusFilter;
    }
    return 'all';
  }, [searchParams]);

  useEffect(() => {
    if (salaryAdvancesQuery.isError) {
      toast({
        title: 'Erreur',
        description: 'Impossible de charger les données.',
        variant: 'destructive',
      });
    }
  }, [salaryAdvancesQuery.isError, toast]);

  useEffect(() => {
    if (searchParams.get('new') === '1') {
      setShowForm(true);
    }
  }, [searchParams]);

  const pendingCount = useMemo(
    () => advances.filter((a) => a.status === 'pending').length,
    [advances]
  );

  const filteredAdvances = useMemo(
    () => filterAdvancesByStatus(advances, statusFilter),
    [advances, statusFilter]
  );

  const anyShowsApprovedColumn = useMemo(
    () => advances.some(hasApprovedAmountDiff),
    [advances]
  );

  const anyShowsRemainingColumn = useMemo(
    () => advances.some(showRemainingRepayment),
    [advances]
  );

  const availableNumeric = Number(availableAmount?.available_amount ?? 0);
  const canRequest = availableNumeric > 0;

  const openRequestForm = () => {
    setShowForm(true);
    const next = new URLSearchParams(searchParams);
    next.set('new', '1');
    setSearchParams(next, { replace: true });
  };

  const closeRequestForm = () => {
    setShowForm(false);
    const next = new URLSearchParams(searchParams);
    next.delete('new');
    setSearchParams(next, { replace: true });
  };

  const handleStatusFilterChange = (filter: SalaryAdvanceStatusFilter) => {
    const next = new URLSearchParams(searchParams);
    if (filter === 'all') {
      next.delete('status');
    } else {
      next.set('status', filter);
    }
    setSearchParams(next, { replace: true });
  };

  const scrollToPending = () => {
    handleStatusFilterChange('pending');
    requestsListRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (isLoading && !advances.length && !availableAmount) {
    return <EmployeeSalaryAdvancesSkeleton />;
  }

  const requestButton = (
    <Button onClick={openRequestForm} disabled={!canRequest}>
      <Plus className="mr-2 h-4 w-4" />
      Demander une avance ou un acompte
    </Button>
  );

  return (
    <TooltipProvider>
      <EmployeePageShell>
        <EmployeePageHeader
          title="Avances & acomptes"
          description="Avance sur salaire ou acompte sur salaire déjà gagné — suivi de vos demandes"
          actions={
            canRequest ? (
              requestButton
            ) : (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-block">{requestButton}</span>
                </TooltipTrigger>
                <TooltipContent>
                  Aucun montant disponible pour le moment
                </TooltipContent>
              </Tooltip>
            )
          }
        />

        {pendingCount > 0 && (
          <Alert className="border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30">
            <Clock className="h-4 w-4 text-amber-700" />
            <AlertDescription className="flex flex-wrap items-center justify-between gap-2 text-amber-950 dark:text-amber-100">
              <span>
                {pendingCount} demande{pendingCount > 1 ? 's' : ''} en attente de
                validation RH
              </span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="border-amber-300 bg-white hover:bg-amber-100 dark:bg-transparent"
                onClick={scrollToPending}
              >
                Voir les demandes
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {loadError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="flex flex-wrap items-center justify-between gap-2">
              <span>Impossible de charger vos avances.</span>
              <Button type="button" variant="outline" size="sm" onClick={() => void refreshAdvances()}>
                Réessayer
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {availableAmount && <AdvanceAvailableSummary data={availableAmount} />}

        <div ref={requestsListRef}>
        <Card>
          <CardHeader className="space-y-3">
            <CardTitle>Mes demandes</CardTitle>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(STATUS_FILTER_LABELS) as SalaryAdvanceStatusFilter[]).map(
                (key) => (
                  <Button
                    key={key}
                    type="button"
                    size="sm"
                    variant={statusFilter === key ? 'default' : 'outline'}
                    onClick={() => handleStatusFilterChange(key)}
                  >
                    {STATUS_FILTER_LABELS[key]}
                  </Button>
                )
              )}
            </div>
          </CardHeader>
          <CardContent>
            {filteredAdvances.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-4 py-12 text-center">
                <p className="text-muted-foreground">
                  {advances.length === 0
                    ? "Vous n'avez pas encore fait de demande d'avance."
                    : 'Aucune demande pour ce filtre.'}
                </p>
                {advances.length === 0 && canRequest && (
                  <Button onClick={openRequestForm}>
                    <Plus className="mr-2 h-4 w-4" />
                    Faire une première demande
                  </Button>
                )}
              </div>
            ) : (
              <>
                <div className="space-y-3 md:hidden">
                  {filteredAdvances.map((advance) => (
                    <AdvanceMobileCard
                      key={advance.id}
                      advance={advance}
                      onView={() => setSelectedAdvance(advance)}
                    />
                  ))}
                </div>

                <div className="hidden md:block">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Nature</TableHead>
                        <TableHead>Montant demandé</TableHead>
                        {anyShowsApprovedColumn && (
                          <TableHead>Montant approuvé</TableHead>
                        )}
                        <TableHead>Versement souhaité</TableHead>
                        <TableHead>Déposée le</TableHead>
                        <TableHead>Statut</TableHead>
                        {anyShowsRemainingColumn && (
                          <TableHead>Reste à rembourser</TableHead>
                        )}
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredAdvances.map((advance) => (
                        <TableRow
                          key={advance.id}
                          className="cursor-pointer"
                          onClick={() => setSelectedAdvance(advance)}
                        >
                          <TableCell className="text-sm">
                            {getAdvanceTypeLabel(advance.advance_type, advance.prime_label)}
                          </TableCell>
                          <TableCell className="font-medium">
                            {formatCurrency(advance.requested_amount)}
                          </TableCell>
                          {anyShowsApprovedColumn && (
                            <TableCell>
                              {hasApprovedAmountDiff(advance)
                                ? formatCurrency(advance.approved_amount)
                                : '—'}
                            </TableCell>
                          )}
                          <TableCell>
                            {formatAdvanceDate(advance.requested_date)}
                          </TableCell>
                          <TableCell>
                            {formatAdvanceDate(advance.created_at)}
                          </TableCell>
                          <TableCell>
                            <EmployeeSalaryAdvanceStatusBadge status={advance.status} />
                          </TableCell>
                          {anyShowsRemainingColumn && (
                            <TableCell>
                              {showRemainingRepayment(advance)
                                ? formatCurrency(advance.remaining_amount)
                                : '—'}
                            </TableCell>
                          )}
                          <TableCell
                            className="text-right"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <AdvanceRowActions
                              onView={() => setSelectedAdvance(advance)}
                            />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </>
            )}
          </CardContent>
        </Card>
        </div>

        {showForm && (
          <SalaryAdvanceRequestForm
            employeeId={resolvedEmployeeId}
            hideEmployeeSelector
            defaultRequestedDate={todayIsoDate()}
            onClose={closeRequestForm}
            onSuccess={() => {
              closeRequestForm();
              void refreshAdvances();
            }}
          />
        )}

        {selectedAdvance && (
          <SalaryAdvanceDetail
            advance={selectedAdvance}
            onClose={() => setSelectedAdvance(null)}
            onUpdate={refreshAdvances}
          />
        )}
      </EmployeePageShell>
    </TooltipProvider>
  );
}
