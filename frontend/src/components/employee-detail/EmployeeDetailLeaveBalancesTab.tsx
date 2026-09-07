import { useEffect, useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useLocation } from 'react-router-dom';
import { AlertCircle, CalendarDays, Loader2, Palmtree, Pencil } from 'lucide-react';
import {
  updateEmployeeLeaveSolde,
  type CompteurAjustable,
} from '@/api/leaveSettings';
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

/** Compteurs dont le solde AFFICHÉ est ajustable par la RH (converti en
 * écart d'ouverture côté serveur, même mécanique que la reprise). */
const COMPTEURS_AJUSTABLES: Record<string, CompteurAjustable> = {
  'Congés Payés (période précédente)': 'cp_n1',
  'Congés Payés (période en cours)': 'cp_n',
  RTT: 'rtt',
  JTC: 'jtc',
};

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

function formatSoldeDraft(value: number | null): string {
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
  const currentYear = new Date().getFullYear();

  // Dialogue générique « Ajuster le solde » (CP N-1 / CP N / RTT / JTC).
  const [adjustType, setAdjustType] = useState<string | null>(null);
  const [adjustYear, setAdjustYear] = useState(currentYear);
  const [adjustSolde, setAdjustSolde] = useState('');
  const [adjustNote, setAdjustNote] = useState('');

  const adjustBalance = adjustType
    ? visibleBalances.find((balance) => balance.type === adjustType)
    : undefined;
  const adjustCompteur = adjustType ? COMPTEURS_AJUSTABLES[adjustType] : undefined;

  useEffect(() => {
    if (!adjustType) return;
    const current = visibleBalances.find((balance) => balance.type === adjustType);
    setAdjustYear(currentYear);
    setAdjustSolde(
      formatSoldeDraft(
        typeof current?.remaining === 'number' ? current.remaining : null,
      ),
    );
    setAdjustNote('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adjustType, currentYear]);

  const adjustMutation = useMutation({
    mutationFn: () => {
      const parsed = Number.parseFloat(adjustSolde.replace(',', '.'));
      if (!adjustCompteur) throw new Error('Compteur non ajustable.');
      return updateEmployeeLeaveSolde(employeeId, adjustYear, {
        compteur: adjustCompteur,
        solde_cible: parsed,
        note: adjustNote.trim() || null,
      });
    },
    onSuccess: () => {
      setAdjustType(null);
      void queryClient.invalidateQueries({
        queryKey: queryKeys.employeeAbsenceBalances(companyId, employeeId),
      });
      void queryClient.invalidateQueries({
        queryKey: companyQueryKey(companyId, 'leave-balances-overview'),
      });
      toast({
        title: 'Solde enregistré',
        description: 'Les soldes du salarié ont été recalculés.',
      });
    },
    onError: () => {
      toast({
        title: 'Solde non enregistré',
        description:
          'Vérifiez l’éligibilité du salarié à ce compteur et réessayez.',
        variant: 'destructive',
      });
    },
  });

  const calendarHref = {
    pathname: location.pathname,
    search: '?tab=calendrier',
  };

  const parsedSolde = Number.parseFloat(adjustSolde.replace(',', '.'));
  const soldeInvalid = Number.isNaN(parsedSolde) || parsedSolde < 0;
  const adjustActionDisabled = balancesQuery.isLoading || !hireDate;

  const handleSubmitAdjust = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (soldeInvalid || adjustMutation.isPending) return;
    adjustMutation.mutate();
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
              Droits acquis, jours pris et soldes restants — le crayon d’une
              ligne permet d’ajuster son solde (CP N-1, CP N, RTT, JTC).
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" asChild className="shrink-0">
            <Link to={calendarHref}>
              <CalendarDays className="mr-2 h-4 w-4" aria-hidden />
              Calendrier
            </Link>
          </Button>
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
                    <TableHead className="w-10" aria-label="Actions" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleBalances.map((balance) => {
                    const unit = balanceUsesHours(balance.type) ? 'h' : 'j';
                    const isFamilial = balance.type === EVENEMENT_FAMILIAL_TYPE;
                    const remainingDisplay = formatBalanceRemaining(balance.remaining, unit);
                    const ajustable = balance.type in COMPTEURS_AJUSTABLES;

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
                        <TableCell className="text-right">
                          {ajustable ? (
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              disabled={adjustActionDisabled}
                              onClick={() => setAdjustType(balance.type)}
                              aria-label={`Ajuster le solde ${getRhLeaveBalanceShortLabel(balance.type)}`}
                            >
                              <Pencil className="h-4 w-4" aria-hidden />
                            </Button>
                          ) : null}
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

      <Dialog
        open={adjustType != null}
        onOpenChange={(open) => !open && setAdjustType(null)}
      >
        <DialogContent className="sm:max-w-md">
          <form onSubmit={handleSubmitAdjust} className="space-y-4">
            <DialogHeader>
              <DialogTitle>
                Ajuster le solde {adjustType ? getRhLeaveBalanceShortLabel(adjustType) : ''}
              </DialogTitle>
              <DialogDescription>
                Saisissez le solde restant souhaité : l’outil enregistre
                l’écart avec le calcul théorique (même mécanique que la
                reprise).
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 sm:grid-cols-[120px_1fr]">
              <div className="space-y-2">
                <Label htmlFor="employee-solde-year">Année</Label>
                <Input
                  id="employee-solde-year"
                  type="number"
                  min={2020}
                  max={2035}
                  value={adjustYear}
                  onChange={(event) => setAdjustYear(Number(event.target.value) || currentYear)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="employee-solde-cible">
                  Solde restant souhaité (j)
                </Label>
                <Input
                  id="employee-solde-cible"
                  type="number"
                  min={0}
                  step={0.5}
                  inputMode="decimal"
                  value={adjustSolde}
                  onChange={(event) => setAdjustSolde(event.target.value)}
                  className="text-right tabular-nums"
                  autoFocus
                />
                {typeof adjustBalance?.remaining === 'number' ? (
                  <p className="text-xs text-muted-foreground">
                    Solde affiché actuellement :{' '}
                    {adjustBalance.remaining.toFixed(1)} j
                  </p>
                ) : null}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="employee-solde-note">Note</Label>
              <Textarea
                id="employee-solde-note"
                value={adjustNote}
                onChange={(event) => setAdjustNote(event.target.value)}
                placeholder="Ex. recalage sur les compteurs du bulletin d’août"
                rows={3}
              />
            </div>

            {soldeInvalid ? (
              <p className="text-sm text-destructive">
                Saisissez un nombre de jours positif ou nul.
              </p>
            ) : null}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setAdjustType(null)}
              >
                Annuler
              </Button>
              <Button type="submit" disabled={soldeInvalid || adjustMutation.isPending}>
                {adjustMutation.isPending ? (
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
