export type SaisieStatusFilter =
  | 'all'
  | 'a_saisir'
  | 'saisi'
  | 'saisi_avec_ecart';

/** Libellés utilisateur des statuts de saisie (filtres et bandeaux). */
export const SAISIE_FILTER_LABELS: Record<
  Exclude<SaisieStatusFilter, 'all'>,
  string
> = {
  a_saisir: 'à saisir',
  saisi: 'saisis',
  saisi_avec_ecart: 'écarts à vérifier',
};

export type ModeFilter = 'all' | 'horaire' | 'forfait_jour';

export type ViewMode = 'list' | 'team';

export type SortKey =
  | 'name'
  | 'team'
  | 'status'
  | 'heures_prevues'
  | 'heures_faites'
  | 'ecart';

export type SortDir = 'asc' | 'desc';

export interface DayConfig {
  type: 'travail' | 'weekend' | 'conge' | 'ferie' | 'arret_maladie';
  hours: number;
}

export interface WeekConfig {
  monday: DayConfig;
  tuesday: DayConfig;
  wednesday: DayConfig;
  thursday: DayConfig;
  friday: DayConfig;
  saturday: DayConfig;
  sunday: DayConfig;
}

export type WeekNumber = 1 | 2 | 3 | 4 | 5;
