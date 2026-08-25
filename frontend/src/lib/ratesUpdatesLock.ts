/**
 * Verrou des mises à jour de taux depuis l'écran « Suivi des taux ».
 *
 * Pourquoi : `POST /rates/sync` n'exige que le rôle RH. Un clic sur « Mise à
 * jour complète » lance tout le scraping — ça consomme les crédits OpenRouter
 * et ça écrit directement les taux non critiques. Tant que le déclenchement
 * n'est pas passé côté serveur (cron mensuel du lot « Taux »), personne ne doit
 * pouvoir le lancer depuis l'interface.
 *
 * Ce verrou ne couvre QUE les boutons. Le déclenchement automatique du 1er du
 * mois (le `useEffect` de la page) reste actif volontairement : c'est
 * aujourd'hui le seul mécanisme qui rafraîchit les taux. Pour le couper aussi,
 * c'est l'interrupteur « Mise à jour automatique le 1er du mois » de la page.
 *
 * Pour lever le verrou : passer la constante à `false`.
 */
export const RATES_UPDATES_LOCKED = true;

/** Affiché en infobulle sur chaque bouton désactivé. */
export const RATES_UPDATES_LOCK_REASON =
  'Mise à jour désactivée : le déclenchement passe côté serveur.';
