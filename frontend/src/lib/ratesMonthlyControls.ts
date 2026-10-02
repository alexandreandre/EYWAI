/** Commandes du lot mensuel des taux affichées sur la page « Suivi des taux ».

Le référentiel est commun à toutes les sociétés : seul un admin plateforme
lance, recommence ou coupe le lot (le serveur le refuse aux RH). Un RH lit
l'état du mois. */

type EtatDuMois = { enabled: boolean; showRun: boolean; showRestart: boolean };

export function commandesDuMois(
  etat: EtatDuMois,
  {
    isSyncing,
    isMonthlySyncRunning,
    peutGerer,
  }: { isSyncing: boolean; isMonthlySyncRunning: boolean; peutGerer: boolean },
): { lancer: boolean; recommencer: boolean; interrupteurActif: boolean } {
  if (!peutGerer) return { lancer: false, recommencer: false, interrupteurActif: false };
  return {
    lancer: etat.showRun && !isSyncing,
    recommencer: etat.showRestart && !isSyncing,
    interrupteurActif: !isMonthlySyncRunning,
  };
}
