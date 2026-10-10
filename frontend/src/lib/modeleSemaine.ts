/**
 * Pré-remplissage du « Modèle de semaine type » d'un salarié : son prévu actuel,
 * à défaut la durée hebdomadaire de son contrat répartie sur cinq jours, à défaut
 * des cases vides. Jamais une valeur d'une autre personne ni de la société.
 */
export type ModeleSemaine = Record<number, string>;

interface JourPrevu {
  jour: number;
  type: string;
  heures_prevues?: number | null;
}

const JOURS_OUVRES = [1, 2, 3, 4, 5];

function texte(heures: number): string {
  return String(Math.round(heures * 100) / 100);
}

export function modeleSemaineDuSalarie({
  prevu,
  year,
  month,
  dureeHebdo,
  forfaitJour,
}: {
  prevu: readonly JourPrevu[];
  year: number;
  month: number;
  dureeHebdo?: number | null;
  forfaitJour: boolean;
}): ModeleSemaine {
  if (forfaitJour) return Object.fromEntries(JOURS_OUVRES.map((d) => [d, '1']));

  const parJour = new Map<number, number>();
  for (const j of prevu) {
    if (j.type !== 'travail' || !(Number(j.heures_prevues) > 0)) continue;
    const jourSemaine = new Date(year, month - 1, j.jour).getDay();
    if (jourSemaine >= 1 && jourSemaine <= 5 && !parJour.has(jourSemaine)) {
      parJour.set(jourSemaine, Number(j.heures_prevues));
    }
  }
  if (parJour.size > 0) {
    return Object.fromEntries(JOURS_OUVRES.map((d) => [d, parJour.has(d) ? texte(parJour.get(d)!) : '']));
  }
  if (typeof dureeHebdo === 'number' && dureeHebdo > 0) {
    return Object.fromEntries(JOURS_OUVRES.map((d) => [d, texte(dureeHebdo / 5)]));
  }
  return Object.fromEntries(JOURS_OUVRES.map((d) => [d, '']));
}
