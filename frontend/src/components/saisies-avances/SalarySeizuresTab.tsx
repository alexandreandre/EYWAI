// frontend/src/components/saisies-avances/SalarySeizuresTab.tsx

import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Plus, Loader2, Pause, Play, X, Eye } from "lucide-react";
import { getSalarySeizures, deleteSalarySeizure, updateSalarySeizure } from '@/api/saisiesAvances';
import type { SalarySeizure, SalarySeizureStatus } from '@/api/saisiesAvances';
import { SalarySeizureForm } from './SalarySeizureForm';
import { SalarySeizureDetail } from './SalarySeizureDetail';

const SEIZURE_TYPE_LABELS: Record<string, string> = {
  'saisie_arret': 'Saisie-arrêt',
  'pension_alimentaire': 'Pension alimentaire',
  'atd': 'Avis à tiers détenteur',
  'satd': 'Saisie administrative',
};

const STATUS_LABELS: Record<SalarySeizureStatus, string> = {
  'active': 'Active',
  'suspended': 'Suspendue',
  'closed': 'Clôturée',
};

const STATUS_COLORS: Record<SalarySeizureStatus, string> = {
  'active': 'bg-green-500',
  'suspended': 'bg-yellow-500',
  'closed': 'bg-gray-500',
};

export function SalarySeizuresTab() {
  const { toast } = useToast();
  const [seizures, setSeizures] = useState<SalarySeizure[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [selectedSeizure, setSelectedSeizure] = useState<SalarySeizure | null>(null);
  const [filterStatus, setFilterStatus] = useState<SalarySeizureStatus | 'all'>('all');

  const fetchSeizures = async () => {
    setIsLoading(true);
    try {
      const data = await getSalarySeizures();
      setSeizures(data);
    } catch (error) {
      toast({
        title: "Erreur",
        description: "Impossible de charger les saisies.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSeizures();
  }, []);

  const handleStatusChange = async (id: string, newStatus: SalarySeizureStatus) => {
    try {
      await updateSalarySeizure(id, { status: newStatus });
      toast({
        title: "Succès",
        description: "Statut de la saisie mis à jour.",
      });
      fetchSeizures();
    } catch (error) {
      toast({
        title: "Erreur",
        description: "Impossible de mettre à jour le statut.",
        variant: "destructive",
      });
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Êtes-vous sûr de vouloir supprimer cette saisie ?')) {
      return;
    }
    try {
      await deleteSalarySeizure(id);
      toast({
        title: "Succès",
        description: "Saisie supprimée.",
      });
      fetchSeizures();
    } catch (error) {
      toast({
        title: "Erreur",
        description: "Impossible de supprimer la saisie.",
        variant: "destructive",
      });
    }
  };

  const filteredSeizures = filterStatus === 'all'
    ? seizures
    : seizures.filter(s => s.status === filterStatus);

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
            variant={filterStatus === 'active' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('active')}
          >
            Actives
          </Button>
          <Button
            variant={filterStatus === 'suspended' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('suspended')}
          >
            Suspendues
          </Button>
          <Button
            variant={filterStatus === 'closed' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('closed')}
          >
            Clôturées
          </Button>
        </div>
        <Button onClick={() => setShowForm(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nouvelle saisie
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Saisies sur salaire</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Employé</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Créancier</TableHead>
                <TableHead>Montant/Mode</TableHead>
                <TableHead>Dates</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredSeizures.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground">
                    Aucune saisie trouvée
                  </TableCell>
                </TableRow>
              ) : (
                filteredSeizures.map((seizure) => (
                  <TableRow key={seizure.id}>
                    <TableCell>{(seizure as any).employee_name || seizure.employee_id}</TableCell>
                    <TableCell>{SEIZURE_TYPE_LABELS[seizure.type] || seizure.type}</TableCell>
                    <TableCell>{seizure.creditor_name}</TableCell>
                    <TableCell>
                      {seizure.calculation_mode === 'fixe' && seizure.amount
                        ? `${Number(seizure.amount || 0).toFixed(2)}€`
                        : seizure.calculation_mode === 'pourcentage' && seizure.percentage
                        ? `${seizure.percentage}%`
                        : 'Barème légal'}
                    </TableCell>
                    <TableCell>
                      {new Date(seizure.start_date).toLocaleDateString('fr-FR')}
                      {seizure.end_date && ` - ${new Date(seizure.end_date).toLocaleDateString('fr-FR')}`}
                    </TableCell>
                    <TableCell>
                      <Badge className={STATUS_COLORS[seizure.status]}>
                        {STATUS_LABELS[seizure.status]}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedSeizure(seizure)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        {seizure.status === 'active' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleStatusChange(seizure.id, 'suspended')}
                          >
                            <Pause className="h-4 w-4" />
                          </Button>
                        )}
                        {seizure.status === 'suspended' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleStatusChange(seizure.id, 'active')}
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(seizure.id)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
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
        <SalarySeizureForm
          onClose={() => setShowForm(false)}
          onSuccess={() => {
            setShowForm(false);
            fetchSeizures();
          }}
        />
      )}

      {selectedSeizure && (
        <SalarySeizureDetail
          seizure={selectedSeizure}
          onClose={() => setSelectedSeizure(null)}
        />
      )}
    </div>
  );
}
