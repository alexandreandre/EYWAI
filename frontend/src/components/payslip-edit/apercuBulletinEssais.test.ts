import { describe, expect, it } from 'vitest';

import { chargerApercu, MESSAGE_APERCU_INDISPONIBLE, MESSAGE_BULLETIN_DISPARU } from './apercuBulletin';

/**
 * « Aperçu indisponible pour le moment » apparaissait par intermittence
 * (tournage B.1-B.4, 19/10) et « Rafraîchir l'aperçu » le faisait revenir :
 * un échec passager se réessaie seul ; un échec qui dure dit quoi faire.
 */
const sansAttente = async () => {};
const erreurHttp = (status: number) => Object.assign(new Error(`HTTP ${status}`), { response: { status } });

describe("l'aperçu du bulletin réessaie seul un échec passager", () => {
  it('un échec puis un succès : l’aperçu arrive, sans message', async () => {
    let appels = 0;
    const lire = async () => {
      appels += 1;
      if (appels === 1) throw erreurHttp(500);
      return '<p>bulletin</p>';
    };
    expect(await chargerApercu(lire, { attendre: sansAttente })).toEqual({ html: '<p>bulletin</p>' });
    expect(appels).toBe(2);
  });

  it('trois échecs : un message qui dit quoi faire', async () => {
    let appels = 0;
    const lire = async () => {
      appels += 1;
      throw new Error('Network Error');
    };
    expect(await chargerApercu(lire, { attendre: sansAttente })).toEqual({ erreur: MESSAGE_APERCU_INDISPONIBLE });
    expect(appels).toBe(3);
    expect(MESSAGE_APERCU_INDISPONIBLE).toContain('Rafraîchir l’aperçu');
    expect(MESSAGE_APERCU_INDISPONIBLE).toContain('rechargez la page');
  });

  it('un bulletin disparu (404) ne se réessaie pas et le dit', async () => {
    let appels = 0;
    const lire = async () => {
      appels += 1;
      throw erreurHttp(404);
    };
    expect(await chargerApercu(lire, { attendre: sansAttente })).toEqual({ erreur: MESSAGE_BULLETIN_DISPARU });
    expect(appels).toBe(1);
  });
});
