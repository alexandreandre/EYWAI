/**
 * La « Date de demande/notification » proposée à la création d'un départ.
 *
 * Elle reprenait le dernier jour travaillé dès qu'il était passé (une fin de
 * CDD au 15/10 créée le 20/10 proposait le 15/10), pour que l'enregistrement ne
 * soit pas refusé : la demande ne pouvait pas suivre le dernier jour. C'est vrai
 * d'un départ notifié (démission, licenciement, rupture, retraite, fin de
 * période d'essai, transfert) : la notification précède la fin. Une fin de CDD
 * n'est pas notifiée — la DSN ne déclare pas de date de notification pour les
 * motifs 031 et 081, il n'y a pas de préavis et aucune indemnité n'en dépend :
 * la date du jour est proposée, même après le dernier jour (tournage H.1, scène 4).
 */

/** Le départ se notifie avant son dernier jour : la demande ne peut pas le suivre. */
export function notificationAvantLaFin(exitType: string): boolean {
  return exitType !== 'fin_cdd';
}

/** La date du jour au format AAAA-MM-JJ, dans le fuseau de l'écran. */
export function aujourdhuiLocal(maintenant: Date = new Date()): string {
  const mois = String(maintenant.getMonth() + 1).padStart(2, '0');
  const jour = String(maintenant.getDate()).padStart(2, '0');
  return `${maintenant.getFullYear()}-${mois}-${jour}`;
}

export function dateDeDemandeProposee({
  aujourdHui,
  dernierJour,
  exitType,
}: {
  aujourdHui: string;
  dernierJour: string | undefined;
  exitType: string;
}): string {
  if (dernierJour && dernierJour < aujourdHui && notificationAvantLaFin(exitType)) {
    return dernierJour;
  }
  return aujourdHui;
}
