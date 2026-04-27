import { Users } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { TableCell, TableRow } from '@/components/ui/table';
import type { Team } from '@/api/teams';

export type TeamCardProps = {
  team: Team;
  onEdit: (team: Team) => void;
  onArchive: (team: Team) => void;
  onReactivate: (team: Team) => void;
  onDelete: (team: Team) => void;
  isArchiveLoading: boolean;
  isDeleteLoading: boolean;
};

function managerLabel(team: Team): string {
  const fn = team.manager_first_name?.trim();
  const ln = team.manager_last_name?.trim();
  if (!fn && !ln) return '—';
  const last = ln ? ln.toUpperCase() : '';
  return [fn, last].filter(Boolean).join(' ');
}

export function TeamCard({
  team,
  onEdit,
  onArchive,
  onReactivate,
  onDelete,
  isArchiveLoading,
  isDeleteLoading,
}: TeamCardProps) {
  const isActive = team.status === 'active';
  const canDelete = team.employee_count === 0;

  return (
    <TableRow
      className="cursor-pointer"
      onClick={() => onEdit(team)}
    >
      <TableCell>
        <div className="flex items-center gap-3">
          <span
            className="h-3 w-3 shrink-0 rounded-full ring-1 ring-border"
            style={{ backgroundColor: team.color }}
            aria-hidden
          />
          <span className="font-medium">{team.name}</span>
        </div>
      </TableCell>
      <TableCell className="text-muted-foreground">{managerLabel(team)}</TableCell>
      <TableCell>
        <span className="inline-flex items-center gap-1.5 tabular-nums">
          <Users className="h-4 w-4 text-muted-foreground" aria-hidden />
          {team.employee_count}
        </span>
      </TableCell>
      <TableCell>
        {isActive ? (
          <Badge className="bg-emerald-600 hover:bg-emerald-600/90">Actif</Badge>
        ) : (
          <Badge variant="secondary">Archivé</Badge>
        )}
      </TableCell>
      <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
        <div className="flex flex-wrap justify-end gap-2">
          {isActive ? (
            <>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => onEdit(team)}
              >
                Modifier
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={isArchiveLoading}
                onClick={() => onArchive(team)}
              >
                Archiver
              </Button>
            </>
          ) : (
            <>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={isArchiveLoading}
                onClick={() => onReactivate(team)}
              >
                Réactiver
              </Button>
              <Button
                type="button"
                size="sm"
                variant="destructive"
                disabled={!canDelete || isDeleteLoading}
                title={
                  !canDelete
                    ? 'Archivez ou réaffectez les salariés avant suppression'
                    : undefined
                }
                onClick={() => onDelete(team)}
              >
                Supprimer
              </Button>
            </>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}
