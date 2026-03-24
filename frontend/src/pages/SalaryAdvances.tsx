// frontend/src/pages/SalaryAdvances.tsx

import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Plus, Loader2, Check, X, Eye, Wallet, Clock, CheckCircle, XCircle, CreditCard } from "lucide-react";
import { getSalaryAdvances, approveSalaryAdvance, rejectSalaryAdvance } from '@/api/saisiesAvances';
import type { SalaryAdvance, SalaryAdvanceStatus } from '@/api/saisiesAvances';
import { SalaryAdvanceRequestForm } from '@/components/saisies-avances/SalaryAdvanceRequestForm';
import { SalaryAdvanceDetail } from '@/components/saisies-avances/SalaryAdvanceDetail';
import { AdvancePaymentModal } from '@/components/saisies-avances/AdvancePaymentModal';

const STATUS_LABELS: Record<SalaryAdvanceStatus, string> = {
  'pending': 'En attente',
  'approved': 'À verser',
  'rejected': 'Rejetée',
  'paid': 'Versée',
};

const STATUS_COLORS: Record<SalaryAdvanceStatus, string> = {
  'pending': 'bg-yellow-500',
  'approved': 'bg-blue-500',
  'rejected': 'bg-red-500',
  'paid': 'bg-green-500',
};

