import {
  isNetSuperieurBrutWarning,
  normalizePayslipWarning,
} from '@/lib/payslipNetBrutAlert';

/**
 * Ce que la ligne d'un bulletin dit de ses alertes : toutes, dans l'ordre,
 * séparées par « · ». « Net > Brut » a son étiquette à côté du nom : il n'est
 * pas répété ici.
 */
export function motifsDesAlertes(warnings: readonly string[]): string {
  return warnings
    .filter((w) => !isNetSuperieurBrutWarning(w))
    .map(normalizePayslipWarning)
    .join(' · ');
}
