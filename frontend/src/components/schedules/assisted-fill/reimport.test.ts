import { describe, expect, it } from 'vitest';

import type { CorrectionALaMain } from '@/api/calendar';
import {
  bilanReimport,
  cleJour,
  libelleBilan,
  libelleCorrection,
  libelleImportRefait,
  libelleLotPrecedent,
  libelleValeur,
  lireRefusDejaImporte,
} from './reimport';

const LOT = {
  batch_id: 'lot-ancien',
  fichier: 'S39.pdf',
  filename: 'S39.pdf',
  valide_le: '2026-10-01T16:09:46+00:00',
  valide_par: 'RH Démo',
  jours_ecrits: 47,
};

function correction(jour: number, partiel: Partial<CorrectionALaMain> = {}): CorrectionALaMain {
  return {
    employee_id: 'emp-1',
    annee: 2026,
    mois: 9,
    jour,
    import_precedent: { heures: 8.5, type: 'travail' },
    calendrier: { heures: 9, type: 'travail' },
    fichier: { heures: 8, type: 'travail' },
    ...partiel,
  };
}

describe('lireRefusDejaImporte', () => {
  it('reconnaît le refus « déjà importé » du serveur', () => {
    const detail = {
      code: 'deja_importe',
      message: 'déjà importé',
      fichiers: [{ filename: 'S39.pdf', lot_precedent: LOT }],
    };
    const erreur = Object.assign(new Error('Request failed with status code 409'), {
      response: { status: 409, data: { detail } },
    });
    expect(lireRefusDejaImporte(erreur)).toEqual(detail);
  });

  it('laisse passer toute autre erreur', () => {
    const phrase = Object.assign(new Error('x'), {
      response: { status: 409, data: { detail: 'Ce batch a déjà été validé.' } },
    });
    expect(lireRefusDejaImporte(phrase)).toBeNull();
    expect(lireRefusDejaImporte(new Error('réseau'))).toBeNull();
    expect(lireRefusDejaImporte(null)).toBeNull();
  });
});

describe('libelleLotPrecedent', () => {
  it('dit quand (heure de Paris), qui et combien de jours', () => {
    expect(libelleLotPrecedent(LOT)).toBe(
      'importé le 1 octobre 2026 à 18:09 par RH Démo · 47 jours écrits',
    );
  });

  it('se tait sur ce qu’il ne sait pas', () => {
    expect(libelleLotPrecedent({ batch_id: 'x', valide_le: '2026-10-01T16:09:46+00:00' })).toBe(
      'importé le 1 octobre 2026 à 18:09',
    );
    expect(libelleLotPrecedent({ batch_id: 'x', jours_ecrits: 1 })).toBe('importé · 1 jour écrit');
  });
});

describe('libelleValeur', () => {
  it('écrit les heures à la française, un type sans heures en clair, un jour vide « vide »', () => {
    expect(libelleValeur({ heures: 8.5, type: 'travail' })).toBe('8,5 h');
    expect(libelleValeur({ heures: 9, type: 'travail' })).toBe('9 h');
    expect(libelleValeur({ heures: 7.83, type: 'travail' })).toBe('7,83 h');
    expect(libelleValeur({ heures: null, type: 'arret_maladie' })).toBe('arrêt maladie');
    expect(libelleValeur({ heures: null, type: 'conges_payes' })).toBe('congé payé');
    expect(libelleValeur(null)).toBe('vide');
  });
});

describe('libelleCorrection', () => {
  it('dit ce qui a été corrigé depuis l’import', () => {
    expect(libelleCorrection(correction(15))).toBe(
      'modifié à la main depuis l’import : 8,5 h → 9 h',
    );
  });

  it('dit un jour effacé depuis l’import', () => {
    expect(libelleCorrection(correction(15, { calendrier: null }))).toBe(
      'effacé à la main depuis l’import : 8,5 h → vide',
    );
  });

  it('dit un jour saisi hors de l’import', () => {
    expect(
      libelleCorrection(
        correction(15, { import_precedent: null, calendrier: { heures: 7, type: 'travail' } }),
      ),
    ).toBe('saisi à la main hors de l’import : 7 h');
  });
});

describe('bilanReimport', () => {
  const envoyes = [15, 16, 18].map((jour) =>
    cleJour({ employee_id: 'emp-1', annee: 2026, mois: 9, jour }),
  );

  it('une correction gardée n’est pas écrite', () => {
    expect(bilanReimport(envoyes, 3, [correction(15), correction(16)])).toEqual({
      joursEcrits: 1,
      correctionsGardees: 2,
    });
  });

  it('une correction d’un salarié non enregistré ne compte pas', () => {
    expect(
      bilanReimport(envoyes, 3, [correction(15), correction(17, { employee_id: 'emp-hors-lot' })]),
    ).toEqual({ joursEcrits: 2, correctionsGardees: 1 });
  });
});

describe('libelleBilan', () => {
  it('dit combien de jours seront écrits et combien de corrections sont gardées', () => {
    expect(libelleBilan({ joursEcrits: 44, correctionsGardees: 3 })).toBe(
      '44 jours seront écrits · 3 corrections faites à la main gardées',
    );
    expect(libelleBilan({ joursEcrits: 1, correctionsGardees: 0 })).toBe(
      '1 jour sera écrit · aucune correction faite à la main à garder',
    );
  });
});

describe('libelleImportRefait', () => {
  it('confirme ce que le serveur a vraiment écrit et gardé', () => {
    expect(
      libelleImportRefait({
        committed_days: 47,
        corrections_gardees: [correction(15), correction(16), correction(17)],
      }),
    ).toBe('47 jours écrits · 3 corrections faites à la main gardées');
    expect(libelleImportRefait({ committed_days: 1 })).toBe(
      '1 jour écrit · aucune correction faite à la main n’était à garder',
    );
    expect(libelleImportRefait(null)).toBe(
      '0 jour écrit · aucune correction faite à la main n’était à garder',
    );
  });
});
