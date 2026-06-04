import { pageTitleClassName } from '@/components/layout';
import { useCallback, useMemo, useState } from 'react';
import { getUserErrorMessage } from '@/lib/errorMessages';
import { Link } from 'react-router-dom';
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { ArrowUpDown, BarChart2, Plus, RefreshCw, Search } from 'lucide-react';

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
import { Input } from '@/components/ui/input';
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
import { cn } from '@/lib/utils';

function apiErrorMessage(err: unknown): string {
  return getUserErrorMessage(err, 'L’opération a échoué. Réessayez.');
}

type SortKey = 'name' | 'employee_count' | 'manager';
type SortOrder = 'asc' | 'desc';

function managerSearchText(team: Team): string {
  const fn = team.manager_first_name?.trim() ?? '';
  const ln = team.manager_last_name?.trim() ?? '';
  return `${fn} ${ln}`.toLowerCase();
}

function SortableHead({
  label,
  active,
  order,
  onClick,
  className,
}: {
  label: string;
  active: boolean;
  order: SortOrder;
  onClick: () => void;
  className?: string;
}) {
  return (
    <TableHead className={className}>
      <button
        type="button"
        className="inline-flex items-center gap-1 font-medium hover:text-foreground"
        onClick={onClick}
      >
        {label}
        <ArrowUpDown
          className={cn('h-3.5 w-3.5', active ? 'text-foreground' : 'text-muted-foreground')}
        />
        {active ? (
          <span className="sr-only">
            {order === 'asc' ? 'croissant' : 'décroissant'}
          </span>
        ) : null}
      </button>
    </TableHead>
  );
}

