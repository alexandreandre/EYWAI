/**
 * Ce que la validation d'un lot de bulletins promet à la gestionnaire : le jour
 * où les salariés les verront, et jusqu'à quand ils se corrigent.
 *
 * Même règle que le serveur (backend/app/modules/payslips/domain/mise_a_disposition.py) :
 * un bulletin validé est remis à la plus tardive de deux dates, sa validation ou
 * le jour réglé par la société dans le mois suivant (`bulletins_mise_a_disposition_jour`
 * de companies.settings : 0 = dès la validation, 1 à 28, le 1er sans réglage) ; un
 * bulletin de sortie est remis à sa validation. Remis, il ne se modifie plus.
 * Les jours sont ceux de Paris.
 */

import { deDevant } from './elision';

export const CLE_MISE_A_DISPOSITION = 'bulletins_mise_a_disposition_jour';
const DES_LA_VALIDATION = 0;
const JOUR_PAR_DEFAUT = 1;
const JOUR_MAX = 28;

const MOIS = [
  'janvier',
  'février',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'août',
  'septembre',
  'octobre',
  'novembre',
  'décembre',
];

/**
 * Le jour réglé par la société, lu comme le serveur (`jour_de_mise_a_disposition`) ;
 * null quand les réglages de la société n'ont pas pu être lus.
 */
export function jourDeMiseADisposition(
  settings: Record<string, unknown> | null | undefined,
): number | null {
  if (!settings || typeof settings !== 'object') return null;
  const valeur = settings[CLE_MISE_A_DISPOSITION];
  let jour: number;
  if (typeof valeur === 'number' && Number.isFinite(valeur)) {
    jour = Math.trunc(valeur);
  } else if (typeof valeur === 'string' && /^\s*[+-]?\d+\s*$/.test(valeur)) {
    jour = Number.parseInt(valeur, 10);
  } else {
    // Absent, booléen ou illisible : le serveur prend le 1er du mois suivant.
    return JOUR_PAR_DEFAUT;
  }
  if (jour < DES_LA_VALIDATION) return JOUR_PAR_DEFAUT;
  return Math.min(jour, JOUR_MAX);
}

/** Le jour de Paris, « AAAA-MM-JJ ». */
export function dateDuJourAParis(maintenant: Date = new Date()): string {
  const parties = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Paris',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(maintenant);
  const valeur = (type: string) => parties.find((p) => p.type === type)?.value ?? '';
  return `${valeur('year')}-${valeur('month')}-${valeur('day')}`;
}

function moisSuivant(annee: number, mois: number): { annee: number; mois: number } {
  return mois === 12 ? { annee: annee + 1, mois: 1 } : { annee, mois: mois + 1 };
}

function iso(annee: number, mois: number, jour: number): string {
  return `${annee}-${String(mois).padStart(2, '0')}-${String(jour).padStart(2, '0')}`;
}

export type RemiseALaValidation =
  /** Remis plus tard : d'ici là, les bulletins se corrigent encore. */
  | { cas: 'plus_tard'; remisLe: string }
  /** Remis le jour même de la validation : visibles et figés aussitôt. */
  | { cas: 'des_maintenant' }
  /** Réglage de la société illisible : aucune date à promettre. */
  | { cas: 'inconnue' };

/** Le jour de remise d'un bulletin (hors sortie) validé aujourd'hui. */
export function remiseALaValidation(params: {
  annee: number;
  mois: number;
  /** Réglage de la société ; null s'il n'a pas pu être lu. */
  jour: number | null;
  /** Jour de la validation, à Paris, « AAAA-MM-JJ ». */
  aujourdhui: string;
}): RemiseALaValidation {
  const { annee, mois, jour, aujourdhui } = params;
  if (jour === null) return { cas: 'inconnue' };
  if (jour === DES_LA_VALIDATION) return { cas: 'des_maintenant' };
  const suivant = moisSuivant(annee, mois);
  const dateDuMois = iso(suivant.annee, suivant.mois, Math.max(jour, 1));
  // max(validation, jour du mois suivant) : déjà passé, la remise est aujourd'hui.
  return dateDuMois > aujourdhui ? { cas: 'plus_tard', remisLe: dateDuMois } : { cas: 'des_maintenant' };
}

