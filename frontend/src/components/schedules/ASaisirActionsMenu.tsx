import { useEffect, useMemo, useState } from 'react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ListChecks,
  Sparkles,
} from 'lucide-react';
import type { EmployeeCalendarOverviewRow } from '@/lib/schedulesOverview';
import type { Team } from '@/api/teams';

interface ASaisirActionsMenuProps {
  /** Lignes « À saisir » correspondant aux filtres actifs. */
  rows: EmployeeCalendarOverviewRow[];
  teamsById: Map<string, Team>;
  allSelected: boolean;
  onSelectSubset: (ids: string[]) => void;
  onFillWithAi: (ids: string[]) => void;
  disabled?: boolean;
}

export function ASaisirActionsMenu({
  rows,
  teamsById,
  allSelected,
  onSelectSubset,
  onFillWithAi,
  disabled = false,
}: ASaisirActionsMenuProps) {
  const [open, setOpen] = useState(false);
  const [pickedIds, setPickedIds] = useState<Set<string>>(new Set());

  const count = rows.length;
  const rowIds = useMemo(() => rows.map((r) => r.employee.id), [rows]);
  const pickedCount = pickedIds.size;
  const allPicked = count > 0 && pickedCount === count;
  const nonePicked = pickedCount === 0;

  useEffect(() => {
    if (open) {
      setPickedIds(new Set(rowIds));
    }
  }, [open, rowIds]);

  const stats = useMemo(() => {
    let horaire = 0;
    let forfait = 0;
    let loadErrors = 0;
    let conflits = 0;
    const teamCounts = new Map<string, number>();
    let sansEquipe = 0;

    for (const row of rows) {
      if (row.isForfaitJour) forfait += 1;
      else horaire += 1;
      if (row.loadError) loadErrors += 1;
      if (row.absenceConflictDays.length > 0) conflits += 1;

      const teamId = row.employee.team_id;
      if (teamId) {
        teamCounts.set(teamId, (teamCounts.get(teamId) ?? 0) + 1);
      } else {
        sansEquipe += 1;
      }
    }

    const teams = [...teamCounts.entries()]
      .map(([id, n]) => ({
        name: teamsById.get(id)?.name ?? 'Équipe',
        color: teamsById.get(id)?.color,
        count: n,
      }))
      .sort((a, b) => b.count - a.count);

    return { horaire, forfait, loadErrors, conflits, teams, sansEquipe };
  }, [rows, teamsById]);

  const sortedRows = useMemo(
    () =>
      [...rows].sort((a, b) =>
        `${a.employee.last_name} ${a.employee.first_name}`.localeCompare(
          `${b.employee.last_name} ${b.employee.first_name}`,
          'fr'
        )
      ),
    [rows]
  );

  if (count === 0) {
    return (
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-9 gap-1.5 lg:ml-auto text-emerald-700 border-emerald-200"
        disabled
      >
        <CheckCircle2 className="h-4 w-4" />
        Aucun calendrier à saisir
      </Button>
    );
  }

  const togglePicked = (id: string) => {
    setPickedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const setAllPicked = (checked: boolean) => {
    setPickedIds(checked ? new Set(rowIds) : new Set());
  };

  const handleSelectSubset = () => {
    onSelectSubset([...pickedIds]);
    setOpen(false);
  };

  const handleFillWithAi = () => {
    onFillWithAi([...pickedIds]);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant={allSelected ? 'secondary' : 'default'}
          size="sm"
          className="h-9 gap-1.5 lg:ml-auto"
          disabled={disabled}
        >
          <ListChecks className="h-4 w-4" />
          {count} à saisir
          <ChevronDown className="h-3.5 w-3.5 opacity-70" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="flex w-80 max-h-[min(32rem,85vh)] flex-col overflow-hidden p-0"
      >
        <div className="shrink-0 border-b px-4 py-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold">Calendriers à saisir</p>
            <Badge variant="secondary" className="tabular-nums">
              {count}
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Cochez les collaborateurs à traiter, puis lancez une action en
            masse ou un remplissage IA.
          </p>
        </div>

        <div className="grid shrink-0 grid-cols-2 gap-2 px-4 py-3 text-xs">
          <div className="rounded-md border bg-muted/30 px-2.5 py-2">
            <p className="text-muted-foreground">Horaire</p>
            <p className="text-base font-semibold tabular-nums">
              {stats.horaire}
            </p>
          </div>
          <div className="rounded-md border bg-muted/30 px-2.5 py-2">
            <p className="text-muted-foreground">Forfait jour</p>
            <p className="text-base font-semibold tabular-nums">
              {stats.forfait}
            </p>
          </div>
        </div>

        {(stats.teams.length > 0 || stats.sansEquipe > 0) && (
          <div className="flex shrink-0 flex-wrap gap-1.5 px-4 pb-3">
            {stats.teams.map((t) => (
              <Badge
                key={t.name}
                variant="outline"
                className="text-[11px] font-normal"
                style={t.color ? { borderColor: t.color, color: t.color } : undefined}
              >
                {t.name} · {t.count}
              </Badge>
            ))}
            {stats.sansEquipe > 0 && (
              <Badge variant="outline" className="text-[11px] font-normal">
                Sans équipe · {stats.sansEquipe}
              </Badge>
            )}
          </div>
        )}

        {(stats.loadErrors > 0 || stats.conflits > 0) && (
          <div className="mx-4 mb-3 shrink-0 space-y-1 rounded-md border border-amber-200 bg-amber-50/70 px-2.5 py-2 text-[11px] text-amber-900">
            {stats.conflits > 0 && (
              <p className="flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                {stats.conflits} avec une absence validée non reflétée
              </p>
            )}
            {stats.loadErrors > 0 && (
              <p className="flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                {stats.loadErrors} calendrier(s) en erreur de chargement
              </p>
            )}
          </div>
        )}

        <div className="flex shrink-0 items-center justify-between border-t px-4 py-2 text-xs">
          <span className="text-muted-foreground tabular-nums">
            {pickedCount} / {count} sélectionné{pickedCount > 1 ? 's' : ''}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="text-primary hover:underline disabled:opacity-40"
              disabled={allPicked}
              onClick={() => setAllPicked(true)}
            >
              Tout cocher
            </button>
            <button
              type="button"
              className="text-muted-foreground hover:underline disabled:opacity-40"
              disabled={nonePicked}
              onClick={() => setAllPicked(false)}
            >
              Tout décocher
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain border-t">
          <ul className="divide-y">
            {sortedRows.map((row) => {
              const team = row.employee.team_id
                ? teamsById.get(row.employee.team_id)
                : undefined;
              const id = row.employee.id;
              const checked = pickedIds.has(id);
              return (
                <li key={id}>
                  <label className="flex cursor-pointer items-center gap-2.5 px-4 py-2 text-xs hover:bg-muted/40">
                    <Checkbox
                      checked={checked}
                      onCheckedChange={() => togglePicked(id)}
                      aria-label={`${row.employee.last_name} ${row.employee.first_name}`}
                    />
                    <span className="min-w-0 flex-1 truncate">
                      {row.employee.last_name} {row.employee.first_name}
                    </span>
                    <span className="flex shrink-0 items-center gap-1.5">
                      {row.absenceConflictDays.length > 0 && (
                        <AlertTriangle className="h-3 w-3 text-amber-600" />
                      )}
                      {team ? (
                        <span
                          className="text-[10px]"
                          style={{ color: team.color }}
                        >
                          {team.name}
                        </span>
                      ) : (
                        <span className="text-[10px] text-muted-foreground">
                          {row.isForfaitJour ? 'Forfait' : 'Horaire'}
                        </span>
                      )}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="shrink-0 flex flex-col gap-2 border-t p-3">
          <Button
            type="button"
            variant="default"
            size="sm"
            className="w-full justify-center gap-1.5"
            disabled={nonePicked}
            onClick={handleSelectSubset}
          >
            <ListChecks className="h-4 w-4" />
            Sélectionner pour action en masse ({pickedCount})
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full justify-center border-0 bg-gradient-to-r from-pink-500 via-rose-500 to-fuchsia-500 text-white shadow-sm hover:from-pink-600 hover:via-rose-600 hover:to-fuchsia-600 hover:text-white disabled:opacity-50"
            disabled={nonePicked}
            onClick={handleFillWithAi}
          >
            <Sparkles className="mr-2 h-4 w-4" />
            Remplir par l&apos;IA ({pickedCount})
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
