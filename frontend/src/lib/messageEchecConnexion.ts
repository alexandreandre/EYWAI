import axios from 'axios';

import { extractDetail, getApiErrorStatus, sanitizeBackendMessage } from '@/lib/errorMessages';

/**
 * Une erreur de connexion distincte pour chaque cas (revue DA du 03/11) :
 * avant, une panne du serveur disait aussi « Identifiant ou mot de passe incorrect ».
 *
 * D'après ce que l'API renvoie vraiment (`/api/auth/login` puis `/api/auth/me`) :
 * - 400 « Identifiant ou mot de passe incorrect » : mauvais mot de passe, compte
 *   inconnu, et aussi compte bloqué dans l'authentification (volontaire : un
 *   statut à part dirait qu'un compte existe) ;
 * - 403 `compte_desactive` : mot de passe juste, plus aucun accès actif ;
 * - 429 `trop_de_tentatives` : limite de l'authentification ;
 * - 401 / 404 « Utilisateur non trouvé » / « Profil utilisateur non trouvé » :
 *   authentifié, mais sans profil Martine ;
 * - 503, 5xx, ou pas de réponse : panne, le mot de passe n'est pas en cause.
 */

export const MESSAGE_IDENTIFIANTS_INCORRECTS = 'Identifiant ou mot de passe incorrect.';

const PAS_EN_CAUSE = 'Votre mot de passe n’est pas en cause.';

const MESSAGE_SERVEUR_INJOIGNABLE = `Le serveur de Martine ne répond pas. Vérifiez votre connexion internet, puis réessayez dans quelques secondes. ${PAS_EN_CAUSE}`;
const MESSAGE_INDISPONIBLE = `Martine est momentanément indisponible. Réessayez dans quelques secondes. ${PAS_EN_CAUSE}`;
const MESSAGE_PANNE = `Le service rencontre un problème. Réessayez dans quelques instants. ${PAS_EN_CAUSE}`;
const MESSAGE_SANS_PROFIL =
  'Votre identifiant est reconnu, mais votre compte n’est pas encore ouvert dans Martine. Contactez votre service RH.';
const MESSAGE_SANS_ACCES = 'Ce compte n’a plus accès à Martine. Contactez votre service RH.';
const MESSAGE_TROP_DE_TENTATIVES =
  'Trop de tentatives de connexion. Patientez quelques minutes avant de réessayer.';
const MESSAGE_CHAMPS_MANQUANTS = 'Saisissez votre identifiant et votre mot de passe.';
const MESSAGE_SESSION_REFUSEE =
  'Vos identifiants sont bons, mais la session n’a pas pu être ouverte. Réessayez dans quelques instants.';
const MESSAGE_INCONNU = 'La connexion n’a pas abouti. Réessayez dans quelques instants.';

const IDENTIFIANTS_INCORRECTS = /identifiant ou mot de passe incorrect|invalid (login )?credentials/i;
const SANS_PROFIL = /utilisateur non trouv|profil utilisateur non trouv/i;

export function messageEchecConnexion(error: unknown): string {
  if (axios.isAxiosError(error) && !error.response) return MESSAGE_SERVEUR_INJOIGNABLE;

  const status = getApiErrorStatus(error);
  const brut = extractDetail(error) ?? '';

  if (status === undefined) return MESSAGE_INCONNU;
  if (status === 503) return MESSAGE_INDISPONIBLE;
  if (status >= 500) return MESSAGE_PANNE;
  if (status === 429) return MESSAGE_TROP_DE_TENTATIVES;
  if (status === 422) return MESSAGE_CHAMPS_MANQUANTS;
  if (IDENTIFIANTS_INCORRECTS.test(brut)) return MESSAGE_IDENTIFIANTS_INCORRECTS;
  if (SANS_PROFIL.test(brut) || status === 404) return MESSAGE_SANS_PROFIL;
  if (status === 403) return MESSAGE_SANS_ACCES;
  if (status === 401) return MESSAGE_SESSION_REFUSEE;

  // Autre refus que le serveur sait dire en clair : on le montre tel quel.
  const detail = sanitizeBackendMessage(brut);
  if (detail) return detail;
  return MESSAGE_IDENTIFIANTS_INCORRECTS;
}
