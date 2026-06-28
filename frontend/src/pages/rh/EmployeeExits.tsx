import { log } from '@/lib/logger';
import { RhPageHeader } from '@/components/layout';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';
import { PlusCircle, Eye, Calendar, Users as UsersIcon, Trash2, RefreshCw, FolderOpen } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { employeeDocumentsPath } from '@/lib/employeeExitDocumentsAccess';
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

function loadErrorMessage(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  return 'Impossible de charger les départs. Vérifiez votre connexion puis réessayez.';
}

const EmployeeExitsPage = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const companyId = useActiveCompanyId();
  const [exits, setExits] = useState<EmployeeExitWithDetails[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedExitType, setSelectedExitType] = useState<string>('all');
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [selectedExit, setSelectedExit] = useState<EmployeeExitWithDetails | null>(null);

  useEffect(() => {
    void fetchExits();
  }, []);

  useEffect(() => {
    if (searchParams.get('create') === '1') {
      setShowCreateDialog(true);
    }
  }, [searchParams]);

  useEffect(() => {
    const exitId = searchParams.get('exitId');
    if (!exitId || exits.length === 0) return;
    const found = exits.find((item) => item.id === exitId);
    if (found) {
      setSelectedExit(found);
    }
  }, [searchParams, exits]);

  const createPrefillEmployeeId = searchParams.get('employeeId') ?? undefined;
  const createPrefillExitType = searchParams.get('exitType') as ExitType | null;
  const returnTo = searchParams.get('returnTo');
  const returnBatchId = searchParams.get('batchId');

  const invalidateEmployeesCache = useCallback(
    (employeeId?: string) => {
      if (!companyId) return;
      void queryClient.invalidateQueries({ queryKey: queryKeys.employees(companyId) });
      if (employeeId) {
        void queryClient.invalidateQueries({
          queryKey: queryKeys.employee(companyId, employeeId),
        });
      }
    },
    [companyId, queryClient],
  );

  const fetchExits = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await getEmployeeExits();
      setExits(data);
    } catch (error: unknown) {
      log.error('Erreur lors du chargement des départs:', error);
      setLoadError(loadErrorMessage(error));
      toast.error('Erreur lors du chargement des départs');
    } finally {
      setLoading(false);
    }
  };

  const filteredExits = useMemo(() => {
    if (selectedExitType === 'all') return exits;
    return exits.filter((e) => e.exit_type === selectedExitType);
  }, [exits, selectedExitType]);

  const exitTypeTabs: Array<{ value: ExitType; label: string }> = [
    { value: 'demission', label: 'Démissions' },
    { value: 'rupture_conventionnelle', label: 'Ruptures conv.' },
    { value: 'licenciement', label: 'Licenciements' },
    { value: 'fin_periode_essai', label: "Périodes d'essai" },
    { value: 'depart_retraite', label: 'Retraites' },
  ];

  const handleDeleteExit = async (exitId: string, employeeName: string) => {
    const confirmMessage = `Êtes-vous sûr de vouloir supprimer le départ de ${employeeName} ?\n\nCette action est irréversible et :\n- Supprimera tous les documents associés\n- Supprimera la checklist\n- Remettra l'employé en statut "actif"`;

    if (!confirm(confirmMessage)) {
      return;
    }

    try {
      await deleteEmployeeExit(exitId);
      toast.success('Le départ a été supprimé avec succès. L\'employé est maintenant en statut "actif".');
      invalidateEmployeesCache();
      fetchExits();
    } catch (error: any) {
      log.error('Erreur lors de la suppression:', error);
      toast.error(error.response?.data?.detail || 'Impossible de supprimer le départ');
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('fr-FR');
  };

  return (
    <div className="space-y-6">
      <RhPageHeader
        title="Départs"
        description="Gérez les processus de départ des collaborateurs et leurs documents de fin de contrat"
        actions={
          <Button onClick={() => setShowCreateDialog(true)}>
            <PlusCircle className="mr-2 h-4 w-4" />
            Nouveau départ
          </Button>
        }
      />

      {/* Statistiques rapides */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">Total des départs</CardTitle>
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

      {/* Tabs par type de départ */}
      <Tabs value={selectedExitType} onValueChange={setSelectedExitType}>
        <TabsList>
          <TabsTrigger value="all">Toutes ({exits.length})</TabsTrigger>
          {exitTypeTabs.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label} ({exits.filter((e) => e.exit_type === tab.value).length})
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value={selectedExitType} className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Liste des départs</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <SharkFinLoader label="Chargement des départs…" />
              ) : loadError ? (
                <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-center">
                  <p className="text-sm text-destructive">{loadError}</p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="mt-4 gap-2"
                    onClick={() => void fetchExits()}
                  >
                    <RefreshCw className="h-4 w-4" />
                    Réessayer
                  </Button>
                </div>
              ) : exits.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <UsersIcon className="h-16 w-16 mx-auto mb-4 text-gray-300" />
                  <p className="text-lg font-medium mb-2">Aucun départ enregistré</p>
                  <p className="text-sm">Cliquez sur « Nouveau départ » pour commencer</p>
                </div>
              ) : filteredExits.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <p className="text-lg font-medium mb-2">Aucun départ pour ce type</p>
                  <p className="text-sm">Sélectionnez un autre onglet ou créez un nouveau départ.</p>
                </div>
              ) : (
                <div className="w-full overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Collaborateur</TableHead>
                        <TableHead>Type de départ</TableHead>
                        <TableHead>Statut</TableHead>
                        <TableHead>Date demande</TableHead>
                        <TableHead>Dernier jour</TableHead>
                        <TableHead>Checklist</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredExits.map((exit) => (
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
                              {exit.employee_id && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  title="Ouvrir le dossier documents du collaborateur"
                                  onClick={() => navigate(employeeDocumentsPath(exit.employee_id))}
                                >
                                  <FolderOpen className="h-4 w-4 mr-1" />
                                  Dossier
                                </Button>
                              )}
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
        onOpenChange={(open) => {
          setShowCreateDialog(open);
          if (!open && searchParams.get('create') === '1') {
            const next = new URLSearchParams(searchParams);
            next.delete('create');
            next.delete('employeeId');
            next.delete('exitType');
            next.delete('returnTo');
            next.delete('batchId');
            setSearchParams(next, { replace: true });
          }
        }}
        initialEmployeeId={createPrefillEmployeeId}
        initialExitType={createPrefillExitType ?? undefined}
        onSuccess={() => {
          invalidateEmployeesCache(createPrefillEmployeeId);
          void fetchExits();
          if (returnTo === 'dsn-import') {
            toast.success('Départ créé. Vous pouvez reprendre l’import DSN.');
            if (returnBatchId) {
              navigate(`/super-admin/dsn-import?resumeBatch=${returnBatchId}`);
            } else {
              navigate('/super-admin/dsn-import');
            }
          }
        }}
      />

      <ExitDetailsPanel
        exitId={selectedExit?.id || null}
        open={!!selectedExit}
        onClose={() => setSelectedExit(null)}
        onUpdate={() => {
          invalidateEmployeesCache(selectedExit?.employee_id);
          void fetchExits();
        }}
      />
    </div>
  );
};

export default EmployeeExitsPage;
