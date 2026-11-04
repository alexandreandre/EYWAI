import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it } from 'vitest';

import { MESSAGE_IDENTIFIANTS_INCORRECTS, messageEchecConnexion } from './messageEchecConnexion';

/**
 * Les corps exacts que `/api/auth/login` rend depuis le 04/11 (un statut et un
 * code par cas : backend/app/modules/auth/application/service.py). Le message
 * vient de `detail.message`, comme pour les autres refus métier.
 */

const config = { headers: new AxiosHeaders() };

function refus(status: number, code: string, message: string) {
  return new AxiosError('Request failed with status code ' + status, 'ERR_BAD_REQUEST', config, null, {
    status,
    statusText: '',
    headers: {},
    config,
    data: { detail: { code, message } },
  });
}

describe('messageEchecConnexion — codes rendus par le serveur', () => {
  it('400 identifiants_incorrects (aussi compte inconnu ou bloqué)', () => {
    expect(
      messageEchecConnexion(refus(400, 'identifiants_incorrects', 'Identifiant ou mot de passe incorrect')),
    ).toBe(MESSAGE_IDENTIFIANTS_INCORRECTS);
  });

  it('403 compte_desactive', () => {
    expect(
      messageEchecConnexion(
        refus(403, 'compte_desactive', 'Ce compte n’a plus accès à Martine : ses accès ont été retirés.'),
      ),
    ).toMatch(/n’a plus accès à Martine/);
  });

  it('429 trop_de_tentatives', () => {
    expect(messageEchecConnexion(refus(429, 'trop_de_tentatives', 'Trop de tentatives.'))).toMatch(
      /Trop de tentatives/,
    );
  });

  it('503 service_indisponible et 500 connexion_impossible : le mot de passe n’est pas en cause', () => {
    expect(messageEchecConnexion(refus(503, 'service_indisponible', 'Indisponible.'))).toMatch(
      /mot de passe n’est pas en cause/,
    );
    expect(messageEchecConnexion(refus(500, 'connexion_impossible', 'Échec.'))).toMatch(
      /mot de passe n’est pas en cause/,
    );
  });

  it('400 email_non_confirmee : le message du serveur est montré', () => {
    const message = "Votre adresse e-mail n'est pas encore confirmée : ouvrez le lien d'activation reçu par e-mail, puis reconnectez-vous.";
    expect(messageEchecConnexion(refus(400, 'email_non_confirmee', message))).toMatch(/pas encore confirmée/);
  });
});
