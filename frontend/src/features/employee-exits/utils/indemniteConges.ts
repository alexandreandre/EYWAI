/**
 * Onglet « Indemnités » d'un départ. Le calcul du dossier est une estimation
 * faite à l'ouverture ; dès que le bulletin du mois de sortie existe, c'est lui
 * qui a été payé, et c'est son indemnité de congés que reprennent le reçu,
 * l'attestation France Travail et la DSN. L'onglet montre donc la même.
 */

export type BulletinDeSortieConges =
  | { mois: string; indemnite_conges?: number | null; calcul_conges?: string | null }
  | null
  | undefined;

export interface IndemniteCongesAffichee {
  montant: number | null;
  source: 'bulletin' | 'estimation';
  mois?: string;
  estimation?: number | null;
  /** Le calcul imprimé par le bulletin (dixième contre maintien, par période). */
  calcul?: string;
}

export function indemniteCongesAffichee(
  estimation: number | null | undefined,
  bulletin: BulletinDeSortieConges
): IndemniteCongesAffichee {
  if (bulletin && typeof bulletin.indemnite_conges === 'number') {
    return {
      montant: bulletin.indemnite_conges,
      source: 'bulletin',
      mois: bulletin.mois,
      estimation: estimation ?? null,
      ...(bulletin.calcul_conges ? { calcul: bulletin.calcul_conges } : {}),
    };
  }
  return { montant: estimation ?? null, source: 'estimation' };
}

/** Total brut des indemnités, avec l'indemnité de congés affichée. */
export function totalBrutDesIndemnites(
  totalDossier: number,
  estimationConges: number | null | undefined,
  bulletin: BulletinDeSortieConges
): number {
  const affichee = indemniteCongesAffichee(estimationConges, bulletin);
  if (affichee.source === 'estimation') return totalDossier;
  const total = totalDossier - (estimationConges ?? 0) + (affichee.montant ?? 0);
  return Math.round(total * 100) / 100;
}
