import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Loader2,
  FileText,
  CheckCircle2,
  Ban,
  Pause,
  Play,
  Trash2,
  Download,
  AlertTriangle,
} from 'lucide-react';
import {
  LOAN_STATUS_COLORS,
  LOAN_STATUS_LABELS,
  activateEmployeeLoan,
  cancelEmployeeLoan,
  deleteEmployeeLoan,
  generateLoanContract,
  getLoanContractUrl,
  getLoanRepayments,
  getLoanSchedule,
  markLoanDeclared2062,
  markLoanDefaulted,
  recordEarlyRepayment,
  updateEmployeeLoan,
  type EmployeeLoan,
} from '@/api/employeeLoans';
import { useToast } from '@/hooks/use-toast';

interface EmployeeLoanDetailDrawerProps {
  loan: EmployeeLoan | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRefresh: () => void;
  mode?: 'rh' | 'employee';
}

const formatEuro = (value: number) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(value);

const INSTALLMENT_STATUS_LABELS: Record<string, string> = {
  pending: 'À venir',
  partial: 'Partielle',
  paid: 'Payée',
  skipped: 'Ignorée',
};

const installmentPaidTotal = (row: { capital_paid?: number; interest_paid?: number }) =>
  (row.capital_paid ?? 0) + (row.interest_paid ?? 0);

const installmentRemaining = (row: {
  total_due: number;
  capital_paid?: number;
  interest_paid?: number;
}) => Math.max(0, row.total_due - installmentPaidTotal(row));