/** « 1er décembre », « 5 janvier 2027 » : l'année se dit quand elle change. */
function jourEnClair(remisLe: string, anneeDuMois: number): string {
  const [a, m, j] = remisLe.split('-').map(Number);
  const jour = j === 1 ? '1er' : String(j);
  return `${jour} ${MOIS[m - 1]}${a !== anneeDuMois ? ` ${a}` : ''}`;
}

/** « de novembre », « d'avril », « de janvier 2027 ». */
function deMoisSuivant(annee: number, mois: number): string {
  const suivant = moisSuivant(annee, mois);
  const nom = `${MOIS[suivant.mois - 1]}${suivant.annee !== annee ? ` ${suivant.annee}` : ''}`;
  return deDevant(nom);
}

/** La phrase dite avant et après la validation de `nombre` bulletins (hors sortie). */
export function phraseRemiseALaValidation(
  remise: RemiseALaValidation,
  params: { annee: number; mois: number; nombre: number },
): string {
  const { annee, mois, nombre } = params;
  const plusieurs = nombre > 1;
  const visibles = plusieurs ? 'Visibles par les salariés' : 'Visible par le salarié';
  switch (remise.cas) {
    case 'plus_tard':
      return (
        `${visibles} le ${jourEnClair(remise.remisLe, annee)}. ` +
        `Jusque-là, vous pouvez encore ${plusieurs ? 'les' : 'le'} corriger.`
      );
    case 'des_maintenant':
      return (
        `${visibles} dès maintenant, et ${plusieurs ? 'figés' : 'figé'} : une erreur se corrigera ` +
        `sur le bulletin ${deMoisSuivant(annee, mois)}, par une régularisation.`
      );
    case 'inconnue':
      return (
        `${visibles} à la date de mise à disposition de la société (onglet « Paramètres paie ») ; ` +
        `à partir de cette date, ${plusieurs ? 'ils ne se modifient' : 'il ne se modifie'} plus.`
      );
  }
}

/** Les noms en une liste lisible : « A, B et C ». */
function enumerer(noms: readonly string[]): string {
  if (noms.length <= 1) return noms[0] ?? '';
  return `${noms.slice(0, -1).join(', ')} et ${noms[noms.length - 1]}`;
}

/** La ligne des bulletins de sortie du lot, remis dès leur validation ; null s'il n'y en a pas. */
export function ligneBulletinsDeSortie(noms: readonly string[]): string | null {
  if (noms.length === 0) return null;
  if (noms.length === 1) {
    return `Le bulletin de sortie ${deDevant(noms[0])} est visible dès sa validation, et figé.`;
  }
  return `Les bulletins de sortie ${deDevant(enumerer(noms))} sont visibles dès leur validation, et figés.`;
}

/**
 * Tout ce que la fenêtre et le message de fin disent sur la remise d'un lot :
 * la phrase des bulletins ordinaires, puis la ligne des bulletins de sortie.
 */
export function textesRemiseDuLot(params: {
  annee: number;
  mois: number;
  jour: number | null;
  aujourdhui: string;
  nombre: number;
  /** Noms des salariés dont le bulletin du lot est un bulletin de sortie. */
  sorties: readonly string[];
}): { phrase: string | null; ligneSortie: string | null } {
  const { annee, mois, jour, aujourdhui, nombre, sorties } = params;
  const ordinaires = Math.max(nombre - sorties.length, 0);
  const remise = remiseALaValidation({ annee, mois, jour, aujourdhui });
  return {
    phrase: ordinaires > 0 ? phraseRemiseALaValidation(remise, { annee, mois, nombre: ordinaires }) : null,
    ligneSortie: ligneBulletinsDeSortie(sorties),
  };
}
