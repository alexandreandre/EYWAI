// Statuts des taux de prélèvement à la source : textes et résumés de la page.
// Le statut lui-même vient du serveur (`pas_rates/domain/model.py`).

import type { PasStatut } from '@/api/pasRates';

export const AIDE_STATUT_PAS: Record<PasStatut, string> = {
  a_jour: 'Taux transmis par la DGFiP, reçu récemment.',
  bareme:
    "La DGFiP n'a pas encore transmis de taux personnalisé : c'est le barème par défaut qui s'applique. Il ne se périme pas — le moteur le recalcule à chaque paie sur la rémunération du mois, et le taux affiché ici est celui de la dernière DSN.",
  a_rafraichir:
    "Ce taux date de plus de deux mois, ou sa période d'origine est inconnue. Déposez la dernière DSN ou le dernier compte rendu métier pour le rafraîchir.",
  manquant:
    "Aucun taux transmis par la DGFiP ni saisi : le bulletin applique la grille par défaut, calculée chaque mois sur la rémunération, en attendant le premier retour. Déposez la DSN ou le compte rendu métier qui porte son taux.",
};

const ORDRE: { statut: PasStatut; singulier: string; pluriel: string }[] = [
  { statut: 'manquant', singulier: 'manquant', pluriel: 'manquants' },
  { statut: 'a_rafraichir', singulier: 'à rafraîchir', pluriel: 'à rafraîchir' },
  { statut: 'bareme', singulier: 'au barème par défaut', pluriel: 'au barème par défaut' },
  { statut: 'a_jour', singulier: 'à jour', pluriel: 'à jour' },
];

/** « 2 manquants · 1 au barème par défaut · 3 à jour », du plus alarmant au plus rassurant. */
export function resumeCompteursPas(compteurs: Record<string, number> | null | undefined): string {
  return ORDRE.filter(({ statut }) => (compteurs?.[statut] ?? 0) > 0)
    .map(({ statut, singulier, pluriel }) => {
      const n = compteurs?.[statut] ?? 0;
      return `${n.toLocaleString('fr-FR')} ${n > 1 ? pluriel : singulier}`;
    })
    .join(' · ');
}

/**
 * La période d'origine du taux, comme la page des taux la lit : l'historique
 * daté d'abord, la date du bloc ensuite. Un enregistrement de fiche effaçait
 * cette date ; la page disait « juin 2026 » et la fiche « période inconnue ».
 */
export function periodeDuTaux(
  bloc: { periode?: string | null; taux?: number | null; type_taux?: string | null } | null | undefined,
  historique: { periode?: string | null }[] | null | undefined,
): string | null {
  const periodes = (historique ?? [])
    .map((l) => l.periode)
    .filter((p): p is string => typeof p === 'string' && p.length > 0)
    .sort();
  return periodes.at(-1) ?? bloc?.periode ?? null;
}

/**
 * D'où vient le taux, dit sur la fiche. Le crayon de la page des taux écrit un
 * type 01 : sans l'historique, un taux tapé au clavier se présentait comme
 * transmis par la DGFiP ([B2], 12/10/2026).
 */
export function origineDuTaux(
  typeTaux: string | null | undefined,
  historique: { periode?: string | null; source?: string | null }[] | null | undefined,
): string | null {
  const dernier = [...(historique ?? [])]
    .filter((l) => typeof l.periode === 'string' && l.periode)
    .sort((a, b) => String(a.periode).localeCompare(String(b.periode)))
    .at(-1);
  if (dernier?.source === 'manuel') return 'Saisie manuelle';
  if (!typeTaux) return null;
  if (typeTaux === '01') return 'Taux transmis par la DGFiP';
  if (typeTaux === '13') return 'Taux barème, en attente du taux DGFiP';
  return `Type de taux ${typeTaux}`;
}
