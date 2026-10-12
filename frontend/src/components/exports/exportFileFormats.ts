import type { ExportType } from '@/api/exports';

/**
 * Exports dont l'écran laisse choisir CSV ou Excel. Quadra et Sage sont des
 * fichiers texte (ASCII à largeur fixe, lignes à « | ») : un nom en « .xlsx »
 * ne s'ouvrirait pas, ils n'ont donc pas de choix de format.
 */
const FILE_FORMAT_EXPORT_TYPES = new Set<ExportType>([
  'journal_paie',
  'charges_sociales',
  'conges_absences',
  'provision_cp',
  'notes_frais',
  'recapitulatif_montants',
  'od_salaires',
  'od_charges_sociales',
  'od_pas',
  'od_globale',
  'export_cabinet_generique',
  'acomptes',
  'saisies',
  'prets_employeur',
  'paiement_organismes',
  'attestations_annexes',
]);

export function proposeLeChoixDuFormat(exportType: ExportType): boolean {
  return FILE_FORMAT_EXPORT_TYPES.has(exportType);
}
