import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it } from 'vitest';

import {
  MESSAGE_IDENTIFIANTS_INCORRECTS,
  messageEchecConnexion,
} from './messageEchecConnexion';

const config = { headers: new AxiosHeaders() };

function reponse(status: number, detail?: unknown) {
  return new AxiosError('Request failed with status code ' + status, 'ERR_BAD_REQUEST', config, null, {
    status,
    statusText: '',
    headers: {},
    config,
    data: detail === undefined ? {} : { detail },
  });
}

describe('messageEchecConnexion — une erreur de connexion distincte pour chaque cas', () => {
  it('mauvais mot de passe ou compte inconnu : le texte attendu par l’e2e', () => {
    expect(messageEchecConnexion(reponse(400, 'Identifiant ou mot de passe incorrect'))).toBe(
      MESSAGE_IDENTIFIANTS_INCORRECTS,
    );
    expect(MESSAGE_IDENTIFIANTS_INCORRECTS).toMatch(/identifiant ou mot de passe incorrect/i);
  });

  it('serveur injoignable : le mot de passe n’est pas en cause', () => {
    const coupe = new AxiosError('Network Error', 'ERR_NETWORK', config, {});
    expect(messageEchecConnexion(coupe)).toMatch(/ne répond pas.*mot de passe n’est pas en cause/);
  });

  it('service indisponible (503) ou en panne (500)', () => {
    expect(messageEchecConnexion(reponse(503))).toMatch(/momentanément indisponible.*mot de passe n’est pas en cause/);
    expect(messageEchecConnexion(reponse(500, 'Erreur interne du serveur: boom'))).toMatch(
      /rencontre un problème.*mot de passe n’est pas en cause/,
    );
  });

  it('compte sans profil Martine (après authentification)', () => {
    expect(messageEchecConnexion(reponse(404, 'Profil utilisateur non trouvé'))).toMatch(
      /pas encore ouvert dans Martine/,
    );
    expect(messageEchecConnexion(reponse(401, 'Utilisateur non trouvé'))).toMatch(/pas encore ouvert dans Martine/);
  });

  it('compte sans accès (403)', () => {
    expect(messageEchecConnexion(reponse(403, 'Compte désactivé'))).toMatch(/n’a plus accès à Martine/);
  });

  it('trop de tentatives (429)', () => {
    expect(messageEchecConnexion(reponse(429))).toMatch(/Trop de tentatives/);
  });

  it('champ manquant (422)', () => {
    expect(messageEchecConnexion(reponse(422, [{ msg: 'field required' }]))).toBe(
      'Saisissez votre identifiant et votre mot de passe.',
    );
  });

  it('session refusée juste après la connexion (401 jeton)', () => {
    expect(messageEchecConnexion(reponse(401, 'Session expirée. Veuillez vous reconnecter.'))).toMatch(
      /n’a pas pu être ouverte/,
    );
  });

  it('autre refus en clair renvoyé par le serveur : on le montre', () => {
    expect(messageEchecConnexion(reponse(400, 'Votre adresse e-mail n’est pas encore confirmée.'))).toBe(
      'Votre adresse e-mail n’est pas encore confirmée.',
    );
  });

  it('erreur inconnue : jamais muette, jamais technique', () => {
    expect(messageEchecConnexion(new TypeError('x is not a function'))).toBe(
      'La connexion n’a pas abouti. Réessayez dans quelques instants.',
    );
  });
});
