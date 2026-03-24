// frontend/src/pages/employee/SalaryAdvances.tsx

import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Plus, Loader2, Wallet } from "lucide-react";
import { getMySalaryAdvances, getMyAdvanceAvailable } from '@/api/saisiesAvances';
import type { SalaryAdvance, AdvanceAvailableAmount } from '@/api/saisiesAvances';
import { SalaryAdvanceRequestForm } from '@/components/saisies-avances/SalaryAdvanceRequestForm';
import { SalaryAdvanceDetail } from '@/components/saisies-avances/SalaryAdvanceDetail';
import { useAuth } from '@/contexts/AuthContext';

const STATUS_LABELS: Record<string, string> = {
  'pending': 'En attente',
  'approved': 'À verser',
  'rejected': 'Rejetée',
  'paid': 'Versée',
};

const STATUS_COLORS: Record<string, string> = {
  'pending': 'bg-yellow-500',
  'approved': 'bg-blue-500',
  'rejected': 'bg-red-500',
  'paid': 'bg-green-500',
};

export default function SalaryAdvances() {
  const { toast } = useToast();
  const { user } = useAuth();
  const [advances, setAdvances] = useState<SalaryAdvance[]>([]);
  const [availableAmount, setAvailableAmount] = useState<AdvanceAvailableAmount | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [selectedAdvance, setSelectedAdvance] = useState<SalaryAdvance | null>(null);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [advancesData, availableData] = await Promise.all([
        getMySalaryAdvances(),
        getMyAdvanceAvailable(),
      ]);
      setAdvances(advancesData);
      setAvailableAmount(availableData);
    } catch (error) {
      toast({
        title: "Erreur",
        description: "Impossible de charger les données.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Avances sur salaire</h1>
        <p className="text-muted-foreground">
          Demander une avance sur votre salaire
        </p>
      </div>

      {availableAmount && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wallet className="h-5 w-5" />
              Montant disponible
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-primary">
              {Number(availableAmount.available_amount || 0).toFixed(2)}€
            </div>
            <p className="text-sm text-muted-foreground mt-2">
              Basé sur {Number(availableAmount.days_worked || 0)} jours travaillés depuis la dernière paie
            </p>
            {Number(availableAmount.outstanding_advances || 0) > 0 && (
              <p className="text-sm text-muted-foreground">
                Avances en cours : {Number(availableAmount.outstanding_advances || 0).toFixed(2)}€
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <div className="flex justify-end">
        <Button onClick={() => setShowForm(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Demander une avance
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Mes demandes d'avance</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Montant demandé</TableHead>
                <TableHead>Date demande</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {advances.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    Aucune demande d'avance
                  </TableCell>
                </TableRow>
              ) : (
                advances.map((advance) => (
                  <TableRow key={advance.id}>
                    <TableCell>{Number(advance.requested_amount || 0).toFixed(2)}€</TableCell>
                    <TableCell>
                      {new Date(advance.requested_date).toLocaleDateString('fr-FR')}
                    </TableCell>
                    <TableCell>
                      <Badge className={STATUS_COLORS[advance.status]}>
                        {STATUS_LABELS[advance.status]}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedAdvance(advance)}
                      >
                        Voir détails
                      </Button>
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
          employeeId={user?.id}
          hideEmployeeSelector={true}
          onClose={() => setShowForm(false)}
          onSuccess={() => {
            setShowForm(false);
            fetchData();
          }}
        />
      )}

      {selectedAdvance && (
        <SalaryAdvanceDetail
          advance={selectedAdvance}
          onClose={() => setSelectedAdvance(null)}
          onUpdate={fetchData}
        />
      )}
    </div>
  );
}
