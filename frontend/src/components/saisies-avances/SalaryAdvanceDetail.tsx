// frontend/src/components/saisies-avances/SalaryAdvanceDetail.tsx

import { log } from '@/lib/logger';
import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/components/ui/use-toast";
import { AlertCircle, Eye, FileText, Trash2 } from "lucide-react";
import { getAdvancePayments, getPaymentProofUrl, deleteAdvancePayment } from '@/api/saisiesAvances';
import type { SalaryAdvance, SalaryAdvancePayment } from '@/api/saisiesAvances';
import { useAuth } from '@/contexts/AuthContext';
import { AdvancePaymentModal } from './AdvancePaymentModal';
import { EmployeeSalaryAdvanceStatusBadge } from '@/components/employee-salary-advances/EmployeeSalaryAdvanceStatusBadge';
import { formatCurrency } from '@/lib/employeeDashboardUtils';
import {
  formatAdvanceDate,
  formatAdvanceDateTime,
  formatAccountingAccount,
  getAdvanceTypeLabel,
  showRemainingRepayment,
} from '@/lib/employeeSalaryAdvancesUtils';

interface SalaryAdvanceDetailProps {
  advance: SalaryAdvance;
  onClose: () => void;
  onUpdate?: () => void;
}

export function SalaryAdvanceDetail({ advance, onClose, onUpdate }: SalaryAdvanceDetailProps) {
  const { toast } = useToast();
  const { user } = useAuth();
  const [payments, setPayments] = useState<SalaryAdvancePayment[]>([]);
  const [isLoadingPayments, setIsLoadingPayments] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);

  const isRh = user?.role === 'rh' || user?.role === 'admin';
  const isEmployee = user?.role === 'collaborateur';

  useEffect(() => {
    if (!isRh) return;
    void fetchPayments();
  }, [advance.id, isRh]);

  const fetchPayments = async () => {
    setIsLoadingPayments(true);
    try {
      const data = await getAdvancePayments(advance.id);
      setPayments(data);
    } catch (error) {
      log.error('Erreur chargement paiements:', error);
    } finally {
      setIsLoadingPayments(false);
    }
  };

  const handleViewProof = async (paymentId: string) => {
    try {
      const { url } = await getPaymentProofUrl(paymentId);
      window.open(url, '_blank');
    } catch {
      toast({
        title: "Erreur",
        description: "Impossible de télécharger la preuve.",
        variant: "destructive",
      });
    }
  };

  const handleDeletePayment = async (paymentId: string) => {
    if (!confirm('Êtes-vous sûr de vouloir supprimer ce paiement ?')) {
      return;
    }
    try {
      await deleteAdvancePayment(paymentId);
      toast({
        title: "Succès",
        description: "Paiement supprimé.",
      });
      void fetchPayments();
      onUpdate?.();
    } catch (error: unknown) {
      const detail =
        error && typeof error === 'object' && 'response' in error
          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Erreur",
        description: detail || "Impossible de supprimer le paiement.",
        variant: "destructive",
      });
    }
  };

  const approvedAmount = Number(advance.approved_amount || 0);
  const requestedAmount = Number(advance.requested_amount || 0);
  const totalPaid = payments.reduce((sum, p) => sum + Number(p.payment_amount || 0), 0);
  const remainingToPay = approvedAmount - totalPaid;

  const dialogTitle = isEmployee
    ? `Ma demande du ${formatAdvanceDate(advance.created_at)}`
    : getAdvanceTypeLabel(advance.advance_type, advance.prime_label);

  const acompteVerse = totalPaid > 0 ? totalPaid : approvedAmount;
  const primeFinal = Number(advance.prime_final_amount || 0);
  const primeSolde =
    advance.advance_type === 'acompte_prime' && primeFinal > 0
      ? Math.max(0, primeFinal - acompteVerse)
      : null;

  const paymentMethodLabel =
    advance.payment_method === 'virement'
      ? 'Virement'
      : advance.payment_method === 'cheque'
        ? 'Chèque'
        : advance.payment_method === 'especes'
          ? 'Espèces'
          : null;

  return (
    <>
      <Dialog open={true} onOpenChange={onClose}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{dialogTitle}</DialogTitle>
          </DialogHeader>
          <div className="space-y-6">
            {advance.status === 'rejected' && advance.rejection_reason && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Demande rejetée</AlertTitle>
                <AlertDescription>{advance.rejection_reason}</AlertDescription>
              </Alert>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Nature</p>
                <p className="font-medium">
                  {getAdvanceTypeLabel(advance.advance_type, advance.prime_label)}
                </p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Compte comptable</p>
                {advance.accounting_account ? (
                  <Badge variant="outline" className="mt-1 font-mono text-sm">
                    {formatAccountingAccount(advance.accounting_account)}
                  </Badge>
                ) : (
                  <p className="text-sm text-muted-foreground">Non renseigné</p>
                )}
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Statut</p>
                <div className="mt-1">
                  <EmployeeSalaryAdvanceStatusBadge status={advance.status} />
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Montant demandé</p>
                <p className="text-lg font-semibold">{formatCurrency(requestedAmount)}</p>
              </div>
            </div>

            {advance.advance_type === 'acompte_prime' && (
              <div className="rounded-md border bg-muted/40 p-3 text-sm space-y-1">
                {advance.prime_label && (
                  <p>
                    <span className="text-muted-foreground">Prime :</span>{' '}
                    <strong>{advance.prime_label}</strong>
                  </p>
                )}
                {advance.prime_expected_amount != null && (
                  <p>
                    <span className="text-muted-foreground">Montant estimé :</span>{' '}
                    {formatCurrency(advance.prime_expected_amount)}
                  </p>
                )}
                {primeFinal > 0 && (
                  <>
                    <p>
                      <span className="text-muted-foreground">Montant définitif :</span>{' '}
                      {formatCurrency(primeFinal)}
                    </p>
                    <p>
                      <span className="text-muted-foreground">Acompte versé :</span>{' '}
                      - {formatCurrency(acompteVerse)}
                    </p>
                    {primeSolde != null && (
                      <p className="font-semibold">
                        Solde à payer : {formatCurrency(primeSolde)}
                      </p>
                    )}
                    {advance.prime_reconciled_at && (
                      <p className="text-muted-foreground">
                        Réconcilié le {formatAdvanceDateTime(advance.prime_reconciled_at)}
                      </p>
                    )}
                  </>
                )}
              </div>
            )}

            {approvedAmount > 0 && (
              <div className="grid grid-cols-1 gap-4 rounded-md border bg-muted/40 p-3 sm:grid-cols-3">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Montant approuvé</p>
                  <p className="text-lg font-semibold">{formatCurrency(approvedAmount)}</p>
                </div>
                {isRh ? (
                  <>
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">Total versé</p>
                      <p className="text-lg font-semibold text-green-600 dark:text-green-400">
                        {formatCurrency(totalPaid)}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">Reste à verser</p>
                      <p className="text-lg font-semibold text-orange-600 dark:text-orange-400">
                        {formatCurrency(remainingToPay)}
                      </p>
                    </div>
                  </>
                ) : (
                  showRemainingRepayment(advance) && (
                    <div className="sm:col-span-2">
                      <p className="text-sm font-medium text-muted-foreground">
                        Reste à rembourser sur vos prochains bulletins
                      </p>
                      <p className="text-lg font-semibold">
                        {formatCurrency(advance.remaining_amount)}
                      </p>
                    </div>
                  )
                )}
              </div>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Versement souhaité
                </p>
                <p>{formatAdvanceDate(advance.requested_date)}</p>
              </div>
              {advance.payment_date && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Date de versement effective
                  </p>
                  <p>{formatAdvanceDate(advance.payment_date)}</p>
                </div>
              )}
            </div>

            {paymentMethodLabel && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">Mode de paiement</p>
                <p>{paymentMethodLabel}</p>
              </div>
            )}

            {advance.request_comment && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">Motif</p>
                <p className="text-sm">{advance.request_comment}</p>
              </div>
            )}

            {isRh && advance.rejection_reason && advance.status !== 'rejected' && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">Raison du rejet</p>
                <p className="text-sm text-destructive">{advance.rejection_reason}</p>
              </div>
            )}

            {isEmployee && advance.status === 'paid' && !showRemainingRepayment(advance) && (
              <p className="text-sm text-muted-foreground">
                Cette avance a été versée et est entièrement remboursée.
              </p>
            )}

            {isRh && (
              <div>
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-lg font-semibold">Paiements</h3>
                  {(advance.status === 'approved' || advance.status === 'paid') &&
                    remainingToPay > 0 && (
                      <Button size="sm" onClick={() => setShowPaymentModal(true)}>
                        Enregistrer un paiement
                      </Button>
                    )}
                </div>

                {isLoadingPayments ? (
                  <p className="text-sm text-muted-foreground">Chargement...</p>
                ) : payments.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Aucun paiement enregistré</p>
                ) : (
                  <div className="space-y-2">
                    {payments.map((payment) => (
                      <Card key={payment.id}>
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="mb-2 flex items-center gap-2">
                                <span className="font-semibold">
                                  {formatCurrency(payment.payment_amount)}
                                </span>
                                <span className="text-sm text-muted-foreground">
                                  le {formatAdvanceDate(payment.payment_date)}
                                </span>
                                {payment.payment_method && (
                                  <Badge variant="outline" className="text-xs">
                                    {payment.payment_method === 'virement'
                                      ? 'Virement'
                                      : payment.payment_method === 'cheque'
                                        ? 'Chèque'
                                        : 'Espèces'}
                                  </Badge>
                                )}
                              </div>
                              {payment.proof_file_name && (
                                <div className="mt-2 flex items-center gap-2">
                                  <FileText className="h-4 w-4 text-muted-foreground" />
                                  <span className="text-sm text-muted-foreground">
                                    {payment.proof_file_name}
                                  </span>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => void handleViewProof(payment.id)}
                                    className="h-6 px-2"
                                  >
                                    <Eye className="mr-1 h-3 w-3" />
                                    Voir
                                  </Button>
                                </div>
                              )}
                              {payment.notes && (
                                <p className="mt-2 text-sm text-muted-foreground">
                                  {payment.notes}
                                </p>
                              )}
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => void handleDeletePayment(payment.id)}
                              className="text-red-600 hover:text-red-700"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              Demande déposée le {formatAdvanceDateTime(advance.created_at)}
            </p>
          </div>
        </DialogContent>
      </Dialog>

      {showPaymentModal && (
        <AdvancePaymentModal
          advance={advance}
          onClose={() => setShowPaymentModal(false)}
          onSuccess={() => {
            setShowPaymentModal(false);
            void fetchPayments();
            onUpdate?.();
          }}
        />
      )}
    </>
  );
}
