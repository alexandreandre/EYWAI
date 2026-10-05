import { describe, expect, it } from 'vitest';

import type { BulletinPourRevue, LigneDuMois } from './revueDuMois';
import {
  estPretAValider,
  libelleBoutonValider,
  resumeValidationGroupee,
} from './validationGroupee';

function bulletin(overrides: Partial<BulletinPourRevue> = {}): BulletinPourRevue {
  return {
    year: 2026,
    month: 9,
    salaire_brut: 2000,
    net_a_payer: 1500,
    heures_sup: 0,
    status: 'brouillon',
    origine: 'calcule',
    a_recalculer: false,
    warnings: [],
    ...overrides,
  };
}

const PRET: LigneDuMois = { statut: 'success', bulletin: bulletin(), ecart: { fort: false } };

describe('estPretAValider — rien à revoir, pas encore validé', () => {
  it('un bulletin généré, à jour, sans alerte ni écart fort est prêt', () => {
    expect(estPretAValider(PRET)).toBe(true);
  });

  it('jamais un bulletin « À recalculer »', () => {
    expect(estPretAValider({ ...PRET, bulletin: bulletin({ a_recalculer: true }) })).toBe(false);
  });

  it('jamais un bulletin en alerte ou à net négatif', () => {
    expect(estPretAValider({ ...PRET, alertes: ['Classification manquante.'] })).toBe(false);
    expect(estPretAValider({ ...PRET, bulletin: bulletin({ net_a_payer: -12 }) })).toBe(false);
  });

  it('pas un bulletin en écart fort : il se revoit avant', () => {
    expect(estPretAValider({ ...PRET, ecart: { fort: true } })).toBe(false);
  });

  it('ni un bulletin déjà validé, ni un bulletin repris de l’ancien logiciel', () => {
    expect(estPretAValider({ ...PRET, bulletin: bulletin({ status: 'valide' }) })).toBe(false);
    expect(estPretAValider({ ...PRET, bulletin: bulletin({ origine: 'importe' }) })).toBe(false);
  });

  it('ni une ligne sans bulletin, en échec ou en cours de génération', () => {
    expect(estPretAValider({ statut: 'idle' })).toBe(false);
    expect(estPretAValider({ statut: 'error' })).toBe(false);
    expect(estPretAValider({ statut: 'loading', bulletin: bulletin() })).toBe(false);
  });
});

describe('libelleBoutonValider', () => {
  it('dit combien de bulletins sont prêts', () => {
    expect(libelleBoutonValider(22)).toBe('Valider les bulletins prêts (22)');
  });
});

describe('resumeValidationGroupee — un succès se confirme, un refus dit où corriger', () => {
  const noms = { 'ps-1': 'Jeanne Essai', 'ps-2': 'Paul Essai', 'ps-3': 'Lou Essai' };

  it('tout validé', () => {
    expect(resumeValidationGroupee({ valides: ['ps-1', 'ps-2'], refus: [] }, noms)).toEqual({
      titre: '2 bulletins validés.',
      refus: [],
    });
    expect(resumeValidationGroupee({ valides: ['ps-1'], refus: [] }, noms).titre).toBe(
      '1 bulletin validé.'
    );
  });

  it('des refus, nommés avec leur raison et leur bulletin', () => {
    const resume = resumeValidationGroupee(
      {
        valides: ['ps-1'],
        refus: [{ payslip_id: 'ps-2', raison: 'Alerte à acquitter dans le bulletin : net +14 %.' }],
      },
      noms
    );
    expect(resume.titre).toBe('1 bulletin validé, 1 refusé : ouvrez-le pour corriger.');
    expect(resume.refus).toEqual([
      {
        payslipId: 'ps-2',
        nom: 'Paul Essai',
        raison: 'Alerte à acquitter dans le bulletin : net +14 %.',
      },
    ]);
  });

  it('rien validé', () => {
    const resume = resumeValidationGroupee(
      {
        valides: [],
        refus: [
          { payslip_id: 'ps-2', raison: 'La mutuelle a changé.' },
          { payslip_id: 'inconnu', raison: 'Bulletin introuvable.' },
        ],
      },
      noms
    );
    expect(resume.titre).toBe('Aucun bulletin validé, 2 refusés : ouvrez-les pour corriger.');
    expect(resume.refus[1]?.nom).toBe('Bulletin inconnu');
  });
});
