/**
 * Les mots des saisies du mois, écrits une seule fois : la page des primes, le
 * tableau, la fenêtre de saisie et les pastilles du bulletin disent la même chose.
 */

import { deDevant } from '@/features/payroll/utils/elision';

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

/** « octobre 2026 ». */
export function moisEnToutesLettres(year: number, month: number): string {
  return `${MOIS[month - 1] ?? ''} ${year}`.trim();
}

/** Ce que la fenêtre de saisie dit de la portée d'une saisie ouverte depuis un bulletin. */
export function phraseSaisiePonctuelle(year?: number, month?: number): string {
  if (!year || !month) return 'Cette saisie ponctuelle ne vaut que pour le mois du bulletin.';
  return `Cette saisie ponctuelle ne vaut que pour ${moisEnToutesLettres(year, month)}.`;
}

export const LIBELLE_SOUMISE_COTISATIONS = 'Soumise à cotisations';
export const LIBELLE_SOUMISE_IMPOT = "Soumise à l'impôt";

/** Pastille d'une prime du bulletin : imprimée dans le brut (soumise) ou non. */
export function pastilleSoumise(soumise: boolean): string {
  return soumise ? LIBELLE_SOUMISE_COTISATIONS : 'Non soumise à cotisations';
}

/** Sous-titre de la liste des saisies : le mois réellement affiché. */
export function sousTitreSaisies(year: number, month: number, filtreSurUnSalarie: boolean): string {
  const mois = moisEnToutesLettres(year, month);
  return filtreSurUnSalarie
    ? `Saisies ponctuelles de ce salarié pour ${mois}.`
    : `Liste de toutes les saisies ponctuelles pour ${mois}.`;
}

export type BulletinARecalculer = { employee_id: string; year: number; month: number };

function deMois(year: number, month: number): string {
  const mois = moisEnToutesLettres(year, month);
  return deDevant(mois);
}

/**
 * La phrase ajoutée au message de succès d'une saisie : quels bulletins du mois
 * deviennent « À recalculer ». `[]` : aucun bulletin, rien à dire. `null` : le
 * serveur n'a pas pu chercher, on le dit sans affirmer.
 */
export function messageBulletinsARecalculer(
  cibles: BulletinARecalculer[] | null | undefined,
  nomDe: (employeeId: string) => string,
): string | null {
  if (cibles == null) return 'Si un bulletin existe déjà pour ce mois, il est à recalculer.';
  if (cibles.length === 0) return null;
  const parMois = new Map<string, BulletinARecalculer[]>();
  for (const c of cibles) {
    const cle = `${c.year}-${c.month}`;
    parMois.set(cle, [...(parMois.get(cle) ?? []), c]);
  }
  const phrases = [...parMois.values()].map((groupe) => {
    const mois = deMois(groupe[0].year, groupe[0].month);
    if (groupe.length === 1) {
      return `Le bulletin ${mois} ${deDevant(nomDe(groupe[0].employee_id))} est à recalculer.`;
    }
    if (groupe.length > 3) return `${groupe.length} bulletins ${mois} sont à recalculer.`;
    const noms = groupe.map((c) => nomDe(c.employee_id));
    const liste = `${noms.slice(0, -1).join(', ')} et ${noms[noms.length - 1]}`;
    return `Les bulletins ${mois} ${deDevant(liste)} sont à recalculer.`;
  });
  return phrases.join(' ');
}

const HS_25_CORRIGEES = 'Heures supplémentaires (corrigées au bulletin)';
const HS_50_CORRIGEES = 'Heures supplémentaires majorées à 50 % (corrigées au bulletin)';

/**
 * Les heures sup corrigées depuis l'onglet « Corriger » du bulletin sont stockées
 * comme deux saisies à 0 € dont la quantité est en heures. Sur la page des
 * primes, on les dit pour ce qu'elles sont : des heures, pas des euros.
 */
export function heuresDeclareesDeLaSaisie(saisie: {
  name: string;
  payroll_quantity?: number | null;
}): { libelle: string; quantite: string } | null {
  const palier = saisie.name === HS_25_CORRIGEES ? 25 : saisie.name === HS_50_CORRIGEES ? 50 : null;
  if (palier === null) return null;
  const heures = String(Math.round(Number(saisie.payroll_quantity ?? 0) * 100) / 100).replace('.', ',');
  return {
    libelle: `Heures sup. corrigées au bulletin : ${heures} h à ${palier} %`,
    quantite: `${heures} h`,
  };
}
