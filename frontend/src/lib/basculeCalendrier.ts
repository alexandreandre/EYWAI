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
 * La bascule de la société, pour tous les mois (fiche salarié) : le premier
 * jour de la première paie Martine. `null` sans reprise ou fenêtre illisible
 * (rien n'est retiré).
 */
export async function basculeDeLaSociete(
  reprise: ReprisePaie | null | undefined,
  lireFenetre: (year: number, month: number) => Promise<{ debut: string }>,
): Promise<BasculeDuMois | null> {
  const premier = reprise?.premier_mois_calcule;
  if (!premier || !/^\d{4}-\d{2}$/.test(premier)) return null;
  const [annee, mois] = premier.split('-').map(Number);
  // Fenêtre illisible : rien n'est retiré, tout le mois est jugé (règle
  // stricte, jamais un jour oublié en silence).
  const debutMartine = await lireFenetre(annee, mois)
    .then((f) => (/^\d{4}-\d{2}-\d{2}/.test(f.debut) ? f.debut.slice(0, 10) : null))
    .catch((): null => null);
  if (!debutMartine) return null;
  const logiciel = reprise?.logiciel_precedent?.trim() || null;
  return { debutMartine, logiciel, phrase: phraseAvantBascule(debutMartine, logiciel) };
}

/**
 * La bascule qui retire des jours du mois affiché, ou `null` quand le mois est
 * entièrement payé par Martine (ou sans reprise). `lireFenetre` : la fenêtre des
 * variables d'un mois (API) ; illisible, rien n'est retiré.
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
  return basculeDeLaSociete(reprise, lireFenetre);
}
