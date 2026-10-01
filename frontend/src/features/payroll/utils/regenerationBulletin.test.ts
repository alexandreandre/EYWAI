import { AxiosError } from 'axios';
import { describe, expect, it, vi } from 'vitest';

import { messageRegenereNonRecharge, regenererPuisRecharger } from './regenerationBulletin';

describe('regenererPuisRecharger', () => {
  it('génération en échec : on ne recharge pas, et c’est un échec', async () => {
    const refus = new AxiosError('Network Error', 'ERR_NETWORK');
    const recharger = vi.fn();

    const issue = await regenererPuisRecharger(() => Promise.reject(refus), recharger);

    expect(issue).toEqual({ kind: 'echec', erreur: refus });
    expect(recharger).not.toHaveBeenCalled();
  });

  it('génération faite puis écran rechargé', async () => {
    const recharger = vi.fn().mockResolvedValue(undefined);

    const issue = await regenererPuisRecharger(() => Promise.resolve({ warnings: [] }), recharger);

    expect(issue).toEqual({ kind: 'regenere', reponse: { warnings: [] } });
    expect(recharger).toHaveBeenCalledOnce();
  });

  it('génération faite mais rechargement en échec : jamais présenté comme un échec de régénération', async () => {
    const coupure = new AxiosError('Network Error', 'ERR_NETWORK');

    const issue = await regenererPuisRecharger(
      () => Promise.resolve({ warnings: [] }),
      () => Promise.reject(coupure)
    );

    expect(issue).toEqual({ kind: 'regenere_non_recharge', reponse: { warnings: [] }, erreur: coupure });
  });

  it('le rechargement attend la fin de la génération', async () => {
    const ordre: string[] = [];

    await regenererPuisRecharger(
      async () => {
        await Promise.resolve();
        ordre.push('généré');
        return {};
      },
      () => {
        ordre.push('rechargé');
      }
    );

    expect(ordre).toEqual(['généré', 'rechargé']);
  });
});

describe('messageRegenereNonRecharge', () => {
  it('dit que la régénération a eu lieu et quoi faire pour voir le résultat', () => {
    const { title, description } = messageRegenereNonRecharge();

    expect(title).toMatch(/^Bulletin régénéré/);
    expect(description).toMatch(/rechargez la page/i);
    expect(`${title} ${description}`).not.toMatch(/impossible|échec/i);
  });
});
