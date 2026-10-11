/**
 * Onglet « Indemnités » d'un départ : à écrire au vert.
 */

export type BulletinDeSortieConges = { mois: string; indemnite_conges?: number | null } | null | undefined;

export interface IndemniteCongesAffichee {
  montant: number | null;
  source: 'bulletin' | 'estimation';
  mois?: string;
  estimation?: number | null;
}

export function indemniteCongesAffichee(
  estimation: number | null | undefined,
  _bulletin: BulletinDeSortieConges
): IndemniteCongesAffichee {
  return { montant: estimation ?? null, source: 'estimation' };
}

export function totalBrutDesIndemnites(
  totalDossier: number,
  _estimationConges: number | null | undefined,
  _bulletin: BulletinDeSortieConges
): number {
  return totalDossier;
}
