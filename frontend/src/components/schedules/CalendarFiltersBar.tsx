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
import { Search, LayoutList, ListTodo, Users } from 'lucide-react';
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
  /** Nombre de calendriers restant à saisir (pour le filtre d'état). */
  aSaisirCount: number;
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
  aSaisirCount,
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
            value={saisieFilter}
            onValueChange={(v) => onSaisieFilterChange(v as SaisieStatusFilter)}
          >
            <SelectTrigger className="h-9 w-fit gap-1.5 px-2.5 [&>span]:line-clamp-none">
              <SelectValue placeholder="Statut saisie" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous les statuts</SelectItem>
              <SelectItem value="a_saisir">À saisir</SelectItem>
              <SelectItem value="saisi">Saisi</SelectItem>
              <SelectItem value="saisi_avec_ecart">Écart à vérifier</SelectItem>
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

        {/* Filtre d'état : montre les calendriers restant à saisir dans le
            tableau — la sélection et les actions se font sur les lignes. */}
        {!isLoading && aSaisirCount > 0 && (
          <Button
            type="button"
            size="sm"
            variant={saisieFilter === 'a_saisir' ? 'default' : 'outline'}
            className="h-9 gap-1.5"
            aria-pressed={saisieFilter === 'a_saisir'}
            onClick={() =>
              onSaisieFilterChange(saisieFilter === 'a_saisir' ? 'all' : 'a_saisir')
            }
          >
            <ListTodo className="h-4 w-4" />À saisir ({aSaisirCount})
          </Button>
        )}
      </div>

      <p className="text-xs text-muted-foreground">
        {isLoading
          ? 'Chargement des calendriers…'
          : `${filteredCount} employé${filteredCount > 1 ? 's' : ''} affiché${
              filteredCount !== totalCount ? ` sur ${totalCount}` : ''
            }`}
      </p>
    </div>
  );
}