export default function SalaryAdvances() {
  const { toast } = useToast();
  const [advances, setAdvances] = useState<SalaryAdvance[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [selectedAdvance, setSelectedAdvance] = useState<SalaryAdvance | null>(null);
  const [paymentAdvance, setPaymentAdvance] = useState<SalaryAdvance | null>(null);
  const [filterStatus, setFilterStatus] = useState<SalaryAdvanceStatus | 'all'>('all');

  const fetchAdvances = async () => {
    setIsLoading(true);
    try {
      // Ajouter un timestamp pour éviter le cache
      const data = await getSalaryAdvances();
      console.log('[DEBUG] Avances récupérées:', data);
      // Vérifier que remaining_to_pay est bien présent
      data.forEach((advance: any) => {
        console.log(`[DEBUG] Avance ${advance.id}: remaining_to_pay=${advance.remaining_to_pay}, approved=${advance.approved_amount}, status=${advance.status}`);
      });
      setAdvances(data);
    } catch (error) {
      console.error('[DEBUG] Erreur lors du chargement des avances:', error);
      toast({
        title: "Erreur",
        description: "Impossible de charger les avances.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAdvances();
  }, []);

  const handleApprove = async (id: string) => {
    try {
      await approveSalaryAdvance(id);
      toast({
        title: "Succès",
        description: "Avance approuvée.",
      });
      fetchAdvances();
    } catch (error) {
      toast({
        title: "Erreur",
        description: "Impossible d'approuver l'avance.",
        variant: "destructive",
      });
    }
  };

  const handleReject = async (id: string) => {
    const reason = prompt('Raison du rejet :');
    if (!reason) return;

    try {
      await rejectSalaryAdvance(id, { rejection_reason: reason });
      toast({
        title: "Succès",
        description: "Avance rejetée.",
      });
      fetchAdvances();
    } catch (error) {
      toast({
        title: "Erreur",
        description: "Impossible de rejeter l'avance.",
        variant: "destructive",
      });
    }
  };

  const filteredAdvances = filterStatus === 'all'
    ? advances
    : advances.filter(a => a.status === filterStatus);

  const stats = {
    total: advances.length,
    pending: advances.filter(a => a.status === 'pending').length,
    approved: advances.filter(a => a.status === 'approved').length,
    paid: advances.filter(a => a.status === 'paid').length,
    rejected: advances.filter(a => a.status === 'rejected').length,
  };

  const totalPendingAmount = advances
    .filter(a => a.status === 'pending')
    .reduce((sum, a) => sum + Number(a.requested_amount || 0), 0);

  const totalOutstandingAmount = advances
    .filter(a => a.status === 'paid')
    .reduce((sum, a) => sum + Number(a.remaining_amount || 0), 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Wallet className="h-8 w-8" />
          Avances sur salaire
        </h1>
        <p className="text-muted-foreground mt-2">
          Gestion des demandes d'avance sur salaire et suivi des remboursements
        </p>
      </div>

      {/* Statistiques */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total</CardTitle>
            <Wallet className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">demandes</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">En attente</CardTitle>
            <Clock className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{stats.pending}</div>
            <p className="text-xs text-muted-foreground">
              {totalPendingAmount > 0 && `${totalPendingAmount.toFixed(2)}€`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">À verser</CardTitle>
            <CheckCircle className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{stats.approved}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Versées</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{stats.paid}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Rejetées</CardTitle>
            <XCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{stats.rejected}</div>
            <p className="text-xs text-muted-foreground">refusées</p>
          </CardContent>
        </Card>
      </div>

      {/* Filtres et actions */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2 flex-wrap">
          <Button
            variant={filterStatus === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('all')}
          >
            Toutes ({stats.total})
          </Button>
          <Button
            variant={filterStatus === 'pending' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('pending')}
          >
            En attente ({stats.pending})
          </Button>
          <Button
            variant={filterStatus === 'approved' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('approved')}
          >
            À verser ({stats.approved})
          </Button>
          <Button
            variant={filterStatus === 'paid' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('paid')}
          >
            Versées ({stats.paid})
          </Button>
        </div>
        <Button onClick={() => setShowForm(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nouvelle avance
        </Button>
      </div>

      {/* Tableau */}
      <Card>
        <CardHeader>
          <CardTitle>Liste des avances</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                      <TableHead>Employé</TableHead>
                      <TableHead>Montant demandé</TableHead>
                      <TableHead>Montant restant à verser</TableHead>
                      <TableHead>Date demande</TableHead>
                      <TableHead>Statut</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAdvances.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      Aucune avance trouvée
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredAdvances.map((advance) => (
                    <TableRow key={advance.id}>
                      <TableCell className="font-medium">
                        {advance.employee_name || advance.employee_id || 'Employé inconnu'}
                      </TableCell>
                      <TableCell>
                        <span className="font-semibold">{Number(advance.requested_amount || 0).toFixed(2)}€</span>
                      </TableCell>
                      <TableCell>
                        {(() => {
                          // Si le statut est "pending", afficher "-"
                          if (advance.status === 'pending') {
                            return <span className="text-muted-foreground">-</span>;
                          }
                          
                          // Utiliser remaining_to_pay si disponible (basé sur les paiements réels)
                          const remainingToPay = (advance as any).remaining_to_pay;
                          if (remainingToPay !== undefined && remainingToPay !== null) {
                            const remaining = Number(remainingToPay);
                            if (remaining > 0) {
                              return <span className="text-orange-600 font-semibold">{remaining.toFixed(2)}€</span>;
                            } else {
                              return <span className="text-green-600 font-semibold">0.00€</span>;
                            }
                          }
                          
                          // Fallback : si remaining_to_pay n'est pas disponible, utiliser approved_amount
                          if (advance.approved_amount) {
                            return <span className="text-green-600 font-semibold">{Number(advance.approved_amount).toFixed(2)}€</span>;
                          }
                          
                          return <span className="text-muted-foreground">-</span>;
                        })()}
                      </TableCell>
                      <TableCell>
                        {new Date(advance.requested_date).toLocaleDateString('fr-FR')}
                      </TableCell>
                      <TableCell>
                        <Badge className={STATUS_COLORS[advance.status]}>
                          {STATUS_LABELS[advance.status]}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex gap-2 justify-end">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedAdvance(advance)}
                            title="Voir détails"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          {advance.status === 'pending' && (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleApprove(advance.id)}
                                title="Approuver"
                                className="text-green-600 hover:text-green-700"
                              >
                                <Check className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleReject(advance.id)}
                                title="Rejeter"
                                className="text-red-600 hover:text-red-700"
                              >
                                <X className="h-4 w-4" />
                              </Button>
                            </>
                          )}
                          {(advance.status === 'approved' || advance.status === 'paid') && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setPaymentAdvance(advance)}
                              title="Enregistrer un paiement"
                              className="text-blue-600 hover:text-blue-700"
                            >
                              <CreditCard className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Modals */}
      {showForm && (
        <SalaryAdvanceRequestForm
          onClose={() => setShowForm(false)}
          onSuccess={() => {
            setShowForm(false);
            fetchAdvances();
          }}
        />
      )}


      {selectedAdvance && (
        <SalaryAdvanceDetail
          advance={selectedAdvance}
          onClose={() => setSelectedAdvance(null)}
          onUpdate={fetchAdvances}
        />
      )}

      {paymentAdvance && (
        <AdvancePaymentModal
          advance={paymentAdvance}
          onClose={() => setPaymentAdvance(null)}
          onSuccess={() => {
            setPaymentAdvance(null);
            fetchAdvances();
          }}
        />
      )}
    </div>
  );
}
