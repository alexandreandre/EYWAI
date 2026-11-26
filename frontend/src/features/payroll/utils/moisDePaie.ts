/**
 * Un seul mois de paie d'un écran à l'autre.
 *
 * Le Calendrier s'ouvrait sur le mois civil, la Paie et les Primes sur le mois de
 * paie (jusqu'au 15, le mois précédent) : le 3 novembre, Primes montrait octobre et
 * le Calendrier novembre. Ici : le mois s'écrit dans l'adresse sous une seule forme
 * (`?month=AAAA-MM`), et le dernier mois affiché est retenu pour la session, de
 * sorte qu'un écran ouvert depuis le menu reprend le mois du précédent.
 *
 * Ordre : l'adresse (un lien, un retour arrière), puis le mois retenu, puis le
 * mois de paie par défaut.
 */
import { moisDePaieParDefaut } from './payrollMonth';

export type MoisDePaie = { year: number; month: number };

const CLE_SESSION = 'martine-mois-de-paie';
/** Prévenu quand la paie en cours change : le menu et ses pastilles la suivent. */
export const EVENEMENT_MOIS_DE_PAIE = 'martine-paie-en-cours';
const CLE_PAIE_EN_COURS = 'martine-paie-en-cours';

/**
 * Un mois retenu par société : LEWIS prépare octobre pendant qu'une autre
 * société prépare novembre (Elsa, 26/11). Sans société active, la clé commune.
 */
function avecSociete(base: string): string {
  try {
    const societe = typeof window !== 'undefined' ? window.localStorage.getItem('activeCompanyId') : null;
    return societe ? `${base}:${societe}` : base;
  } catch {
    return base;
  }
}

function cleSession(): string {
  return avecSociete(CLE_SESSION);
}

function params(search: string | URLSearchParams): URLSearchParams {
  if (typeof search !== 'string') return search;
  return new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
}

function valide(year: number, month: number): MoisDePaie | null {
  return Number.isInteger(year) && year > 2000 && Number.isInteger(month) && month >= 1 && month <= 12
    ? { year, month }
    : null;
}

/** `month=2026-10` ; l'ancienne forme des Primes (`year=2026&month=10`) se lit encore. */
export function moisDeLAdresse(search: string | URLSearchParams): MoisDePaie | null {
  const p = params(search);
  const brut = (p.get('month') ?? '').trim();
  const forme = /^(\d{4})-(\d{2})$/.exec(brut);
  if (forme) return valide(Number(forme[1]), Number(forme[2]));
  const annee = (p.get('year') ?? '').trim();
  if (/^\d{4}$/.test(annee) && /^\d{1,2}$/.test(brut)) return valide(Number(annee), Number(brut));
  return null;
}

/** La période « AAAA-MM » du mois, comme l'attendent les exports et la DSN. */
export function periodeDuMois(mois: MoisDePaie): string {
  return `${mois.year}-${String(mois.month).padStart(2, '0')}`;
}

/** Le mois écrit dans l'adresse, sous la forme unique ; le reste de l'adresse est gardé. */
export function avecMoisDePaie(prev: URLSearchParams, mois: MoisDePaie): URLSearchParams {
  const next = new URLSearchParams(prev);
  next.delete('year');
  next.set('month', periodeDuMois(mois));
  return next;
}

/** Un lien vers un autre écran, qui emporte le mois. */
export function lienAvecMois(chemin: string, mois: MoisDePaie): string {
  const [base, recherche = ''] = chemin.split('?');
  return `${base}?${avecMoisDePaie(new URLSearchParams(recherche), mois).toString()}`;
}

function session(): Storage | null {
  try {
    return typeof window !== 'undefined' ? window.sessionStorage : null;
  } catch {
    return null;
  }
}

/** Le dernier mois de paie affiché dans cet onglet ; null s'il n'y en a pas. */
export function moisDePaieRetenu(stockage: Storage | null = session()): MoisDePaie | null {
  try {
    const brut = stockage?.getItem(cleSession());
    if (!brut) return null;
    const lu = JSON.parse(brut) as Partial<MoisDePaie>;
    return valide(Number(lu.year), Number(lu.month));
  } catch {
    return null;
  }
}

export function retenirMoisDePaie(mois: MoisDePaie, stockage: Storage | null = session()): void {
  try {
    stockage?.setItem(cleSession(), JSON.stringify({ year: mois.year, month: mois.month }));
  } catch {
    // Navigation privée ou stockage plein : le mois reste dans l'adresse.
  }
}

/** Le mois affiché : celui de l'adresse, sinon le mois retenu, sinon le mois de paie. */
export function moisDePaieAffiche(
  search: string | URLSearchParams,
  retenu: MoisDePaie | null,
  maintenant: Date,
): MoisDePaie {
  return moisDeLAdresse(search) ?? retenu ?? moisDePaieParDefaut(maintenant);
}

export function memeMois(a: MoisDePaie | null | undefined, b: MoisDePaie | null | undefined): boolean {
  return Boolean(a && b && a.year === b.year && a.month === b.month);
}

/** Le stockage qui survit à l'onglet : la paie en cours tient d'un jour à l'autre. */
function durable(): Storage | null {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null;
  } catch {
    return null;
  }
}

/**
 * La paie en cours de la société : le mois CHOISI dans « Générer la Paie »,
 * pas un mois seulement consulté. Le menu (pastille des calendriers) et le
 * verrou « Lancer la paie » la suivent (Elsa, 26/11 : LEWIS en est à octobre,
 * le menu comptait novembre). Hors de la fenêtre proposée (12 mois avant, 2
 * après le mois de paie par défaut), on revient au mois par défaut.
 */
export function paieEnCours(maintenant: Date, stockage: Storage | null = durable()): MoisDePaie {
  const defaut = moisDePaieParDefaut(maintenant);
  try {
    const brut = stockage?.getItem(avecSociete(CLE_PAIE_EN_COURS));
    if (!brut) return defaut;
    const lu = JSON.parse(brut) as Partial<MoisDePaie>;
    const m = valide(Number(lu.year), Number(lu.month));
    if (!m) return defaut;
    const ecart = (m.year - defaut.year) * 12 + (m.month - defaut.month);
    return ecart >= -12 && ecart <= 2 ? m : defaut;
  } catch {
    return defaut;
  }
}

export function choisirPaieEnCours(mois: MoisDePaie, stockage: Storage | null = durable()): void {
  try {
    const cle = avecSociete(CLE_PAIE_EN_COURS);
    const valeur = JSON.stringify({ year: mois.year, month: mois.month });
    if (stockage?.getItem(cle) === valeur) return;
    stockage?.setItem(cle, valeur);
    if (typeof window !== 'undefined') window.dispatchEvent(new Event(EVENEMENT_MOIS_DE_PAIE));
  } catch {
    // Stockage indisponible : la paie en cours reste celle par défaut.
  }
}
