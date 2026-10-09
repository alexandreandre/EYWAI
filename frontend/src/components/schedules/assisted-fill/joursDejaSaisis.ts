/**
 * Heures réelles déjà saisies que l'import va remplacer (retour du 09/10/2026 :
 * 7 h les 5 et 6 octobre passées à 6 h sans que la revue l'annonce). La règle
 * ne change pas — l'import remplace toujours —, elle est dite avant
 * « Enregistrer » et redite dans le message de fin.
 */

export interface JourImporte {
  jour: number;
  heures: number | null;
  nature: 'prevu' | 'reel';
  annee: number;
  mois: number;
}

export interface LigneAvecJours {
  nom: string;
  employeeId: string | null;
  enregistrable: boolean;
  jours: JourImporte[];
}

/** Heures réelles déjà saisies : salarié → (jour `AAAA-MM-JJ` → heures). */
export type HeuresDejaSaisies = Record<string, Record<string, number | null>>;

export interface JoursRemplacesSalarie {
  nom: string;
  jours: number;
}

const TOLERANCE = 0.01;

export function cleJourExistant(annee: number, mois: number, jour: number): string {
  return `${annee}-${String(mois).padStart(2, '0')}-${String(jour).padStart(2, '0')}`;
}

export function joursRemplaces(
  lignes: LigneAvecJours[],
  existantes: HeuresDejaSaisies,
): JoursRemplacesSalarie[] {
  const resultat: JoursRemplacesSalarie[] = [];
  for (const ligne of lignes) {
    if (!ligne.enregistrable || !ligne.employeeId) continue;
    const dejaSaisies = existantes[ligne.employeeId] ?? {};
    const n = ligne.jours.filter((j) => {
      if (j.nature !== 'reel' || j.heures == null) return false;
      const avant = dejaSaisies[cleJourExistant(j.annee, j.mois, j.jour)];
      return avant != null && avant > 0 && Math.abs(avant - j.heures) > TOLERANCE;
    }).length;
    if (n > 0) resultat.push({ nom: ligne.nom, jours: n });
  }
  return resultat;
}

const jours = (n: number) => `${n} ${n > 1 ? 'jours' : 'jour'}`;
const detail = (l: JoursRemplacesSalarie[]) => l.map((x) => `${x.nom} (${jours(x.jours)})`).join(', ');

export function phraseJoursRemplaces(l: JoursRemplacesSalarie[]): string | null {
  if (l.length === 0) return null;
  const total = l.reduce((n, x) => n + x.jours, 0);
  const sujet =
    total > 1
      ? `${total} jours déjà saisis seront remplacés par l’import`
      : '1 jour déjà saisi sera remplacé par l’import';
  return `${sujet} : ${detail(l)}.`;
}

export function suiteResultatJoursRemplaces(l: JoursRemplacesSalarie[]): string {
  return l.length === 0 ? '' : ` Jours déjà saisis remplacés : ${detail(l)}.`;
}
