import { moisDePaieParDefaut } from './payrollMonth';

export type VuePaie = 'employee' | 'month';

export type ParamsVuePaie = {
  view: VuePaie;
  year: number | null;
  month: number | null;
  /** « Seulement à revoir » (?revue=1). */
  aRevoir: boolean;
};

function searchParams(search: string | URLSearchParams): URLSearchParams {
  if (typeof search !== 'string') return search;
  const trimmed = search.startsWith('?') ? search.slice(1) : search;
  return new URLSearchParams(trimmed);
}

/** Relit la recherche à chaque appel : l’onglet n’est pas figé au premier rendu. */
export function lireParamsVuePaie(search: string | URLSearchParams): ParamsVuePaie {
  const params = searchParams(search);
  const view: VuePaie = params.get('view') === 'month' ? 'month' : 'employee';
  const aRevoir = params.get('revue') === '1';
  const raw = params.get('month');
  if (!raw) return { view, year: null, month: null, aRevoir };
  const [annee, mois] = raw.split('-');
  const year = parseInt(annee ?? '', 10);
  const month = parseInt(mois ?? '', 10);
  return {
    view,
    year: Number.isFinite(year) && year > 2000 ? year : null,
    month: month >= 1 && month <= 12 ? month : null,
    aRevoir,
  };
}

/**
 * Le mois choisi, écrit dans l'adresse : le retour d'un bulletin (navigate(-1))
 * revient au même mois (revue du 05/10 : il revenait au mois courant).
 */
export function avecMois(prev: URLSearchParams, year: number, month: number): URLSearchParams {
  const next = new URLSearchParams(prev);
  next.set('month', `${year}-${String(month).padStart(2, '0')}`);
  return next;
}

export function avecRevue(prev: URLSearchParams, actif: boolean): URLSearchParams {
  const next = new URLSearchParams(prev);
  if (actif) next.set('revue', '1');
  else next.delete('revue');
  return next;
}

/**
 * Le mois affiché : celui de l'adresse, sinon le mois de paie (jusqu'au 15, le
 * mois précédent), comme les Saisies, le mode groupé et le tableau de bord.
 */
export function moisAffiche(params: ParamsVuePaie, maintenant: Date): { year: number; month: number } {
  if (params.year != null && params.month != null) return { year: params.year, month: params.month };
  return moisDePaieParDefaut(maintenant);
}
