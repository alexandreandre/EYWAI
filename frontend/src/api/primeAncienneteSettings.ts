/**
 * API — paramètres prime d'ancienneté entreprise
 */

import apiClient from './apiClient';

export type ProrataMode = 'heures_contrat' | 'jours_forfait' | 'none';

export interface PrimeAncienneteOverrides {
  valeur_point_override?: number | null;
  min_annees_override?: number | null;
  prorata_mode_override?: ProrataMode | null;
}

export interface PrimeAncienneteCcResolved {
  idcc?: string | null;
  formule?: string | null;
  valeur_point_zone?: number | null;
  zone_libelle?: string | null;
  min_annees: number;
  statuts_exclus: string[];
  prorata_enabled: boolean;
  prorata_mode: ProrataMode;
}

export interface PrimeAncienneteSettings {
  overrides: PrimeAncienneteOverrides;
  cc_resolved: PrimeAncienneteCcResolved;
  code_postal?: string | null;
}

export type PrimeAncienneteSettingsUpdate = PrimeAncienneteOverrides;

export async function getPrimeAncienneteSettings(): Promise<PrimeAncienneteSettings> {
  const response = await apiClient.get('/api/prime-anciennete-settings/');
  return response.data;
}

export async function savePrimeAncienneteSettings(
  data: PrimeAncienneteSettingsUpdate
): Promise<PrimeAncienneteSettings> {
  const response = await apiClient.put('/api/prime-anciennete-settings/', data);
  return response.data;
}
