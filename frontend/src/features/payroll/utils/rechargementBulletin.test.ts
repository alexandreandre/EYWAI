import fs from 'fs';
import path from 'path';

import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it, vi } from 'vitest';

import { rechargementsDuBulletin } from './rechargementBulletin';
import { regenererPuisRecharger } from './regenerationBulletin';

function echecHttp(status: number): AxiosError {
  const config = { headers: new AxiosHeaders() };
  return new AxiosError(`Request failed with status code ${status}`, 'ERR_BAD_RESPONSE', config, null, {
    status,
    statusText: '',
    headers: {},
    config,
    data: {},
  });
}

function dependances(lire: () => Promise<{ id: string }>) {
  return {
    lire,
    appliquer: vi.fn(),
    remplace: vi.fn().mockResolvedValue(undefined),
    signalerEchec: vi.fn(),
    invaliderListes: vi.fn(),
  };
}

describe('rechargementsDuBulletin', () => {
  it('recharger : applique le bulletin relu', async () => {
    const d = dependances(() => Promise.resolve({ id: 'ps-1' }));

    await rechargementsDuBulletin(d).recharger();

    expect(d.appliquer).toHaveBeenCalledWith({ id: 'ps-1' });
    expect(d.signalerEchec).not.toHaveBeenCalled();
  });

  it('recharger : un 404 dit « remplacé », un autre échec est signalé sur place', async () => {
    const introuvable = dependances(() => Promise.reject(echecHttp(404)));
    await rechargementsDuBulletin(introuvable).recharger();
    expect(introuvable.remplace).toHaveBeenCalledOnce();
    expect(introuvable.signalerEchec).not.toHaveBeenCalled();

    const panne = echecHttp(500);
    const enPanne = dependances(() => Promise.reject(panne));
    await rechargementsDuBulletin(enPanne).recharger();
    expect(enPanne.signalerEchec).toHaveBeenCalledWith(panne);
    expect(enPanne.remplace).not.toHaveBeenCalled();
  });

  it('après régénération : un rechargement en échec remonte, jamais avalé', async () => {
    const coupure = new AxiosError('Network Error', 'ERR_NETWORK');
    const d = dependances(() => Promise.reject(coupure));

    await expect(rechargementsDuBulletin(d).apresRegeneration()).rejects.toBe(coupure);
    expect(d.signalerEchec).not.toHaveBeenCalled();
    expect(d.invaliderListes).toHaveBeenCalledOnce();
  });

  it('après régénération : un 404 dit « remplacé » sans remonter', async () => {
    const d = dependances(() => Promise.reject(echecHttp(404)));

    await expect(rechargementsDuBulletin(d).apresRegeneration()).resolves.toBeUndefined();
    expect(d.remplace).toHaveBeenCalledOnce();
  });

  it('régénération réussie, rechargement en panne : l’issue est « écran non rechargé »', async () => {
    const panne = echecHttp(503);
    const d = dependances(() => Promise.reject(panne));

    const issue = await regenererPuisRecharger(
      () => Promise.resolve({ warnings: [] }),
      rechargementsDuBulletin(d).apresRegeneration
    );

    expect(issue).toEqual({ kind: 'regenere_non_recharge', reponse: { warnings: [] }, erreur: panne });
  });

  it('sans bulletin à relire, rien n’est lu ni signalé', async () => {
    const d = { ...dependances(() => Promise.resolve({ id: 'x' })), lire: null };

    await rechargementsDuBulletin(d).apresRegeneration();
    await rechargementsDuBulletin(d).recharger();

    expect(d.appliquer).not.toHaveBeenCalled();
    expect(d.signalerEchec).not.toHaveBeenCalled();
  });
});

describe('branchement dans l’écran de correction', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '../../../pages/rh/PayslipEdit.tsx'), 'utf8');

  it('le bouton Régénérer reçoit le rechargement qui laisse remonter les échecs', () => {
    expect(source).toMatch(/onRegenerated=\{rechargements\.apresRegeneration\}/);
  });

  it('les rechargements de l’écran viennent de rechargementsDuBulletin', () => {
    expect(source).toMatch(/rechargementsDuBulletin\(/);
    expect(source).not.toMatch(/onRegenerated=\{apresChangement\}/);
  });
});
