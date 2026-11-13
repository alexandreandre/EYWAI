/** Période descriptive d'une saisie : elle voyage dans le libellé imprimé,
 * sans changer le mois de versement ni le traitement du catalogue. */
function dateFr(iso: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
  const date = new Date(`${iso}T12:00:00Z`);
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== iso) return null;
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
}

export function erreurPeriodeSaisie(debut: string, fin: string): string | null {
  if (!debut && !fin) return null;
  if (!debut || !fin) return 'Renseignez le début et la fin de la période.';
  if (!dateFr(debut) || !dateFr(fin)) return 'Les dates de la période sont invalides.';
  if (debut > fin) return 'La fin de la période doit suivre son début.';
  return null;
}

export function libelleAvecPeriode(nom: string, debut: string, fin: string): string {
  const erreur = erreurPeriodeSaisie(debut, fin);
  if (erreur) throw new Error(erreur);
  if (!debut) return nom;
  return debut === fin
    ? `${nom} du ${dateFr(debut)}`
    : `${nom} du ${dateFr(debut)} au ${dateFr(fin)}`;
}
