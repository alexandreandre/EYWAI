export type VuePaie = 'employee' | 'month';

export type ParamsVuePaie = {
  view: VuePaie;
  year: number | null;
  month: number | null;
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
  const raw = params.get('month');
  if (!raw) return { view, year: null, month: null };
  const [annee, mois] = raw.split('-');
  const year = parseInt(annee ?? '', 10);
  const month = parseInt(mois ?? '', 10);
  return {
    view,
    year: Number.isFinite(year) && year > 2000 ? year : null,
    month: month >= 1 && month <= 12 ? month : null,
  };
}
