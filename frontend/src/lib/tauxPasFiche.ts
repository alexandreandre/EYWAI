/**
 * Le taux de prélèvement à la source que la fiche détient, avec la même règle
 * que le moteur (`backend/app/shared/pas_taux.py`, `taux_connu`).
 *
 * Un taux se détient s'il est transmis par la DGFiP (type, identifiant ou
 * période d'origine) ou saisi case « personnalisé » cochée. Un `taux: 0` posé
 * par défaut par un formulaire n'en est pas un : le bulletin applique alors la
 * grille par défaut, calculée chaque mois sur la rémunération ([B1], 12/10/2026).
 */
export interface BlocPas {
  taux?: number | string | null;
  type_taux?: string | null;
  identifiant_taux?: string | null;
  periode?: string | null;
  is_personnalise?: boolean | null;
}

export const LIBELLE_SANS_TAUX = 'Aucun taux connu — grille par défaut appliquée';

export function tauxConnu(bloc: BlocPas | null | undefined): number | null {
  if (!bloc || bloc.taux === null || bloc.taux === undefined || bloc.taux === '') return null;
  const taux = Number(bloc.taux);
  if (!Number.isFinite(taux)) return null;
  const transmis = Boolean(
    String(bloc.type_taux ?? '').trim() ||
      String(bloc.identifiant_taux ?? '').trim() ||
      String(bloc.periode ?? '').trim(),
  );
  return transmis || bloc.is_personnalise === true ? taux : null;
}

export function formaterTaux(taux: number): string {
  return `${taux.toLocaleString('fr-FR', { maximumFractionDigits: 2 })}\u00a0%`;
}

export function libelleTauxFiche(bloc: BlocPas | null | undefined): string {
  const taux = tauxConnu(bloc);
  return taux === null ? LIBELLE_SANS_TAUX : formaterTaux(taux);
}
