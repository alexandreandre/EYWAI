/**
 * Bascule de reprise vue du calendrier (retour d'Elsa, LEWIS, septembre 2026 :
 * « Reste à compléter : 25 calendriers sur 40 » comptait les jours payés par
 * l'ancien logiciel). Le premier mois calculé par Martine se lit sur la
 * reprise de la société (`company_payroll_takeover`, déjà exposée) ; sa paie
 * commence au début de sa fenêtre des variables (21/09 pour octobre). Avant ce
 * jour, rien n'est attendu au calendrier. Aucun réglage nouveau.
 */
import type { ReprisePaie } from '@/features/dsn-import/lib/bascule';
import { phraseAvantBascule } from '@/lib/joursHorsContrat';

export interface BasculeDuMois {
  /** Premier jour de la première paie Martine (ISO). */
  debutMartine: string;
  logiciel: string | null;
  /** « Jours avant le 21/09/2026 : payés par l’ancien logiciel (Quadra), non comptés. » */
  phrase: string;
}

function rang(year: number, month: number): number {
  return year * 12 + month;
}

/**
 * La bascule qui retire des jours du mois affiché, ou `null` quand le mois est
 * entièrement payé par Martine (ou sans reprise). `lireFenetre` : la fenêtre des
 * variables d'un mois (API) ; illisible, la paie Martine part du 1er du premier
 * mois calculé.
 */
export async function debutDeLaPaieMartine(
  reprise: ReprisePaie | null | undefined,
  year: number,
  month: number,
  lireFenetre: (year: number, month: number) => Promise<{ debut: string }>,
): Promise<BasculeDuMois | null> {
  const premier = reprise?.premier_mois_calcule;
  if (!premier || !/^\d{4}-\d{2}$/.test(premier)) return null;
  const [annee, mois] = premier.split('-').map(Number);
  // Un mois affiché à partir du premier mois calculé est payé par Martine.
  if (rang(year, month) >= rang(annee, mois)) return null;
  const debutMartine = await lireFenetre(annee, mois)
    .then((f) => f.debut.slice(0, 10))
    .catch(() => `${premier}-01`);
  const logiciel = reprise?.logiciel_precedent?.trim() || null;
  return { debutMartine, logiciel, phrase: phraseAvantBascule(debutMartine, logiciel) };
}
