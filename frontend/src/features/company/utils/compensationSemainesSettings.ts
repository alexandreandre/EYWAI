import type { CompanySettingsResponse } from '@/api/company';

/** L'option est absente des réglages tant que la société ne l'a jamais cochée : elle vaut alors faux. */
export function lireCompensationSemaines(settings: CompanySettingsResponse | undefined): boolean {
  return settings?.settings?.compensation_heures_entre_semaines === true;
}
