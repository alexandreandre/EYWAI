import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Calendar,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import type { EmployeeCalendarOverviewRow } from '@/lib/schedulesOverview';
import type { Team } from '@/api/teams';
import type { SortDir, SortKey } from './types';
import { cn } from '@/lib/utils';
import { isSignificantEcart } from '@/lib/calendarStats';

const ROW_STATUS_LABELS: Record<string, string> = {
  a_saisir: 'À saisir',
  saisi: 'Saisi',
  saisi_avec_ecart: 'Écart',
};

const ROW_STATUS_VARIANT: Record<
  string,
  'default' | 'secondary' | 'outline' | 'destructive'
> = {
  a_saisir: 'outline',
  saisi: 'secondary',
  saisi_avec_ecart: 'destructive',
};

interface CalendarEmployeeTableProps {
  rows: EmployeeCalendarOverviewRow[];
  teamsById: Map<string, Team>;
  isLoading: boolean;
  employeesLoadError?: boolean;
  employeesLoadErrorMessage?: string;
  onRetryEmployees?: () => void;
  unfilteredRowCount?: number;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onToggleSelectAll: (ids: string[]) => void;
  onOpenEmployee: (id: string) => void;
  sortKey: SortKey;
  sortDir: SortDir;
  onSort: (key: SortKey) => void;
  visibleIds: string[];
}

function SortIcon({
  column,
  sortKey,
  sortDir,
}: {
  column: SortKey;
  sortKey: SortKey;
  sortDir: SortDir;
}) {
  if (sortKey !== column) return <ArrowUpDown className="h-3.5 w-3.5 opacity-40" />;
  return sortDir === 'asc' ? (
    <ArrowUp className="h-3.5 w-3.5" />
  ) : (
    <ArrowDown className="h-3.5 w-3.5" />
  );
}

function formatHours(value: number, isForfait: boolean): string {
  if (isForfait) return `${value.toFixed(0)} j`;
  return `${value.toFixed(1)} h`;
}

