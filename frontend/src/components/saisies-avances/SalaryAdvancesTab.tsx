// frontend/src/components/saisies-avances/SalaryAdvancesTab.tsx

import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Plus, Loader2, Check, X, Eye } from "lucide-react";
import { getSalaryAdvances, approveSalaryAdvance, rejectSalaryAdvance } from '@/api/saisiesAvances';
import type { SalaryAdvance, SalaryAdvanceStatus } from '@/api/saisiesAvances';
import { SalaryAdvanceRequestForm } from './SalaryAdvanceRequestForm';
import { SalaryAdvanceApprovalModal } from './SalaryAdvanceApprovalModal';
import { SalaryAdvanceDetail } from './SalaryAdvanceDetail';

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

export function SalaryAdvancesTab() {
  const { toast } = useToast();
  const [advances, setAdvances] = useState<SalaryAdvance[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [selectedAdvance, setSelectedAdvance] = useState<SalaryAdvance | null>(null);
  const [approvalAdvance, setApprovalAdvance] = useState<SalaryAdvance | null>(null);
  const [filterStatus, setFilterStatus] = useState<SalaryAdvanceStatus | 'all'>('all');

  const fetchAdvances = async () => {
    setIsLoading(true);
    try {
      const data = await getSalaryAdvances();
      setAdvances(data);
    } catch (error) {
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
    setApprovalAdvance(advances.find(a => a.id === id) || null);
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <Button
            variant={filterStatus === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('all')}
          >
            Toutes
          </Button>
          <Button
            variant={filterStatus === 'pending' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('pending')}
          >
            En attente
          </Button>
          <Button
            variant={filterStatus === 'approved' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('approved')}
          >
            À verser
          </Button>
          <Button
            variant={filterStatus === 'paid' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('paid')}
          >
            Versées
          </Button>
        </div>
        <Button onClick={() => setShowForm(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nouvelle avance
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Avances sur salaire</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Employé</TableHead>
                <TableHead>Montant demandé</TableHead>
                <TableHead>Montant approuvé</TableHead>
                <TableHead>Date demande</TableHead>
                <TableHead>Reste à rembourser</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredAdvances.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground">
                    Aucune avance trouvée
                  </TableCell>
                </TableRow>
              ) : (
                filteredAdvances.map((advance) => (
                  <TableRow key={advance.id}>
                    <TableCell>{advance.employee_name || advance.employee_id || 'Employé inconnu'}</TableCell>
                    <TableCell>{Number(advance.requested_amount || 0).toFixed(2)}€</TableCell>
                    <TableCell>
                      {advance.approved_amount ? `${Number(advance.approved_amount).toFixed(2)}€` : '-'}
                    </TableCell>
                    <TableCell>
                      {new Date(advance.requested_date).toLocaleDateString('fr-FR')}
                    </TableCell>
                    <TableCell>
                      {Number(advance.remaining_amount || 0) > 0 ? `${Number(advance.remaining_amount || 0).toFixed(2)}€` : '-'}
                    </TableCell>
                    <TableCell>
                      <Badge className={STATUS_COLORS[advance.status]}>
                        {STATUS_LABELS[advance.status]}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedAdvance(advance)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        {advance.status === 'pending' && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleApprove(advance.id)}
                            >
                              <Check className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleReject(advance.id)}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {showForm && (
        <SalaryAdvanceRequestForm
          onClose={() => setShowForm(false)}
          onSuccess={() => {
            setShowForm(false);
            fetchAdvances();
          }}
        />
      )}

      {approvalAdvance && (
        <SalaryAdvanceApprovalModal
          advance={approvalAdvance}
          onClose={() => setApprovalAdvance(null)}
          onSuccess={() => {
            setApprovalAdvance(null);
            fetchAdvances();
          }}
        />
      )}

      {selectedAdvance && (
        <SalaryAdvanceDetail
          advance={selectedAdvance}
          onClose={() => setSelectedAdvance(null)}
        />
      )}
    </div>
  );
}
