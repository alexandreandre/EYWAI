/**
 * Verrou des mises à jour de taux depuis l'écran « Suivi des taux ».
 *
 * Pourquoi : un clic sur « Mise à jour complète » lance tout le scraping — ça
 * consomme les crédits OpenRouter et ça écrit directement les taux non
 * critiques. Le serveur réserve `POST /rates/sync` aux admins plateforme ;
 * tant que le déclenchement passe par le cron mensuel du lot « Taux »,
 * personne ne doit pouvoir le lancer depuis l'interface.
 *
 * Ce verrou ne couvre QUE les boutons de mise à jour ciblée ou complète.
 * Le lot du mois est lancé par le cron (1er au 3, matin, heure de Paris),
 * pas par l'ouverture de la page. L'interrupteur et « Réessayer » ne
 * s'affichent qu'à un admin plateforme (`commandesDuMois`), comme le serveur.
 *
 * Pour lever le verrou : passer la constante à `false`.
 */
export const RATES_UPDATES_LOCKED = true;

/** Affiché en infobulle sur chaque bouton désactivé. */
export const RATES_UPDATES_LOCK_REASON =
  'Mise à jour désactivée : le déclenchement passe côté serveur.';
