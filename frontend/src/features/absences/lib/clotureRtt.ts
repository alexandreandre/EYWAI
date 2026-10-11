/**
 * La clôture des RTT solde la perte des jours non posés : elle n'a de sens
 * qu'à l'approche de la fin de période (31/12 par défaut). Avant, les jours
 * restants peuvent encore être posés.
 * Ouverte quand le serveur annonce le rappel de fin d'année, ou en décembre.
 */
export function clotureRttOuverte(rappelActif: boolean | undefined, aujourdhui: Date): boolean {
  return rappelActif === true || aujourdhui.getMonth() === 11;
}
