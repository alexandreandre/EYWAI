import { useEffect, useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useLocation } from 'react-router-dom';
import { AlertCircle, CalendarDays, Loader2, Palmtree, Pencil } from 'lucide-react';
import { updateEmployeeRttSolde } from '@/api/leaveSettings';
import { useCompany } from '@/contexts/CompanyContext';
import { useEmployeeAbsenceBalancesQuery } from '@/hooks/queries/useEmployeeAbsenceBalancesQuery';
import { EvenementFamilialBalanceDialog } from '@/components/dashboard/EvenementFamilialBalanceDialog';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { useToast } from '@/hooks/use-toast';
import { companyQueryKey, queryKeys } from '@/lib/queryKeys';
import {
  balanceUsesHours,
  formatBalanceRemaining,
  getRhLeaveBalanceShortLabel,
  isRhLeaveBalanceVisible,
} from '@/lib/employeeAbsencesUtils';
import { cn } from '@/lib/utils';

const EVENEMENT_FAMILIAL_TYPE = 'Événement familial';

interface EmployeeDetailLeaveBalancesTabProps {
  employeeId: string;
  hireDate?: string | null;
}

function formatAmount(value: number | string | undefined, unit: string): string {
  if (value === undefined || value === 'N/A') return '—';
  if (value === 'selon événement') return 'Selon événement';
  if (typeof value === 'number') return `${value.toFixed(1)} ${unit}`;
  return String(value);
}

function formatRttDraft(value: number | null): string {
  return value == null ? '' : value.toFixed(1);
}