export default function Teams() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { activeCompany } = useCompany();

  const companyId = activeCompany?.company_id ?? '';

  const [showArchived, setShowArchived] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [panelFocusMembers, setPanelFocusMembers] = useState(false);
  const [teamToDelete, setTeamToDelete] = useState<Team | null>(null);
  const [teamToArchive, setTeamToArchive] = useState<Team | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

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
    void queryClient.invalidateQueries({ queryKey: ['team-detail'] });
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
      setTeamToArchive(null);
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

  const filteredAndSorted = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    let rows = list;
    if (q) {
      rows = rows.filter((team) => {
        const name = team.name.toLowerCase();
        const desc = (team.description ?? '').toLowerCase();
        const mgr = managerSearchText(team);
        return name.includes(q) || desc.includes(q) || mgr.includes(q);
      });
    }
    const sorted = [...rows].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') {
        cmp = a.name.localeCompare(b.name, 'fr');
      } else if (sortKey === 'employee_count') {
        cmp = a.employee_count - b.employee_count;
      } else {
        cmp = managerSearchText(a).localeCompare(managerSearchText(b), 'fr');
      }
      return sortOrder === 'asc' ? cmp : -cmp;
    });
    return sorted;
  }, [list, searchQuery, sortKey, sortOrder]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortOrder(key === 'employee_count' ? 'desc' : 'asc');
    }
  };

  const openCreate = () => {
    setSelectedTeam(null);
    setPanelFocusMembers(false);
    setPanelOpen(true);
  };

  const openEdit = (team: Team, options?: { focusMembers?: boolean }) => {
    setSelectedTeam(team);
    setPanelFocusMembers(Boolean(options?.focusMembers));
    setPanelOpen(true);
  };

  const closePanel = () => {
    setPanelOpen(false);
    setPanelFocusMembers(false);
  };

  const tableHeaders = (
    <TableRow>
      <SortableHead
        label="Équipe"
        active={sortKey === 'name'}
        order={sortOrder}
        onClick={() => toggleSort('name')}
      />
      <SortableHead
        label="Responsable"
        active={sortKey === 'manager'}
        order={sortOrder}
        onClick={() => toggleSort('manager')}
      />
      <SortableHead
        label="Salariés"
        active={sortKey === 'employee_count'}
        order={sortOrder}
        onClick={() => toggleSort('employee_count')}
      />
      <TableHead>Statut</TableHead>
      <TableHead className="text-right">Actions</TableHead>
    </TableRow>
  );

  if (!companyId) {
    return (
      <div className="container mx-auto max-w-3xl rounded-lg border border-dashed p-8 text-center text-muted-foreground">
        Sélectionnez une entreprise pour gérer les équipes.
      </div>
    );
  }

  const hasSearch = searchQuery.trim().length > 0;
  const showEmptySearch =
    teamsQuery.isSuccess && list.length > 0 && filteredAndSorted.length === 0;

  return (
    <div className="container mx-auto flex max-w-7xl flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <h1 className={pageTitleClassName}>Équipes</h1>
          <p className="text-sm text-muted-foreground">{headerSubtitle}</p>
          <p className="text-xs text-muted-foreground max-w-xl">
            Les salariés sont affectés depuis la fiche collaborateur. L’archivage
            retire l’équipe de l’organisation active et désaffecte ses membres.
          </p>
          <Link
            to="/analytics"
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <BarChart2 className="h-3.5 w-3.5" />
            Analytics Team
          </Link>
          {archivedCount > 0 && !showArchived && (
            <p className="text-xs text-muted-foreground">
              {archivedCount} archivée{archivedCount > 1 ? 's' : ''} — activez le
              filtre pour les afficher.
            </p>
          )}
        </div>
        <div className="flex flex-col items-stretch gap-3 sm:items-end">
          <div className="flex flex-wrap gap-2 sm:justify-end">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => void teamsQuery.refetch()}
              disabled={teamsQuery.isFetching}
            >
              <RefreshCw
                className={cn('h-4 w-4', teamsQuery.isFetching && 'animate-spin')}
              />
              Actualiser
            </Button>
            <Button type="button" onClick={openCreate} className="gap-2">
              <Plus className="h-4 w-4" />
              Nouvelle équipe
            </Button>
          </div>
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

      {teamsQuery.isSuccess && list.length > 0 && (
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Rechercher une équipe, un responsable…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
            aria-label="Rechercher dans les équipes"
          />
        </div>
      )}

      {teamsQuery.isLoading && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>{tableHeaders}</TableHeader>
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
        <div className="rounded-lg border border-dashed bg-muted/30 p-10 text-center text-muted-foreground space-y-4">
          <p>Aucune équipe créée. Commencez par créer votre première équipe.</p>
          <Button type="button" onClick={openCreate} className="gap-2">
            <Plus className="h-4 w-4" />
            Nouvelle équipe
          </Button>
        </div>
      )}

      {showEmptySearch && (
        <div className="rounded-lg border border-dashed bg-muted/30 p-8 text-center text-muted-foreground">
          Aucune équipe ne correspond à votre recherche.
          {hasSearch && (
            <Button
              type="button"
              variant="link"
              className="mt-2 block mx-auto"
              onClick={() => setSearchQuery('')}
            >
              Effacer la recherche
            </Button>
          )}
        </div>
      )}

      {teamsQuery.isSuccess && filteredAndSorted.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>{tableHeaders}</TableHeader>
            <TableBody>
              {filteredAndSorted.map((team) => (
                <TeamCard
                  key={team.id}
                  team={team}
                  onEdit={openEdit}
                  onArchive={(t) => setTeamToArchive(t)}
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
        onClose={closePanel}
        team={selectedTeam ?? undefined}
        focusMembers={panelFocusMembers}
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
        open={teamToArchive !== null}
        onOpenChange={(open) => !open && setTeamToArchive(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archiver cette équipe ?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2 text-sm text-muted-foreground">
                <p>
                  L’équipe « {teamToArchive?.name} » ne sera plus active dans
                  l’organisation.
                </p>
                {(teamToArchive?.employee_count ?? 0) > 0 ? (
                  <p>
                    Les{' '}
                    <strong>
                      {teamToArchive?.employee_count} salarié
                      {(teamToArchive?.employee_count ?? 0) > 1 ? 's' : ''}
                    </strong>{' '}
                    seront retirés de cette équipe (leurs fiches ne sont pas
                    supprimées). Réaffectez-les depuis la fiche Collaborateur si
                    besoin.
                  </p>
                ) : (
                  <p>Aucun salarié n’est actuellement affecté à cette équipe.</p>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (teamToArchive) {
                  archiveMutation.mutate(teamToArchive.id);
                }
              }}
            >
              Archiver
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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
