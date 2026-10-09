/**
 * Formats acceptés par l'import de pointages, et ce que l'écran en dit.
 *
 * Les PDF et les photos passent par la lecture IA ; les CSV et les Excel sont
 * lus tels quels, sans IA et sans choix de semaine (les dates sont dans le fichier).
 */

/** Attribut `accept` du sélecteur de fichiers. */
export const FORMATS_ACCEPTES_ATTRIBUT = '.pdf,.jpg,.jpeg,.png,.webp,.tif,.tiff,.csv,.xlsx,.xls';

/** Ce que dit la zone de dépôt. */
export const FORMATS_ACCEPTES_LIBELLE = 'PDF, photo (JPG, PNG), CSV ou Excel (max 15 Mo)';

/** Vrai pour un CSV ou un Excel (lecture directe, sans IA). */
export function estFichierTabulaire(nom: string): boolean {
  const bas = nom.toLowerCase();
  return bas.endsWith('.csv') || bas.endsWith('.xlsx') || bas.endsWith('.xls');
}

/** « Lecture du fichier… » tant que rien n'est lu par l'IA, « Analyse IA en cours… » sinon. */
export function libelleAnalyseEnCours(fichiers: { name: string }[]): string {
  return fichiers.length > 0 && fichiers.every((f) => estFichierTabulaire(f.name))
    ? 'Lecture du fichier…'
    : 'Analyse IA en cours…';
}
