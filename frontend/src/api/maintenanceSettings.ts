import apiClient from '@/api/apiClient';

export type SubrogationMode = 'when_maintien' | 'automatic' | 'at_mp_only' | 'per_case' | 'never';

/** Barème de la convention (conception du 24/10/2026). */
export type BaremeConvention = 'plasturgie_0292';

export interface MaintenanceSettings {
  id: string | null;
  company_id: string;
  apply_legal_maintenance: boolean;
  min_seniority_months: number;
  min_seniority_months_at_mp: number;
  employer_waiting_days: number;
  remove_employer_waiting: boolean;
  annual_unique_waiting: boolean;
  maintain_100_percent: boolean;
  differentiated_at_illness: boolean;
  no_seniority_condition: boolean;
  custom_duration_days: number | null;
  subrogation_mode: SubrogationMode;
  provident_relay_days: number | null;
  provident_maintenance_rate: number | null;
  provident_cadre_only: boolean;
  /** Jours de carence payés par l'employeur par année civile (plasturgie : 3). */
  paid_waiting_days_per_year: number | null;
  paid_waiting_min_seniority_months: number;
  /** Maintien en jours ouvrés : 7 h + heures sup structurelles, IJSS hors bulletin. */
  maintain_working_days: boolean;
  /** Maintien à 100 % pendant les congés de maternité, de paternité et
   * d'adoption (convention) ; éteint par défaut. */
  maintain_parental_leave: boolean;
  /** Arrêt sans subrogation : true, Martine ne verse que le complément (IJSS des
   * jours maintenus déduites) ; false, le salaire garanti en entier. */
  deduire_ijss_sans_subrogation: boolean;
  /** Barème de la convention : null, les réglages manuels ; sinon les paliers du
   * barème, et les champs qu'il remplace disparaissent de l'écran. */
  bareme_convention: BaremeConvention | null;
  created_at: string | null;
  updated_at: string | null;
}

export type MaintenanceSettingsUpdate = Partial<
  Omit<MaintenanceSettings, 'id' | 'company_id' | 'created_at' | 'updated_at'>
>;

export async function getMaintenanceSettings(): Promise<MaintenanceSettings> {
  const response = await apiClient.get<MaintenanceSettings>('/api/maintenance-settings/');
  return response.data;
}

/** Un barème tel que l'écran le montre, construit par le serveur depuis le moteur. */
export interface BaremeLisible {
  code: BaremeConvention;
  libelle: string;
  sources: { titre: string; url: string }[];
  categories: {
    titre: string;
    lignes: { anciennete: string; paliers: string; limite: string }[];
    notes: string[];
  }[];
  regles: string[];
}

export async function getBaremesMaintien(): Promise<BaremeLisible[]> {
  const response = await apiClient.get<BaremeLisible[]>('/api/maintenance-settings/baremes');
  return response.data;
}

export async function saveMaintenanceSettings(
  data: MaintenanceSettingsUpdate
): Promise<MaintenanceSettings> {
  const response = await apiClient.put<MaintenanceSettings>('/api/maintenance-settings/', data);
  return response.data;
}
