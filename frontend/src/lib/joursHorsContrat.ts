/**
 * Jours du mois qui n'attendent aucune saisie parce qu'ils sont hors du champ de
 * la paie Martine : avant l'entrée du salarié (retour d'Elsa, salarié entré le
 * 05/10 dont les jours d'avant s'affichaient « à saisir » avec une alerte) et
 * avant la bascule de la société (jours payés par l'ancien logiciel : septembre
 * chez LEWIS comptait 25 calendriers « à compléter » sur 40).
 *
 * Même règle que le juge du serveur (`periode_a_saisir`, `date_entree`) : un
 * jour avant l'entrée n'est pas compté.
 */

function joursDuMois(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

/**
 * Premier jour du mois à partir d'une date ISO : `null` si la date est absente,
 * avant le mois ou le 1er (rien n'est exclu) ; le jour s'il tombe dans le mois ;
 * le nombre de jours du mois + 1 si la date est après (tout le mois est exclu).
 */
export function premierJourDansLeMois(
  iso: string | null | undefined,
  year: number,
  month: number,
): number | null {
  const date = iso?.slice(0, 10);
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  const prefixe = `${year}-${String(month).padStart(2, '0')}`;
  if (date < `${prefixe}-01`) return null;
  if (date.startsWith(prefixe)) {
    const jour = Number(date.slice(8, 10));
    return jour > 1 ? jour : null;
  }
  return joursDuMois(year, month) + 1;
}

/** Premier jour du contrat dans le mois (entrée), même lecture que le serveur : `hire_date`. */
export function premierJourDuContratDansLeMois(
  employee: { hire_date?: string | null },
  year: number,
  month: number,
): number | null {
  return premierJourDansLeMois(employee.hire_date, year, month);
}

export function estAvantLEntree(jour: number, premierJourContrat: number | null | undefined): boolean {
  return premierJourContrat != null && jour < premierJourContrat;
}

/** Infobulle d'une case avant l'entrée. */
export function libelleAvantEntree(premierJour: number, month: number): string {
  if (premierJour > 31) return 'Entrée après ce mois : hors contrat, rien à saisir.';
  const jj = `${String(premierJour).padStart(2, '0')}/${String(month).padStart(2, '0')}`;
  return `Avant l’entrée le ${jj} : hors contrat, rien à saisir.`;
}

function enFrancais(iso: string): string {
  const [annee, mois, jour] = iso.slice(0, 10).split('-');
  return `${jour}/${mois}/${annee}`;
}

/** « Jours avant le 21/09/2026 : payés par l’ancien logiciel (Quadra), non comptés. » */
export function phraseAvantBascule(debutMartine: string, logiciel?: string | null): string {
  const nom = logiciel?.trim();
  return `Jours avant le ${enFrancais(debutMartine)} : payés par l’ancien logiciel${
    nom ? ` (${nom})` : ''
  }, non comptés.`;
}