export function CalendarEmployeeTable({
  rows,
  teamsById,
  isLoading,
  employeesLoadError = false,
  employeesLoadErrorMessage,
  onRetryEmployees,
  unfilteredRowCount = 0,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  onOpenEmployee,
  sortKey,
  sortDir,
  onSort,
  visibleIds,
}: CalendarEmployeeTableProps) {
  const allVisibleSelected =
    visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id));

  if (isLoading) {
    return (
      <div className="rounded-md border">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-none border-b last:border-0" />
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    if (employeesLoadError) {
      return (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-12 text-center">
          <AlertTriangle className="mx-auto h-10 w-10 text-destructive/70 mb-3" />
          <p className="font-medium text-destructive">
            {employeesLoadErrorMessage ?? 'Impossible de charger la liste des employés.'}
          </p>
          {onRetryEmployees && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-4 gap-2"
              onClick={onRetryEmployees}
            >
              <RefreshCw className="h-4 w-4" />
              Réessayer
            </Button>
          )}
        </div>
      );
    }

    if (unfilteredRowCount === 0) {
      return (
        <div className="rounded-md border border-dashed p-12 text-center">
          <CheckCircle2 className="mx-auto h-10 w-10 text-muted-foreground/50 mb-3" />
          <p className="font-medium text-foreground">Aucun employé à piloter</p>
          <p className="text-sm text-muted-foreground mt-1">
            Aucun collaborateur éligible n&apos;est disponible pour ce mois.
          </p>
        </div>
      );
    }

    return (
      <div className="rounded-md border border-dashed p-12 text-center">
        <CheckCircle2 className="mx-auto h-10 w-10 text-muted-foreground/50 mb-3" />
        <p className="font-medium text-foreground">Aucun employé ne correspond à vos filtres</p>
        <p className="text-sm text-muted-foreground mt-1">
          Modifiez la recherche ou les filtres pour afficher des résultats.
        </p>
      </div>
    );
  }

  const allSaisi = rows.every((r) => r.rowStatus !== 'a_saisir');
  if (allSaisi && rows.length > 0) {
    // optional banner when filtered set is complete
  }

  return (
    <div className="rounded-md border overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            <TableHead className="w-10">
              <Checkbox
                checked={allVisibleSelected}
                onCheckedChange={() => onToggleSelectAll(visibleIds)}
                aria-label="Tout sélectionner"
              />
            </TableHead>
            <TableHead>
              <button
                type="button"
                className="flex items-center gap-1 font-medium"
                onClick={() => onSort('name')}
              >
                Collaborateur
                <SortIcon column="name" sortKey={sortKey} sortDir={sortDir} />
              </button>
            </TableHead>
            <TableHead>
              <button
                type="button"
                className="flex items-center gap-1 font-medium"
                onClick={() => onSort('team')}
              >
                Équipe
                <SortIcon column="team" sortKey={sortKey} sortDir={sortDir} />
              </button>
            </TableHead>
            <TableHead>
              <button
                type="button"
                className="flex items-center gap-1 font-medium"
                onClick={() => onSort('status')}
              >
                Statut
                <SortIcon column="status" sortKey={sortKey} sortDir={sortDir} />
              </button>
            </TableHead>
            <TableHead className="text-right">
              <button
                type="button"
                className="flex items-center gap-1 font-medium ml-auto"
                onClick={() => onSort('heures_prevues')}
              >
                H. prévues
                <SortIcon column="heures_prevues" sortKey={sortKey} sortDir={sortDir} />
              </button>
            </TableHead>
            <TableHead className="text-right">
              <button
                type="button"
                className="flex items-center gap-1 font-medium ml-auto"
                onClick={() => onSort('heures_faites')}
              >
                H. faites
                <SortIcon column="heures_faites" sortKey={sortKey} sortDir={sortDir} />
              </button>
            </TableHead>
            <TableHead className="text-right">
              <button
                type="button"
                className="flex items-center gap-1 font-medium ml-auto"
                onClick={() => onSort('ecart')}
              >
                Écart
                <SortIcon column="ecart" sortKey={sortKey} sortDir={sortDir} />
              </button>
            </TableHead>
            <TableHead className="w-16 text-center">Alertes</TableHead>
            <TableHead className="w-12" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const team = row.employee.team_id
              ? teamsById.get(row.employee.team_id)
              : undefined;
            const ecartSignificant = !row.isForfaitJour
              ? isSignificantEcart(row.heuresPrevues, row.heuresFaites)
              : row.ecart !== 0;
            const ecartLabel = row.isForfaitJour
              ? `${row.ecart >= 0 ? '+' : ''}${row.ecart} j`
              : `${row.ecart >= 0 ? '+' : ''}${row.ecart.toFixed(1)} h`;

            return (
              <TableRow
                key={row.employee.id}
                className={cn(
                  'cursor-pointer',
                  selectedIds.has(row.employee.id) && 'bg-primary/5',
                  row.loadError && 'bg-destructive/5'
                )}
                onClick={() => onOpenEmployee(row.employee.id)}
              >
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Checkbox
                    checked={selectedIds.has(row.employee.id)}
                    onCheckedChange={() => onToggleSelect(row.employee.id)}
                  />
                </TableCell>
                <TableCell>
                  <div className="font-medium">
                    {row.employee.last_name} {row.employee.first_name}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {row.employee.job_title ?? '—'}
                    {row.isForfaitJour ? ' · Forfait jour' : ' · Horaire'}
                  </div>
                </TableCell>
                <TableCell>
                  {team ? (
                    <Badge
                      variant="outline"
                      className="text-xs font-normal"
                      style={{
                        borderColor: team.color,
                        color: team.color,
                      }}
                    >
                      {team.name}
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={ROW_STATUS_VARIANT[row.rowStatus] ?? 'outline'}>
                    {ROW_STATUS_LABELS[row.rowStatus] ?? row.rowStatus}
                  </Badge>
                </TableCell>
                <TableCell className="text-right tabular-nums text-sm">
                  {formatHours(row.heuresPrevues, row.isForfaitJour)}
                </TableCell>
                <TableCell className="text-right tabular-nums text-sm">
                  {formatHours(row.heuresFaites, row.isForfaitJour)}
                </TableCell>
                <TableCell
                  className={cn(
                    'text-right tabular-nums text-sm font-medium',
                    ecartSignificant && 'text-destructive'
                  )}
                >
                  {ecartLabel}
                </TableCell>
                <TableCell className="text-center">
                  <TooltipProvider>
                    {row.absenceConflictDays.length > 0 && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <AlertTriangle className="h-4 w-4 text-amber-600 inline" />
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="text-xs">
                            Absence validée non reflétée : jours{' '}
                            {row.absenceConflictDays.join(', ')}
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    )}
                    {row.loadError && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <AlertTriangle className="h-4 w-4 text-destructive inline ml-1" />
                        </TooltipTrigger>
                        <TooltipContent>
                          <p className="text-xs">Erreur de chargement du calendrier</p>
                        </TooltipContent>
                      </Tooltip>
                    )}
                  </TooltipProvider>
                </TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onOpenEmployee(row.employee.id)}
                    aria-label="Voir le calendrier"
                  >
                    <Calendar className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
