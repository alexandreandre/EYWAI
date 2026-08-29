import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { Search, LayoutList, ListFilter, Users } from 'lucide-react';
import type { Team } from '@/api/teams';
import type { ModeFilter, SaisieStatusFilter, ViewMode } from './types';

interface CalendarFiltersBarProps {
  searchQuery: string;
  onSearchChange: (q: string) => void;
  teams: Team[];
  selectedTeamIds: string[];
  onTeamIdsChange: (ids: string[]) => void;
  saisieFilter: SaisieStatusFilter;
  onSaisieFilterChange: (f: SaisieStatusFilter) => void;
  modeFilter: ModeFilter;
  onModeFilterChange: (f: ModeFilter) => void;
  viewMode: ViewMode;
  onViewModeChange: (v: ViewMode) => void;
  filteredCount: number;
  totalCount: number;
  /** Compteurs par statut de saisie (sur tout le mois, avant filtres). */
  statusCounts: { aSaisir: number; saisi: number; ecart: number };
  isLoading?: boolean;
}

export function CalendarFiltersBar({
  searchQuery,
  onSearchChange,
  teams,
  selectedTeamIds,
  onTeamIdsChange,
  saisieFilter,
  onSaisieFilterChange,
  modeFilter,
  onModeFilterChange,
  viewMode,
  onViewModeChange,
  filteredCount,
  totalCount,
  statusCounts,
  isLoading = false,
}: CalendarFiltersBarProps) {
  const teamValue =
    selectedTeamIds.length === 0
      ? 'all'
      : selectedTeamIds.length === 1
        ? selectedTeamIds[0]
        : 'multi';

  return (
    <div className="flex flex-col gap-3 py-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-center lg:gap-2">
        <div
          className="flex items-center gap-2 shrink-0"
          role="group"
          aria-label="Mode d'affichage"
        >
          <span className="text-xs font-medium text-muted-foreground whitespace-nowrap">
            Vue
          </span>
          <ToggleGroup
            type="single"
            value={viewMode}
            onValueChange={(v) => v && onViewModeChange(v as ViewMode)}
            className="border rounded-md"
          >
            <ToggleGroupItem
              value="team"
              aria-label="Vue planning équipe"
              className="gap-1.5 h-9 px-3"
            >
              <Users className="h-4 w-4" />
              <span className="text-xs">Planning</span>
            </ToggleGroupItem>
            <ToggleGroupItem
              value="list"
              aria-label="Vue liste"
              className="gap-1.5 h-9 px-3"
            >
              <LayoutList className="h-4 w-4" />
              <span className="text-xs">Liste</span>
            </ToggleGroupItem>
          </ToggleGroup>
        </div>

        <div className="relative w-full min-w-[12rem] max-w-md lg:w-64 shrink-0">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Rechercher nom, prénom, poste…"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9 h-9"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={teamValue}
            onValueChange={(v) => {
              if (v === 'all') onTeamIdsChange([]);
              else onTeamIdsChange([v]);
            }}
          >
            <SelectTrigger className="h-9 w-fit gap-1.5 px-2.5 [&>span]:line-clamp-none">
              <SelectValue placeholder="Équipe" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Toutes les équipes</SelectItem>
              {teams.map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {t.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={modeFilter}
            onValueChange={(v) => onModeFilterChange(v as ModeFilter)}
          >
            <SelectTrigger className="h-9 w-fit gap-1.5 px-2.5 [&>span]:line-clamp-none">
              <SelectValue placeholder="Mode" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous les modes</SelectItem>
              <SelectItem value="horaire">Horaire</SelectItem>
              <SelectItem value="forfait_jour">Forfait jour</SelectItem>
            </SelectContent>
          </Select>
        </div>

      </div>

      {/* Statut de saisie : sa propre ligne, toujours au même endroit —
          les segments à compteurs filtrent le tableau, l'actif est en
          surbrillance. */}
      <div
        role="group"
        aria-label="Filtrer le tableau par statut de saisie"
        className="flex w-fit max-w-full items-center gap-0.5 overflow-x-auto rounded-md border bg-muted/30 p-0.5"
      >
        <span className="flex items-center gap-1 pl-2 pr-1 text-xs font-medium text-muted-foreground whitespace-nowrap">
          <ListFilter className="h-3.5 w-3.5" />
          Filtrer :
        </span>
        {(
          [
            { value: 'all', label: 'Tous', count: totalCount },
            { value: 'a_saisir', label: 'À saisir', count: statusCounts.aSaisir },
            { value: 'saisi', label: 'Saisis', count: statusCounts.saisi },
            {
              value: 'saisi_avec_ecart',
              label: 'Écarts',
              count: statusCounts.ecart,
            },
          ] as { value: SaisieStatusFilter; label: string; count: number }[]
        ).map((opt) => (
          <Button
            key={opt.value}
            type="button"
            size="sm"
            variant={saisieFilter === opt.value ? 'default' : 'ghost'}
            className="h-8 shrink-0 gap-1 px-2.5 text-xs"
            aria-pressed={saisieFilter === opt.value}
            onClick={() => onSaisieFilterChange(opt.value)}
          >
            {opt.label}
            <span
              className={
                saisieFilter === opt.value
                  ? 'tabular-nums opacity-80'
                  : 'tabular-nums text-muted-foreground'
              }
            >
              {opt.count}
            </span>
          </Button>
        ))}
      </div>

      <p className="text-xs text-muted-foreground">
        {isLoading
          ? 'Chargement des calendriers…'
          : `${filteredCount} employé${filteredCount > 1 ? 's' : ''} affiché${
              filteredCount > 1 ? 's' : ''
            }${filteredCount !== totalCount ? ` sur ${totalCount}` : ''}`}
      </p>
    </div>
  );
}
