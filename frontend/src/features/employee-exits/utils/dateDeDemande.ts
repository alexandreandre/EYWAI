/**
 * La « Date de demande/notification » proposée à la création d'un départ.
 *
 * La date du jour, plafonnée au dernier jour travaillé quand il est déjà passé :
 * la base impose, pour tout départ, une demande au plus tard le dernier jour
 * (contrainte employee_exits_check). Une fin de CDD au 15/10 créée le 20/10
 * propose donc le 15/10 ; lui proposer le 20/10 faisait échouer
 * l'enregistrement en 502 (tournage H.1, 20/10/2026).
 */

/** La date du jour au format AAAA-MM-JJ, dans le fuseau de l'écran. */
export function aujourdhuiLocal(maintenant: Date = new Date()): string {
  const mois = String(maintenant.getMonth() + 1).padStart(2, '0');
  const jour = String(maintenant.getDate()).padStart(2, '0');
  return `${maintenant.getFullYear()}-${mois}-${jour}`;
}

export function dateDeDemandeProposee({
  aujourdHui,
  dernierJour,
}: {
  aujourdHui: string;
  dernierJour: string | undefined;
}): string {
  if (dernierJour && dernierJour < aujourdHui) {
    return dernierJour;
  }
  return aujourdHui;
}
