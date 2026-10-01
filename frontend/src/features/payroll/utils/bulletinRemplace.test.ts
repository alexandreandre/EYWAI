import { AxiosError } from 'axios';
import { describe, expect, it } from 'vitest';

import { GENERIC_ERROR_MESSAGE } from '@/lib/errorMessages';

import {
  MESSAGE_BULLETIN_REMPLACE,
  estBulletinIntrouvable,
  lienListeDesBulletins,
  messageBulletinNonCharge,
  messageBulletinRemplace,
} from './bulletinRemplace';

const erreurHttp = (status: number, detail?: unknown) =>
  Object.assign(new AxiosError(`Request failed with status code ${status}`), {
    response: { status, data: detail === undefined ? {} : { detail } },
  });
const coupureReseau = () => new AxiosError('Network Error', 'ERR_NETWORK');

const AUTRES_ECHECS: [string, unknown][] = [
  ['coupure réseau', coupureReseau()],
  ['session expirée (401)', erreurHttp(401)],
  ['droits (403)', erreurHttp(403, 'Permission insuffisante')],
  ['panne serveur (500)', erreurHttp(500, 'Internal Server Error')],
  ['service indisponible (503)', erreurHttp(503)],
  ['conflit (409)', erreurHttp(409)],
  ['erreur hors réseau', new Error('boom')],
];

describe('estBulletinIntrouvable', () => {
  it('seul un 404 veut dire que le bulletin n’existe plus', () => {
    expect(estBulletinIntrouvable(erreurHttp(404, 'Bulletin introuvable'))).toBe(true);
  });

  it.each(AUTRES_ECHECS)('%s : le bulletin n’est pas pour autant remplacé', (_cas, erreur) => {
    expect(estBulletinIntrouvable(erreur)).toBe(false);
  });
});

describe('messageBulletinRemplace', () => {
  it('dit que le bulletin a été remplacé et que la liste se recharge', () => {
    const message = messageBulletinRemplace();

    expect(message.title).toBe('Ce bulletin a été remplacé : rechargement…');
    expect(MESSAGE_BULLETIN_REMPLACE).toBe(message.title);
    expect(message.description).toMatch(/rouvrez-le depuis la liste/i);
  });
});

describe('messageBulletinNonCharge', () => {
  it.each(AUTRES_ECHECS)('%s : jamais « remplacé » ni « introuvable »', (_cas, erreur) => {
    const { title, description } = messageBulletinNonCharge(erreur);

    expect(`${title} ${description}`).not.toMatch(/remplacé|introuvable/i);
  });

  it.each(AUTRES_ECHECS)('%s : dit quoi faire, jamais le message générique seul', (_cas, erreur) => {
    const { description } = messageBulletinNonCharge(erreur);

    expect(description).not.toBe(GENERIC_ERROR_MESSAGE);
    expect(description).not.toMatch(/^Une erreur est survenue\.?$/);
    expect(description).toMatch(/vérifiez|reconnectez|rechargez|demandez|rouvrez/i);
  });

  it('coupure réseau : vérifier la connexion', () => {
    expect(messageBulletinNonCharge(coupureReseau()).description).toMatch(/connexion internet/);
  });

  it('droits : la société active ou un administrateur', () => {
    expect(messageBulletinNonCharge(erreurHttp(403)).description).toMatch(
      /société active|administrateur/
    );
  });

  it('un détail technique du serveur ne s’affiche jamais', () => {
    const { description } = messageBulletinNonCharge(
      erreurHttp(400, "KeyError: 'payslip_data' in queries.py")
    );

    expect(description).not.toMatch(/KeyError|\.py/);
  });
});

describe('lienListeDesBulletins', () => {
  it('ramène sur le salarié et le mois du bulletin', () => {
    expect(lienListeDesBulletins({ employee_id: 'emp-1', year: 2026, month: 9 })).toBe(
      '/payroll?employee=emp-1&month=2026-09'
    );
  });

  it('bulletin inconnu (lien ouvert directement) : la page de paie', () => {
    expect(lienListeDesBulletins(null)).toBe('/payroll');
  });
});