export function EmployeeDetailLeaveBalancesTab({
  employeeId,
  hireDate,
}: EmployeeDetailLeaveBalancesTabProps) {
  const location = useLocation();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id;
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const balancesQuery = useEmployeeAbsenceBalancesQuery(employeeId);
  const visibleBalances =
    balancesQuery.data?.filter(isRhLeaveBalanceVisible) ?? [];
  const rttBalance = visibleBalances.find((balance) => balance.type === 'RTT');
  const currentRttRemaining =
    typeof rttBalance?.remaining === 'number' ? rttBalance.remaining : null;
  const currentYear = new Date().getFullYear();
  const [rttDialogOpen, setRttDialogOpen] = useState(false);
  const [rttYear, setRttYear] = useState(currentYear);
  const [rttSolde, setRttSolde] = useState(formatRttDraft(currentRttRemaining));
  const [rttNote, setRttNote] = useState('');

  useEffect(() => {
    if (!rttDialogOpen) return;
    setRttYear(currentYear);
    setRttSolde(formatRttDraft(currentRttRemaining));
    setRttNote('');
  }, [currentRttRemaining, currentYear, rttDialogOpen]);

  const rttMutation = useMutation({
    mutationFn: () => {
      const parsed = Number.parseFloat(rttSolde.replace(',', '.'));
      return updateEmployeeRttSolde(employeeId, rttYear, {
        rtt_solde: parsed,
        note: rttNote.trim() || null,
      });
    },
    onSuccess: () => {
      setRttDialogOpen(false);
      void queryClient.invalidateQueries({
        queryKey: queryKeys.employeeAbsenceBalances(companyId, employeeId),
      });
      void queryClient.invalidateQueries({
        queryKey: companyQueryKey(companyId, 'leave-balances-overview'),
      });
      toast({
        title: 'Solde RTT enregistré',
        description: 'Les soldes du salarié ont été recalculés.',
      });
    },
    onError: () => {
      toast({
        title: 'Solde RTT non enregistré',
        description: 'Vérifiez l’éligibilité RTT du salarié et réessayez.',
        variant: 'destructive',
      });
    },
  });

  const calendarHref = {
    pathname: location.pathname,
    search: '?tab=calendrier',
  };

  const parsedRttSolde = Number.parseFloat(rttSolde.replace(',', '.'));
  const rttSoldeInvalid = Number.isNaN(parsedRttSolde) || parsedRttSolde < 0;
  const rttActionDisabled = balancesQuery.isLoading || !hireDate;

  const handleSubmitRtt = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (rttSoldeInvalid || rttMutation.isPending) return;
    rttMutation.mutate();
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 space-y-0">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Palmtree className="h-5 w-5 shrink-0 text-primary" aria-hidden />
              Soldes de congés
            </CardTitle>
            <CardDescription>
              Droits acquis, jours pris et soldes restants (CP, RTT, repos compensateur, etc.).
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="shrink-0"
              disabled={rttActionDisabled}
              onClick={() => setRttDialogOpen(true)}
            >
              <Pencil className="mr-2 h-4 w-4" aria-hidden />
              Ajuster RTT
            </Button>
            <Button variant="outline" size="sm" asChild className="shrink-0">
              <Link to={calendarHref}>
                <CalendarDays className="mr-2 h-4 w-4" aria-hidden />
                Calendrier
              </Link>
            </Button>
          </div>
        </CardHeader>

        <CardContent>
          {balancesQuery.isLoading ? (
            <div className="flex min-h-[120px] items-center justify-center">
              <SharkFinLoader variant="compact" label="" />
            </div>
          ) : balancesQuery.isError ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Soldes indisponibles</AlertTitle>
              <AlertDescription>
                {!hireDate
                  ? 'Renseignez la date d’entrée du collaborateur pour calculer les soldes.'
                  : 'Impossible de charger les soldes. Vérifiez les paramètres congés de la société.'}
              </AlertDescription>
            </Alert>
          ) : visibleBalances.length === 0 ? (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Aucun solde affiché</AlertTitle>
              <AlertDescription>
                {!hireDate
                  ? 'Renseignez la date d’entrée du collaborateur pour calculer les soldes.'
                  : 'Vérifiez les paramètres congés de la société ou l’import des soldes CP initiaux.'}
              </AlertDescription>
            </Alert>
          ) : (
            <div className="overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead className="text-right">Acquis</TableHead>
                    <TableHead className="text-right">Pris</TableHead>
                    <TableHead className="text-right">Restant</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleBalances.map((balance) => {
                    const unit = balanceUsesHours(balance.type) ? 'h' : 'j';
                    const isFamilial = balance.type === EVENEMENT_FAMILIAL_TYPE;
                    const remainingDisplay = formatBalanceRemaining(balance.remaining, unit);

                    return (
                      <TableRow key={balance.type}>
                        <TableCell className="font-medium">
                          <span title={balance.type}>
                            {getRhLeaveBalanceShortLabel(balance.type)}
                          </span>
                          {balance.type !== getRhLeaveBalanceShortLabel(balance.type) ? (
                            <p className="text-xs font-normal text-muted-foreground">
                              {balance.type}
                            </p>
                          ) : null}
                        </TableCell>
                        <TableCell className="text-right tabular-nums text-muted-foreground">
                          {isFamilial ? '—' : formatAmount(balance.acquired, unit)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums text-muted-foreground">
                          {formatAmount(balance.taken, unit)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {isFamilial ? (
                            <EvenementFamilialBalanceDialog triggerLabel="Voir le détail" />
                          ) : (
                            <span
                              className={cn(
                                'font-semibold',
                                balance.remaining === 'N/A'
                                  ? 'text-muted-foreground'
                                  : 'text-primary',
                              )}
                            >
                              {remainingDisplay}
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={rttDialogOpen} onOpenChange={setRttDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={handleSubmitRtt} className="space-y-4">
            <DialogHeader>
              <DialogTitle>Ajuster le solde RTT</DialogTitle>
              <DialogDescription>
                Saisie de reprise pour l’année sélectionnée.
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 sm:grid-cols-[120px_1fr]">
              <div className="space-y-2">
                <Label htmlFor="employee-rtt-year">Année</Label>
                <Input
                  id="employee-rtt-year"
                  type="number"
                  min={2020}
                  max={2035}
                  value={rttYear}
                  onChange={(event) => setRttYear(Number(event.target.value) || currentYear)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="employee-rtt-solde">Solde RTT</Label>
                <Input
                  id="employee-rtt-solde"
                  type="number"
                  min={0}
                  step={0.5}
                  inputMode="decimal"
                  value={rttSolde}
                  onChange={(event) => setRttSolde(event.target.value)}
                  className="text-right tabular-nums"
                  autoFocus
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="employee-rtt-note">Note</Label>
              <Textarea
                id="employee-rtt-note"
                value={rttNote}
                onChange={(event) => setRttNote(event.target.value)}
                placeholder="Reprise historique"
                rows={3}
              />
            </div>

            {rttSoldeInvalid ? (
              <p className="text-sm text-destructive">
                Saisissez un nombre de jours positif ou nul.
              </p>
            ) : null}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setRttDialogOpen(false)}
              >
                Annuler
              </Button>
              <Button type="submit" disabled={rttSoldeInvalid || rttMutation.isPending}>
                {rttMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                ) : null}
                Enregistrer
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