export function EmployeeLoanDetailDrawer({
  loan,
  open,
  onOpenChange,
  onRefresh,
  mode = 'rh',
}: EmployeeLoanDetailDrawerProps) {
  const { toast } = useToast();
  const isRh = mode === 'rh';
  const [contractLoading, setContractLoading] = useState(false);
  const [earlyOpen, setEarlyOpen] = useState(false);
  const [earlyAmount, setEarlyAmount] = useState('');
  const [earlyDate, setEarlyDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [actionLoading, setActionLoading] = useState(false);

  const scheduleQuery = useQuery({
    queryKey: ['loan-schedule', loan?.id],
    queryFn: () => getLoanSchedule(loan!.id),
    enabled: Boolean(loan?.id && open),
  });

  const repaymentsQuery = useQuery({
    queryKey: ['loan-repayments', loan?.id],
    queryFn: () => getLoanRepayments(loan!.id),
    enabled: Boolean(loan?.id && open),
  });

  if (!loan) return null;

  const handleDownloadContract = async () => {
    setContractLoading(true);
    try {
      if (isRh && !loan.contract_file_path) {
        await generateLoanContract(loan.id);
      }
      const { url } = await getLoanContractUrl(loan.id);
      window.open(url, '_blank');
      if (isRh) onRefresh();
    } catch {
      toast({
        title: 'Erreur',
        description: 'Impossible de récupérer le contrat.',
        variant: 'destructive',
      });
    } finally {
      setContractLoading(false);
    }
  };

  const runAction = async (action: () => Promise<unknown>, success: string) => {
    setActionLoading(true);
    try {
      await action();
      toast({ title: success });
      onRefresh();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Action impossible.';
      toast({ title: 'Erreur', description: detail, variant: 'destructive' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleEarlyRepayment = async () => {
    const amount = Number(earlyAmount);
    if (!amount || amount <= 0) return;
    await runAction(
      () => recordEarlyRepayment(loan.id, { amount, repayment_date: earlyDate }),
      'Remboursement anticipé enregistré',
    );
    setEarlyOpen(false);
  };

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{isRh ? 'Prêt employeur' : 'Mon prêt employeur'}</SheetTitle>
            <SheetDescription>
              {loan.employee_name ?? ''} {formatEuro(loan.principal_amount)} — début{' '}
              {new Date(loan.start_date).toLocaleDateString('fr-FR')}
            </SheetDescription>
          </SheetHeader>

          <div className="mt-4 space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge className={LOAN_STATUS_COLORS[loan.status]}>
                {LOAN_STATUS_LABELS[loan.status]}
              </Badge>
              {loan.requires_2062_declaration && !loan.declared_2062 && (
                <Badge variant="outline">Formulaire 2062 à déclarer</Badge>
              )}
              {loan.declared_2062 && <Badge variant="secondary">2062 déclaré</Badge>}
            </div>

            {loan.requires_2062_declaration && !loan.declared_2062 && !isRh && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  Ce prêt doit être déclaré à l&apos;administration fiscale (formulaire n°2062)
                  avec votre déclaration de revenus.
                </AlertDescription>
              </Alert>
            )}

            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-muted-foreground">Capital restant dû</dt>
              <dd className="font-semibold">{formatEuro(loan.remaining_capital)}</dd>
              <dt className="text-muted-foreground">Mensualité</dt>
              <dd>{formatEuro(loan.monthly_payment)}</dd>
              <dt className="text-muted-foreground">Taux annuel</dt>
              <dd>{(loan.annual_interest_rate * 100).toFixed(2)} %</dd>
              <dt className="text-muted-foreground">Durée</dt>
              <dd>{loan.duration_months} mois</dd>
              <dt className="text-muted-foreground">Jour de prélèvement</dt>
              <dd>Le {loan.repayment_day} de chaque mois</dd>
              {loan.reason && (
                <>
                  <dt className="text-muted-foreground">Motif</dt>
                  <dd className="col-span-1">{loan.reason}</dd>
                </>
              )}
            </dl>

            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={handleDownloadContract}
                disabled={contractLoading}
              >
                {contractLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                {isRh && !loan.contract_file_path ? 'Générer contrat PDF' : 'Télécharger contrat'}
              </Button>

              {isRh && loan.requires_2062_declaration && !loan.declared_2062 && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={actionLoading}
                  onClick={() => runAction(() => markLoanDeclared2062(loan.id), '2062 enregistré')}
                >
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Marquer 2062 déclaré
                </Button>
              )}

              {isRh && loan.status === 'active' && (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={actionLoading}
                    onClick={() =>
                      runAction(
                        () => updateEmployeeLoan(loan.id, { status: 'suspended' }),
                        'Prêt suspendu',
                      )
                    }
                  >
                    <Pause className="mr-2 h-4 w-4" />
                    Suspendre
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={actionLoading}
                    onClick={() =>
                      runAction(() => markLoanDefaulted(loan.id), 'Prêt mis en défaut')
                    }
                  >
                    <AlertTriangle className="mr-2 h-4 w-4" />
                    Mettre en défaut
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={actionLoading}
                    onClick={() => {
                      setEarlyAmount(String(loan.remaining_capital));
                      setEarlyOpen(true);
                    }}
                  >
                    <FileText className="mr-2 h-4 w-4" />
                    Remboursement anticipé
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={actionLoading}
                    onClick={() =>
                      runAction(() => cancelEmployeeLoan(loan.id), 'Prêt annulé')
                    }
                  >
                    <Ban className="mr-2 h-4 w-4" />
                    Annuler
                  </Button>
                </>
              )}

              {isRh && loan.status === 'suspended' && (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={actionLoading}
                    onClick={() =>
                      runAction(
                        () => updateEmployeeLoan(loan.id, { status: 'active' }),
                        'Prêt réactivé',
                      )
                    }
                  >
                    <Play className="mr-2 h-4 w-4" />
                    Réactiver
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={actionLoading}
                    onClick={() =>
                      runAction(() => markLoanDefaulted(loan.id), 'Prêt mis en défaut')
                    }
                  >
                    <AlertTriangle className="mr-2 h-4 w-4" />
                    Mettre en défaut
                  </Button>
                </>
              )}

              {isRh && loan.status === 'draft' && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={actionLoading}
                  onClick={() =>
                    runAction(() => activateEmployeeLoan(loan.id), 'Prêt activé')
                  }
                >
                  <Play className="mr-2 h-4 w-4" />
                  Activer le prêt
                </Button>
              )}

              {isRh && (loan.status === 'draft' || loan.status === 'cancelled') && (
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={actionLoading}
                  onClick={() =>
                    runAction(async () => {
                      await deleteEmployeeLoan(loan.id);
                    }, 'Prêt supprimé')
                  }
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Supprimer
                </Button>
              )}
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold">Échéancier</h3>
              {scheduleQuery.isLoading ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <div className="max-h-48 overflow-auto rounded border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>N°</TableHead>
                        <TableHead>Période</TableHead>
                        <TableHead>Capital</TableHead>
                        <TableHead>Intérêts</TableHead>
                        <TableHead>Échéance</TableHead>
                        <TableHead>Prélevé</TableHead>
                        <TableHead>Reliquat</TableHead>
                        <TableHead>Statut</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(scheduleQuery.data ?? []).map((row) => (
                        <TableRow key={row.installment_number}>
                          <TableCell>{row.installment_number}</TableCell>
                          <TableCell>
                            {String(row.month).padStart(2, '0')}/{row.year}
                          </TableCell>
                          <TableCell>{formatEuro(row.capital_part)}</TableCell>
                          <TableCell>{formatEuro(row.interest_part)}</TableCell>
                          <TableCell>{formatEuro(row.total_due)}</TableCell>
                          <TableCell>
                            {installmentPaidTotal(row) > 0
                              ? formatEuro(installmentPaidTotal(row))
                              : '—'}
                          </TableCell>
                          <TableCell>
                            {row.status === 'partial' ||
                            (row.status === 'pending' && installmentPaidTotal(row) > 0)
                              ? formatEuro(installmentRemaining(row))
                              : row.status === 'pending'
                                ? '—'
                                : '—'}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                row.status === 'partial'
                                  ? 'outline'
                                  : row.status === 'paid'
                                    ? 'default'
                                    : 'secondary'
                              }
                              className={
                                row.status === 'partial'
                                  ? 'border-amber-500 text-amber-700'
                                  : undefined
                              }
                            >
                              {INSTALLMENT_STATUS_LABELS[row.status] ?? row.status}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>

            <div>
              <h3 className="mb-2 text-sm font-semibold">Remboursements sur bulletin</h3>
              {repaymentsQuery.isLoading ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (repaymentsQuery.data ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucun remboursement enregistré.</p>
              ) : (
                <div className="max-h-40 overflow-auto rounded border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Période bulletin</TableHead>
                        <TableHead>Éch. n°</TableHead>
                        <TableHead>Capital</TableHead>
                        <TableHead>Intérêts</TableHead>
                        <TableHead>Reste dû prêt</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(repaymentsQuery.data ?? []).map((row) => {
                        const instNum = scheduleQuery.data?.find(
                          (i) => i.id === row.installment_id,
                        )?.installment_number;
                        return (
                          <TableRow key={row.id}>
                            <TableCell>
                              {String(row.month).padStart(2, '0')}/{row.year}
                            </TableCell>
                            <TableCell>{instNum ?? '—'}</TableCell>
                            <TableCell>{formatEuro(row.capital_amount)}</TableCell>
                            <TableCell>{formatEuro(row.interest_amount)}</TableCell>
                            <TableCell>{formatEuro(row.remaining_after)}</TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>
          </div>
        </SheetContent>
      </Sheet>

      <Dialog open={earlyOpen} onOpenChange={setEarlyOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remboursement anticipé</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Montant (€)</Label>
              <Input
                type="number"
                min={0}
                max={loan.remaining_capital}
                value={earlyAmount}
                onChange={(e) => setEarlyAmount(e.target.value)}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Maximum : {formatEuro(loan.remaining_capital)}
              </p>
            </div>
            <div>
              <Label>Date</Label>
              <Input
                type="date"
                value={earlyDate}
                onChange={(e) => setEarlyDate(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEarlyOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleEarlyRepayment} disabled={actionLoading}>
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
