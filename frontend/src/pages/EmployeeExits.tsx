import React, { useState, useEffect } from 'react';
import { PlusCircle, Eye, Calendar, FileText, Users as UsersIcon, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';
import {
  getEmployeeExits,
  deleteEmployeeExit,
  type EmployeeExitWithDetails,
  type ExitType,
  exitTypeLabels,
  statusLabels,
  getStatusVariant,
} from '@/api/employeeExits';
import { CreateExitDialog } from '@/components/exits/CreateExitDialog';
import { ExitDetailsPanel } from '@/components/exits/ExitDetailsPanel';

const EmployeeExitsPage = () => {
  const [exits, setExits] = useState<EmployeeExitWithDetails[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedExitType, setSelectedExitType] = useState<string>('all');
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [selectedExit, setSelectedExit] = useState<EmployeeExitWithDetails | null>(null);

  useEffect(() => {
    fetchExits();
  }, [selectedExitType]);

  const fetchExits = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (selectedExitType !== 'all') {
        params.exit_type = selectedExitType;
      }
      const data = await getEmployeeExits(params);
      setExits(data);
    } catch (error: any) {
      console.error('Erreur lors du chargement des sorties:', error);
      toast.error('Erreur lors du chargement des sorties');
    } finally {
      setLoading(false);
    }
  };

  const handleExitCreated = () => {
    setShowCreateDialog(false);
    fetchExits();
    toast.success('Processus de sortie créé avec succès');
  };

  const handleDeleteExit = async (exitId: string, employeeName: string) => {
    const confirmMessage = `Êtes-vous sûr de vouloir supprimer la sortie de ${employeeName} ?\n\nCette action est irréversible et :\n- Supprimera tous les documents associés\n- Supprimera la checklist\n- Remettra l'employé en statut "actif"`;

    if (!confirm(confirmMessage)) {
      return;
    }

    try {
      await deleteEmployeeExit(exitId);
      toast.success('La sortie a été supprimée avec succès. L\'employé est maintenant en statut "actif".');
      fetchExits();
    } catch (error: any) {
      console.error('Erreur lors de la suppression:', error);
      toast.error(error.response?.data?.detail || 'Impossible de supprimer la sortie');
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('fr-FR');
  };

  return (
    <div className="space-y-6 p-6">
      {/* En-tête */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Sortie du collaborateur</h1>
          <p className="text-gray-600 mt-1">
            Gérez les processus de sortie des collaborateurs (démissions, ruptures conventionnelles, licenciements)
          </p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)}>
          <PlusCircle className="mr-2 h-4 w-4" />
          Nouvelle sortie
        </Button>
      </div>

      {/* Statistiques rapides */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">Total sorties</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{exits.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">En cours</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {exits.filter(e => !e.status.includes('effective') && !e.status.includes('archivee') && !e.status.includes('annulee')).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">Effectives</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {exits.filter(e => e.status.includes('effective')).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">Archivées</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-600">
              {exits.filter(e => e.status.includes('archivee')).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs par type de sortie */}
      <Tabs value={selectedExitType} onValueChange={setSelectedExitType}>
        <TabsList>
          <TabsTrigger value="all">Toutes ({exits.length})</TabsTrigger>
          <TabsTrigger value="demission">
            Démissions ({exits.filter(e => e.exit_type === 'demission').length})
          </TabsTrigger>
          <TabsTrigger value="rupture_conventionnelle">
            Ruptures conv. ({exits.filter(e => e.exit_type === 'rupture_conventionnelle').length})
          </TabsTrigger>
          <TabsTrigger value="licenciement">
            Licenciements ({exits.filter(e => e.exit_type === 'licenciement').length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value={selectedExitType} className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Liste des sorties</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="text-center py-12">
                  <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent"></div>
                  <p className="mt-2 text-sm text-gray-600">Chargement...</p>
                </div>
              ) : exits.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <UsersIcon className="h-16 w-16 mx-auto mb-4 text-gray-300" />
                  <p className="text-lg font-medium mb-2">Aucune sortie enregistrée</p>
                  <p className="text-sm">Cliquez sur "Nouvelle sortie" pour commencer</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Collaborateur</TableHead>
                        <TableHead>Type de sortie</TableHead>
                        <TableHead>Statut</TableHead>
                        <TableHead>Date demande</TableHead>
                        <TableHead>Dernier jour</TableHead>
                        <TableHead>Checklist</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {exits.map((exit) => (
                        <TableRow key={exit.id} className="hover:bg-gray-50">
                          <TableCell>
                            <div>
                              <div className="font-medium text-gray-900">
                                {exit.employee?.first_name} {exit.employee?.last_name}
                              </div>
                              {exit.employee?.job_title && (
                                <div className="text-sm text-gray-500">{exit.employee.job_title}</div>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <span className="text-sm font-medium">
                              {exitTypeLabels[exit.exit_type as ExitType]}
                            </span>
                          </TableCell>
                          <TableCell>
                            <Badge variant={getStatusVariant(exit.status)}>
                              {statusLabels[exit.status]}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1 text-sm">
                              <Calendar className="h-4 w-4 text-gray-400" />
                              {formatDate(exit.exit_request_date)}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1 text-sm">
                              <Calendar className="h-4 w-4 text-gray-400" />
                              {formatDate(exit.last_working_day)}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Progress
                                value={exit.checklist_completion_rate || 0}
                                className="w-20 h-2"
                              />
                              <span className="text-xs text-gray-600">
                                {Math.round(exit.checklist_completion_rate || 0)}%
                              </span>
                            </div>
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setSelectedExit(exit)}
                              >
                                <Eye className="h-4 w-4 mr-1" />
                                Détails
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteExit(
                                  exit.id,
                                  `${exit.employee?.first_name} ${exit.employee?.last_name}`
                                )}
                                className="text-destructive hover:text-destructive hover:bg-destructive/10"
                              >
                                <Trash2 className="h-4 w-4 mr-1" />
                                Supprimer
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
      <CreateExitDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onSuccess={fetchExits}
      />

      <ExitDetailsPanel
        exitId={selectedExit?.id || null}
        open={!!selectedExit}
        onClose={() => setSelectedExit(null)}
        onUpdate={fetchExits}
      />
    </div>
  );
};

export default EmployeeExitsPage;
