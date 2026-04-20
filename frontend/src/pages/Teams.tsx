import { useCallback, useMemo, useState } from 'react';
import axios from 'axios';
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { Plus, RefreshCw } from 'lucide-react';

import {
  archiveTeam,
  createTeam,
  deleteTeam,
  getTeams,
  reactivateTeam,
  updateTeam,
  type Team,
} from '@/api/teams';
import { getEmployeesForPlanning } from '@/api/planning';
import { TeamCard } from '@/components/teams/TeamCard';
import { TeamPanel } from '@/components/teams/TeamPanel';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useToast } from '@/hooks/use-toast';
import { useCompany } from '@/contexts/CompanyContext';

function apiErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const raw = err.response?.data as { detail?: unknown } | undefined;
    const d = raw?.detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d)) {
      const first = d[0] as { msg?: string } | undefined;
      if (first?.msg) return first.msg;
    }
  }
  return err instanceof Error ? err.message : 'Erreur inattendue';
}

export default function Teams() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { activeCompany } = useCompany();

  const companyId = activeCompany?.company_id ?? '';

  const [showArchived, setShowArchived] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [teamToDelete, setTeamToDelete] = useState<Team | null>(null);

  const teamsQuery = useQuery({
    queryKey: ['teams', showArchived],
    queryFn: () => getTeams(showArchived),
    enabled: Boolean(companyId),
  });

  const employeesQuery = useQuery({
    queryKey: ['employees-list'],
    queryFn: () => getEmployeesForPlanning(),
    enabled: Boolean(companyId),
  });

  const invalidateTeams = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['teams'] });
  }, [queryClient]);

  const createMutation = useMutation({
    mutationFn: createTeam,
    onSuccess: () => {
      invalidateTeams();
      toast({ title: 'Équipe créée' });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: Parameters<typeof updateTeam>[1];
    }) => updateTeam(id, payload),
    onSuccess: () => {
      invalidateTeams();
      toast({ title: 'Équipe mise à jour' });
    },
  });

  const archiveMutation = useMutation({
    mutationFn: archiveTeam,
    onSuccess: () => {
      invalidateTeams();
      toast({ title: 'Équipe archivée' });
    },
    onError: (e) => {
      toast({
        variant: 'destructive',
        title: 'Archivage impossible',
        description: apiErrorMessage(e),
      });
    },
  });

  const reactivateMutation = useMutation({
    mutationFn: reactivateTeam,
    onSuccess: () => {
      invalidateTeams();
      toast({ title: 'Équipe réactivée' });
    },
    onError: (e) => {
      toast({
        variant: 'destructive',
        title: 'Réactivation impossible',
        description: apiErrorMessage(e),
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTeam,
    onSuccess: () => {
      invalidateTeams();
      toast({ title: 'Équipe supprimée' });
      setTeamToDelete(null);
    },
    onError: (e) => {
      toast({
        variant: 'destructive',
        title: 'Suppression impossible',
        description: apiErrorMessage(e),
      });
    },
  });

  const list = teamsQuery.data?.teams ?? [];
  const total = teamsQuery.data?.total ?? 0;
  const archivedCount = teamsQuery.data?.archived_count ?? 0;

  const headerSubtitle = useMemo(() => {
    if (showArchived) {
      return `${total} équipe${total > 1 ? 's' : ''} (${archivedCount} archivée${archivedCount > 1 ? 's' : ''})`;
    }
    return `${total} équipe${total > 1 ? 's' : ''} active${total > 1 ? 's' : ''}`;
  }, [showArchived, total, archivedCount]);

  const openCreate = () => {
    setSelectedTeam(null);
    setPanelOpen(true);
  };

  const openEdit = (team: Team) => {
    setSelectedTeam(team);
    setPanelOpen(true);
  };

  if (!companyId) {
    return (
      <div className="mx-auto max-w-3xl rounded-lg border border-dashed p-8 text-center text-muted-foreground">
        Sélectionnez une entreprise pour gérer les équipes.
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Équipes</h1>
          <p className="mt-1 text-sm text-muted-foreground">{headerSubtitle}</p>
          {archivedCount > 0 && !showArchived && (
            <p className="mt-1 text-xs text-muted-foreground">
              {archivedCount} archivée{archivedCount > 1 ? 's' : ''} — activez le
              filtre pour les afficher.
            </p>
          )}
        </div>
        <div className="flex flex-col items-stretch gap-3 sm:items-end">
          <Button type="button" onClick={openCreate} className="gap-2">
            <Plus className="h-4 w-4" />
            Nouvelle équipe
          </Button>
          <div className="flex items-center gap-2 rounded-md border bg-card px-3 py-2">
            <Switch
              id="show-archived-teams"
              checked={showArchived}
              onCheckedChange={setShowArchived}
            />
            <Label htmlFor="show-archived-teams" className="text-sm font-normal">
              Voir les équipes archivées
              {archivedCount > 0 && (
                <Badge variant="secondary" className="ml-2">
                  {archivedCount}
                </Badge>
              )}
            </Label>
          </div>
        </div>
      </div>

      {teamsQuery.isLoading && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Équipe</TableHead>
                <TableHead>Responsable</TableHead>
                <TableHead>Salariés</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[0, 1, 2].map((i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-5 w-40" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-12" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-6 w-16" />
                  </TableCell>
                  <TableCell className="text-right">
                    <Skeleton className="ml-auto h-9 w-28" />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {teamsQuery.isError && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {apiErrorMessage(teamsQuery.error)}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-4 gap-2"
            onClick={() => void teamsQuery.refetch()}
          >
            <RefreshCw className="h-4 w-4" />
            Réessayer
          </Button>
        </div>
      )}

      {teamsQuery.isSuccess && list.length === 0 && (
        <div className="rounded-lg border border-dashed bg-muted/30 p-10 text-center text-muted-foreground">
          Aucune équipe créée. Commencez par créer votre première équipe.
        </div>
      )}

      {teamsQuery.isSuccess && list.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Équipe</TableHead>
                <TableHead>Responsable</TableHead>
                <TableHead>Salariés</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.map((team) => (
                <TeamCard
                  key={team.id}
                  team={team}
                  onEdit={openEdit}
                  onArchive={(t) => archiveMutation.mutate(t.id)}
                  onReactivate={(t) => reactivateMutation.mutate(t.id)}
                  onDelete={(t) => setTeamToDelete(t)}
                  isArchiveLoading={
                    (archiveMutation.isPending &&
                      archiveMutation.variables === team.id) ||
                    (reactivateMutation.isPending &&
                      reactivateMutation.variables === team.id)
                  }
                  isDeleteLoading={
                    deleteMutation.isPending &&
                    teamToDelete?.id === team.id
                  }
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <TeamPanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        team={selectedTeam ?? undefined}
        onCreate={async (payload) => {
          try {
            await createMutation.mutateAsync(payload);
          } catch (e) {
            toast({
              variant: 'destructive',
              title: 'Création impossible',
              description: apiErrorMessage(e),
            });
            throw e;
          }
        }}
        onUpdate={async (teamId, payload) => {
          try {
            await updateMutation.mutateAsync({ id: teamId, payload });
          } catch (e) {
            toast({
              variant: 'destructive',
              title: 'Mise à jour impossible',
              description: apiErrorMessage(e),
            });
            throw e;
          }
        }}
        employees={employeesQuery.data ?? []}
        companyId={companyId}
      />

      <AlertDialog
        open={teamToDelete !== null}
        onOpenChange={(open) => !open && setTeamToDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer l’équipe ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action est définitive. L’équipe « {teamToDelete?.name} » sera
              supprimée de la liste.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (teamToDelete) {
                  deleteMutation.mutate(teamToDelete.id);
                }
              }}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
