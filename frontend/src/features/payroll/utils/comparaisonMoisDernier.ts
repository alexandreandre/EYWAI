/**
 * Section « Ce qui a changé par rapport au mois dernier ».
 *
 * Le front n'invente aucun montant : il affiche le texte fourni par le serveur,
 * ou « Pas de bulletin le mois dernier ».
 */

export const TEXTE_PAS_DE_BULLETIN = 'Pas de bulletin le mois dernier';

export type PaireMontant = {
  avant: number;
  apres: number;
};

export type ComparaisonMoisDernier = {
  present?: boolean;
  texte?: string | null;
  brut?: PaireMontant | null;
  net?: PaireMontant | null;
  heures_sup?: PaireMontant | null;
  absences?: PaireMontant | null;
};

export function messageComparaisonMoisDernier(
  comparaison: ComparaisonMoisDernier | null | undefined
): string {
  if (!comparaison || comparaison.present === false) {
    return TEXTE_PAS_DE_BULLETIN;
  }
  const texte = typeof comparaison.texte === 'string' ? comparaison.texte.trim() : '';
  return texte.length > 0 ? texte : TEXTE_PAS_DE_BULLETIN;
}

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

function moisEnToutesLettres(mois: number, annee: number): string {
  return `${MOIS[mois - 1] ?? mois} ${annee}`;
}

/**
 * Deux comparaisons, deux références : « Ce qui a changé » prend le bulletin du
 * mois civil précédent, validé ou non ; l'onglet « Comparaison N-1 » prend le
 * dernier bulletin validé. Chaque titre nomme la sienne.
 */
export function titreComparaisonMoisDernier(
  annee: number | null | undefined,
  mois: number | null | undefined
): string {
  const debut = 'Ce qui a changé par rapport';
  if (!annee || !mois) return `${debut} au mois civil précédent (bulletin validé ou non)`;
  const precedent = mois === 1 ? { annee: annee - 1, mois: 12 } : { annee, mois: mois - 1 };
  return `${debut} à ${moisEnToutesLettres(precedent.mois, precedent.annee)} (bulletin validé ou non)`;
}

export function sousTitreComparaisonValidee(
  mois: number | null | undefined,
  annee: number | null | undefined,
  moisPrecedentRepris = false
): string {
  if (!mois || !annee) {
    return moisPrecedentRepris
      ? 'Analyse automatique par rapport au dernier bulletin calculé par Martine, qui n’existe pas encore.'
      : 'Analyse automatique par rapport au dernier bulletin validé, qui n’existe pas encore.';
  }
  return `Analyse automatique par rapport au dernier bulletin validé : ${moisEnToutesLettres(mois, annee)}.`;
}

export const MESSAGE_AUCUN_BULLETIN_VALIDE =
  'Aucun bulletin validé avant ce mois : la comparaison n’est pas possible pour ce salarié. « Ce qui a changé », dans l’onglet Bulletin, compare au bulletin du mois civil précédent, validé ou non.';

/**
 * Mois précédent repris de l'ancien logiciel (Zone 404, 20/11) : le serveur le
 * dit dans R12 (« Septembre vient de l'ancien logiciel : pas de comparaison du
 * net. »). On le reconnaît à ce texte, puisque R12 n'a pas de champ dédié.
 */
export function messageMoisRepris(
  alertes: Array<{ rule_id: string; message: string }>
): string | null {
  const r12 = alertes.find((a) => a.rule_id === 'R12');
  return r12 && /vient de l.ancien logiciel/.test(r12.message) ? r12.message : null;
}

/** L'encadré « pas de comparaison » : la vraie raison quand le mois précédent est repris. */
export function messageSansBulletinDeReference(
  alertes: Array<{ rule_id: string; message: string }>
): string {
  const repris = messageMoisRepris(alertes);
  if (!repris) return MESSAGE_AUCUN_BULLETIN_VALIDE;
  return `${repris} « Ce qui a changé », dans l’onglet Bulletin, compare au bulletin du mois civil précédent, validé ou non.`;
}
