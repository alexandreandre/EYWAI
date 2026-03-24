// frontend/src/components/saisies-avances/SalaryAdvanceDetail.tsx

import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";
import { FileText, Download, Trash2, Eye } from "lucide-react";
import { getAdvancePayments, getPaymentProofUrl, deleteAdvancePayment } from '@/api/saisiesAvances';
import type { SalaryAdvance, SalaryAdvancePayment } from '@/api/saisiesAvances';
import { useAuth } from '@/contexts/AuthContext';
import { AdvancePaymentModal } from './AdvancePaymentModal';

const STATUS_LABELS: Record<string, string> = {
  'pending': 'En attente',
  'approved': 'À verser',
  'rejected': 'Rejetée',
  'paid': 'Versée',
};

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
  const [viewingProof, setViewingProof] = useState<string | null>(null);

  const isRh = user?.role === 'rh' || user?.role === 'admin';

  useEffect(() => {
    fetchPayments();
  }, [advance.id]);

  const fetchPayments = async () => {
    setIsLoadingPayments(true);
    try {
      const data = await getAdvancePayments(advance.id);
      setPayments(data);
    } catch (error) {
      console.error('Erreur chargement paiements:', error);
    } finally {
      setIsLoadingPayments(false);
    }
  };

  const handleViewProof = async (paymentId: string) => {
    try {
      const { url } = await getPaymentProofUrl(paymentId);
      window.open(url, '_blank');
    } catch (error: any) {
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
      fetchPayments();
      onUpdate?.();
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Impossible de supprimer le paiement.",
        variant: "destructive",
      });
    }
  };

  const approvedAmount = Number(advance.approved_amount || 0);
  const totalPaid = payments.reduce((sum, p) => sum + Number(p.payment_amount || 0), 0);
  const remainingToPay = approvedAmount - totalPaid; // Montant restant à verser à l'employé

  return (
    <>
      <Dialog open={true} onOpenChange={onClose}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Détails de l'avance</DialogTitle>
          </DialogHeader>
          <div className="space-y-6">
            {/* Informations principales */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Statut</p>
                <Badge className="mt-1">{STATUS_LABELS[advance.status]}</Badge>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Montant demandé</p>
                <p className="text-lg font-semibold">{Number(advance.requested_amount || 0).toFixed(2)}€</p>
              </div>
            </div>

            {approvedAmount > 0 && (
              <div className="grid grid-cols-3 gap-4 p-3 bg-blue-50 rounded-md">
                <div>
                  <p className="text-sm font-medium text-blue-900">Montant approuvé</p>
                  <p className="text-lg font-semibold text-blue-900">{approvedAmount.toFixed(2)}€</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-blue-900">Total versé</p>
                  <p className="text-lg font-semibold text-green-600">{totalPaid.toFixed(2)}€</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-blue-900">Reste à verser</p>
                  <p className="text-lg font-semibold text-orange-600">{remainingToPay.toFixed(2)}€</p>
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Date de demande</p>
                <p>{new Date(advance.requested_date).toLocaleDateString('fr-FR')}</p>
              </div>
              {advance.payment_date && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Date de versement</p>
                  <p>{new Date(advance.payment_date).toLocaleDateString('fr-FR')}</p>
                </div>
              )}
            </div>

            {advance.payment_method && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">Mode de paiement</p>
                <p>
                  {advance.payment_method === 'virement' ? 'Virement' :
                   advance.payment_method === 'cheque' ? 'Chèque' : 'Espèces'}
                </p>
              </div>
            )}

            {advance.request_comment && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">Motif</p>
                <p className="text-sm">{advance.request_comment}</p>
              </div>
            )}

            {advance.rejection_reason && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">Raison du rejet</p>
                <p className="text-sm text-red-600">{advance.rejection_reason}</p>
              </div>
            )}

            {/* Section Paiements */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Paiements</h3>
                {isRh && (advance.status === 'approved' || advance.status === 'paid') && remainingToPay > 0 && (
                  <Button
                    size="sm"
                    onClick={() => setShowPaymentModal(true)}
                  >
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
                            <div className="flex items-center gap-2 mb-2">
                              <span className="font-semibold">
                                {Number(payment.payment_amount || 0).toFixed(2)}€
                              </span>
                              <span className="text-sm text-muted-foreground">
                                le {new Date(payment.payment_date).toLocaleDateString('fr-FR')}
                              </span>
                              {payment.payment_method && (
                                <Badge variant="outline" className="text-xs">
                                  {payment.payment_method === 'virement' ? 'Virement' :
                                   payment.payment_method === 'cheque' ? 'Chèque' : 'Espèces'}
                                </Badge>
                              )}
                            </div>
                            {payment.proof_file_name && (
                              <div className="flex items-center gap-2 mt-2">
                                <FileText className="h-4 w-4 text-muted-foreground" />
                                <span className="text-sm text-muted-foreground">
                                  {payment.proof_file_name}
                                </span>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleViewProof(payment.id)}
                                  className="h-6 px-2"
                                >
                                  <Eye className="h-3 w-3 mr-1" />
                                  Voir
                                </Button>
                              </div>
                            )}
                            {payment.notes && (
                              <p className="text-sm text-muted-foreground mt-2">{payment.notes}</p>
                            )}
                          </div>
                          {isRh && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeletePayment(payment.id)}
                              className="text-red-600 hover:text-red-700"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>

            <div>
              <p className="text-sm font-medium text-muted-foreground">Créée le</p>
              <p>{new Date(advance.created_at).toLocaleString('fr-FR')}</p>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {showPaymentModal && (
        <AdvancePaymentModal
          advance={advance}
          onClose={() => setShowPaymentModal(false)}
          onSuccess={() => {
            setShowPaymentModal(false);
            fetchPayments();
            onUpdate?.();
          }}
        />
      )}
    </>
  );
}
