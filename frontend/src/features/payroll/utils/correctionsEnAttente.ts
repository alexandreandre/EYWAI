/**
 * Une correction faite à la main qui ne trouve plus sa ligne bloque la
 * validation du bulletin. La ligne du salarié dans la liste du mois le dit,
 * comme la liste de contrôle (jeu du 23/10).
 */
export function messageCorrectionsEnAttente(nombre: number | null | undefined): string | null {
  if (!nombre || nombre <= 0) return null;
  return nombre === 1
    ? '1 correction ne trouve plus sa ligne : réglez-la dans l’onglet « Corriger » avant de valider.'
    : `${nombre} corrections ne trouvent plus leur ligne : réglez-les dans l’onglet « Corriger » avant de valider.`;
}
