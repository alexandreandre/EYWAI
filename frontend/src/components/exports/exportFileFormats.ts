import type { ExportType } from '@/api/exports';

export type ExportFileFormat = 'csv' | 'xlsx' | 'pdf';

/**
 * Exports dont l'écran laisse choisir CSV, Excel ou PDF (le PDF est l'Excel mis
 * en page par le serveur, demande d'Elsa du 17/11). Quadra et Sage sont des
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

/** Exports du mois à lire ou imprimer : le PDF d'office (Elsa, 20/11). */
const PDF_D_OFFICE = new Set<ExportType>(['journal_paie', 'od_globale', 'charges_sociales']);

/** Exports en tableau dont l'Excel est le format d'office. */
const EXCEL_D_OFFICE = new Set<ExportType>([
  'conges_absences',
  'notes_frais',
  'acomptes',
  'saisies',
  'prets_employeur',
  'paiement_organismes',
  'attestations_annexes',
  'recapitulatif_montants',
]);

/**
 * Le CSV des charges sociales n'a que le récapitulatif et le détail, pas le
 * tableau validé par caisse de l'Excel et du PDF : il n'est plus proposé.
 */
const SANS_CSV = new Set<ExportType>(['charges_sociales']);

const LIBELLES_FORMAT: Record<ExportFileFormat, string> = {
  pdf: 'PDF (.pdf)',
  xlsx: 'Excel (.xlsx)',
  csv: 'CSV (.csv)',
};

export function proposeLeChoixDuFormat(exportType: ExportType): boolean {
  return FILE_FORMAT_EXPORT_TYPES.has(exportType);
}

/** Les formats proposés, celui d'office en premier ; vide sans choix de format. */
export function formatsProposes(exportType: ExportType): { value: ExportFileFormat; label: string }[] {
  if (!proposeLeChoixDuFormat(exportType)) return [];
  const dOffice = formatParDefaut(exportType);
  const ordre: ExportFileFormat[] = [
    dOffice,
    ...((PDF_D_OFFICE.has(exportType) ? ['pdf', 'xlsx', 'csv'] : ['xlsx', 'csv', 'pdf']) as ExportFileFormat[]).filter(
      (f) => f !== dOffice,
    ),
  ];
  return ordre
    .filter((f) => !(f === 'csv' && SANS_CSV.has(exportType)))
    .map((value) => ({ value, label: LIBELLES_FORMAT[value] }));
}

export function formatParDefaut(exportType: ExportType): ExportFileFormat {
  if (PDF_D_OFFICE.has(exportType)) return 'pdf';
  if (EXCEL_D_OFFICE.has(exportType)) return 'xlsx';
  return 'csv';
}

/**
 * Exports du mois entier : la sélection de collaborateurs n'y a pas de sens
 * (une OD, un journal, des charges ou une DSN partielle seraient faux), le
 * « Périmètre collaborateur » est masqué et tout le monde est pris.
 */
const SANS_PERIMETRE = new Set<ExportType>([
  'journal_paie',
  'charges_sociales',
  'od_globale',
  'od_salaires',
  'od_charges_sociales',
  'od_pas',
  'dsn_mensuelle',
]);

export function proposeLePerimetre(exportType: ExportType): boolean {
  return !SANS_PERIMETRE.has(exportType);
}

/**
 * Nom d'un lien de téléchargement du virement : le fichier à déposer à la
 * banque et la liste à relire, plutôt que deux noms de fichiers presque
 * identiques (Elsa, 20/11). Le nom du fichier reste affiché à côté.
 */
export function libelleDuTelechargement(exportType: ExportType, nomDuFichier: string): string | null {
  if (exportType !== 'virement_salaires' && exportType !== 'virement_acomptes') return null;
  if (/_(bancaire|sepa)_/.test(nomDuFichier)) return 'Fichier pour la banque';
  return 'Liste de contrôle';
}
