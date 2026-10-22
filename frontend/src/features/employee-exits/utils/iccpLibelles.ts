/**
 * Détail de l'indemnité compensatrice de congés du dossier de départ. Son
 * estimation suit la règle du bulletin de sortie : par période de référence,
 * sur les jours restants, le plus favorable du dixième et du maintien.
 * « L1243-8 » est l'article de la prime de précarité, pas des congés.
 */

export function libelleMethodeIccp(methode: string | undefined): string {
  switch (methode) {
    case 'par_periode':
      return 'Par période, le plus favorable';
    case 'maintien':
      return 'Maintien de salaire';
    case 'dixieme':
      return 'Règle du 1/10e';
    case 'dixieme_global':
    case 'l1243_8': // dossiers calculés avant le 11/10/2026
      return '1/10e de la rémunération du contrat';
    default:
      return '—';
  }
}

export interface PeriodeIccp {
  libelle?: string;
  restants?: number | null;
  droits?: number | null;
  dixieme?: number | null;
  maintien?: number | null;
  retenu?: number | null;
  methode?: string;
}

function euros(valeur: number | null | undefined): string {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })
    .format(valeur ?? 0)
    .replace(/[\u202F\u00A0]/g, ' ');
}

function jours(valeur: number | null | undefined): string {
  return String(Math.round((valeur ?? 0) * 100) / 100).replace('.', ',');
}

/** Une ligne lisible par période de référence. */
export function lignesDesPeriodes(details: { periodes?: PeriodeIccp[] | null } | null | undefined): string[] {
  return (details?.periodes ?? []).map((p) => {
    const tete = `Période ${p.libelle ?? ''} : ${jours(p.restants)} j restants sur ${jours(p.droits)}`;
    const corps =
      p.dixieme == null
        ? `rémunération inconnue, maintien ${euros(p.maintien)}`
        : `1/10e ${euros(p.dixieme)} ou maintien ${euros(p.maintien)}`;
    return `${tete} — ${corps} → ${euros(p.retenu)}`;
  });
}
