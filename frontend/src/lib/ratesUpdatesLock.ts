/**
 * Verrou des mises à jour de taux depuis l'écran « Suivi des taux ».
 *
 * Pourquoi : `POST /rates/sync` n'exige que le rôle RH. Un clic sur « Mise à
 * jour complète » lance tout le scraping — ça consomme les crédits OpenRouter
 * et ça écrit directement les taux non critiques. Tant que le déclenchement
 * n'est pas passé côté serveur (cron mensuel du lot « Taux »), personne ne doit
 * pouvoir le lancer depuis l'interface.
 *
 * Ce verrou ne couvre QUE les boutons de mise à jour ciblée ou complète.
 * Le lot du mois est lancé par le cron (1er au 3, matin, heure de Paris),
 * pas par l'ouverture de la page. L'interrupteur et « Réessayer » passent
 * par le même verrou serveur.
 *
 * Pour lever le verrou : passer la constante à `false`.
 */
export const RATES_UPDATES_LOCKED = true;

/** Affiché en infobulle sur chaque bouton désactivé. */
export const RATES_UPDATES_LOCK_REASON =
  'Mise à jour désactivée : le déclenchement passe côté serveur.';
