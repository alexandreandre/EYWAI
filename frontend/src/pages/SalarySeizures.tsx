// frontend/src/pages/SalarySeizures.tsx

import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Plus, Loader2, Pause, Play, X, Eye, Scale, AlertCircle, CheckCircle } from "lucide-react";
import { getSalarySeizures, deleteSalarySeizure, updateSalarySeizure } from '@/api/saisiesAvances';
import type { SalarySeizure, SalarySeizureStatus } from '@/api/saisiesAvances';
import { SalarySeizureForm } from '@/components/saisies-avances/SalarySeizureForm';
import { SalarySeizureDetail } from '@/components/saisies-avances/SalarySeizureDetail';

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

export default function SalarySeizures() {
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

  const stats = {
    total: seizures.length,
    active: seizures.filter(s => s.status === 'active').length,
    suspended: seizures.filter(s => s.status === 'suspended').length,
    closed: seizures.filter(s => s.status === 'closed').length,
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Scale className="h-8 w-8" />
          Saisies sur salaire
        </h1>
        <p className="text-muted-foreground mt-2">
          Gestion des prélèvements obligatoires sur salaire (saisie-arrêt, pension alimentaire, ATD, SATD)
        </p>
      </div>

      {/* Statistiques */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total saisies</CardTitle>
            <Scale className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">toutes périodes</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Actives</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{stats.active}</div>
            <p className="text-xs text-muted-foreground">en cours</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Suspendues</CardTitle>
            <AlertCircle className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{stats.suspended}</div>
            <p className="text-xs text-muted-foreground">temporairement</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Clôturées</CardTitle>
            <X className="h-4 w-4 text-gray-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-600">{stats.closed}</div>
            <p className="text-xs text-muted-foreground">terminées</p>
          </CardContent>
        </Card>
      </div>

      {/* Filtres et actions */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <Button
            variant={filterStatus === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('all')}
          >
            Toutes ({stats.total})
          </Button>
          <Button
            variant={filterStatus === 'active' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('active')}
          >
            Actives ({stats.active})
          </Button>
          <Button
            variant={filterStatus === 'suspended' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('suspended')}
          >
            Suspendues ({stats.suspended})
          </Button>
          <Button
            variant={filterStatus === 'closed' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterStatus('closed')}
          >
            Clôturées ({stats.closed})
          </Button>
        </div>
        <Button onClick={() => setShowForm(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nouvelle saisie
        </Button>
      </div>

      {/* Tableau */}
      <Card>
        <CardHeader>
          <CardTitle>Liste des saisies</CardTitle>
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
                  <TableHead>Type</TableHead>
                  <TableHead>Créancier</TableHead>
                  <TableHead>Montant/Mode</TableHead>
                  <TableHead>Dates</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredSeizures.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                      Aucune saisie trouvée
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredSeizures.map((seizure) => (
                    <TableRow key={seizure.id}>
                      <TableCell className="font-medium">
                        {(seizure as any).employee_name || seizure.employee_id}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {SEIZURE_TYPE_LABELS[seizure.type] || seizure.type}
                        </Badge>
                      </TableCell>
                      <TableCell>{seizure.creditor_name}</TableCell>
                      <TableCell>
                        {seizure.calculation_mode === 'fixe' && seizure.amount
                          ? `${seizure.amount.toFixed(2)}€`
                          : seizure.calculation_mode === 'pourcentage' && seizure.percentage
                          ? `${seizure.percentage}%`
                          : 'Barème légal'}
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">
                          <div>Début: {new Date(seizure.start_date).toLocaleDateString('fr-FR')}</div>
                          {seizure.end_date && (
                            <div className="text-muted-foreground">
                              Fin: {new Date(seizure.end_date).toLocaleDateString('fr-FR')}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={STATUS_COLORS[seizure.status]}>
                          {STATUS_LABELS[seizure.status]}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex gap-2 justify-end">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedSeizure(seizure)}
                            title="Voir détails"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          {seizure.status === 'active' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleStatusChange(seizure.id, 'suspended')}
                              title="Suspendre"
                            >
                              <Pause className="h-4 w-4" />
                            </Button>
                          )}
                          {seizure.status === 'suspended' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleStatusChange(seizure.id, 'active')}
                              title="Reprendre"
                            >
                              <Play className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(seizure.id)}
                            title="Supprimer"
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
          )}
        </CardContent>
      </Card>

      {/* Modals */}
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
