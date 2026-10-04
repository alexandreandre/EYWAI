import { describe, expect, it } from 'vitest';

import {
  MESSAGE_A_RECALCULER,
  MESSAGE_COMPARAISON_INDISPONIBLE,
  estPerime,
  jobsDesBulletinsPerimes,
  jobsDesLignesPerimes,
  libelleBoutonRecalculerTout,
  libelleToastRecalcul,
  messageARecalculer,
  montantsDepuisLigne,
  montantsDepuisReponse,
} from './bulletinARecalculer';

describe('estPerime', () => {
  it('seul true est à recalculer', () => {
    expect(estPerime({ a_recalculer: true })).toBe(true);
    expect(estPerime({ a_recalculer: false })).toBe(false);
    expect(estPerime({ a_recalculer: null })).toBe(false);
    expect(estPerime({})).toBe(false);
    expect(estPerime(undefined)).toBe(false);
  });

  it('un bulletin repris ne se marque pas, même si le serveur dit true', () => {
    expect(estPerime({ a_recalculer: true, origine: 'importe' })).toBe(false);
  });
});

describe('messageARecalculer', () => {
  const MUTUELLE = 'La mutuelle a changé depuis le calcul : recalculez avant de valider.';

  it('dit ce que le serveur a vu changer', () => {
    expect(messageARecalculer({ a_recalculer: true, raison_a_recalculer: MUTUELLE })).toBe(MUTUELLE);
  });

  it('le dit aussi quand le mois d’avant est à régénérer', () => {
    expect(
      messageARecalculer({
        a_recalculer: true,
        a_regenerer: 'Le bulletin du mois précédent a changé…',
        raison_a_recalculer: MUTUELLE,
      })
    ).toBe(MUTUELLE);
  });

  it('le mois d’avant seul se dit par « À régénérer »', () => {
    expect(
      messageARecalculer({
        a_recalculer: true,
        a_regenerer: 'Le bulletin du mois précédent a changé…',
        raison_a_recalculer: null,
      })
    ).toBeNull();
  });

  it('sans raison du serveur, un bulletin périmé garde le message général', () => {
    expect(messageARecalculer({ a_recalculer: true })).toBe(MESSAGE_A_RECALCULER);
    expect(messageARecalculer({ a_recalculer: false })).toBeNull();
    expect(messageARecalculer(undefined)).toBeNull();
  });

  it('un bulletin repris n’a jamais d’alerte', () => {
    expect(
      messageARecalculer({ a_recalculer: true, origine: 'importe', raison_a_recalculer: MUTUELLE })
    ).toBeNull();
  });

  it('le message général ne prétend pas savoir que c’est le calendrier', () => {
    expect(MESSAGE_A_RECALCULER).not.toMatch(/^Le calendrier ou les absences/);
    expect(MESSAGE_A_RECALCULER).toMatch(/fiche/);
  });
});

describe('jobsDesBulletinsPerimes', () => {
  const salaries = [
    { id: 'e1', first_name: 'Jeanne', last_name: 'Essai' },
    { id: 'e2', first_name: 'Paul', last_name: 'Essai' },
    { id: 'e3', first_name: 'Claire', last_name: 'Essai' },
  ];

  it('ne relance que les bulletins périmés du mois, pas les inconnus ni les repris', () => {
    const jobs = jobsDesBulletinsPerimes(
      salaries,
      {
        e1: [
          {
            year: 2026,
            month: 5,
            a_recalculer: true,
            origine: 'calcule',
            heures_sup: 2,
            salaire_brut: 1800,
            net_a_payer: 1400,
          },
        ],
        e2: [{ year: 2026, month: 5, a_recalculer: null, origine: 'calcule' }],
        e3: [{ year: 2026, month: 5, a_recalculer: true, origine: 'importe' }],
      },
      2026,
      5
    );
    expect(jobs).toEqual([
      {
        employeeId: 'e1',
        employeeName: 'Jeanne Essai',
        year: 2026,
        month: 5,
        montantsAvant: { heures_sup: 2, salaire_brut: 1800, net_a_payer: 1400 },
      },
    ]);
  });

  it('un salarié, tous ses mois périmés de l’année', () => {
    const jobs = jobsDesLignesPerimes(salaries[0], [
      { year: 2026, month: 4, a_recalculer: true, origine: 'calcule' },
      { year: 2026, month: 5, a_recalculer: false, origine: 'calcule' },
      { year: 2025, month: 12, a_recalculer: true, origine: 'calcule' },
    ]);
    expect(jobs.map((j) => `${j.year}-${j.month}`)).toEqual(['2026-4', '2025-12']);
  });

  it('ignore un bulletin d’un autre mois', () => {
    const jobs = jobsDesBulletinsPerimes(
      salaries.slice(0, 1),
      {
        e1: [{ year: 2026, month: 4, a_recalculer: true, origine: 'calcule' }],
      },
      2026,
      5
    );
    expect(jobs).toEqual([]);
  });
});

describe('libelleToastRecalcul', () => {
  const avant = { heures_sup: 2, salaire_brut: 1800, net_a_payer: 1400 };
  const apres = { heures_sup: 4, salaire_brut: 1900, net_a_payer: 1480 };

  it('résume heures sup, brut et net avant → après', () => {
    const toast = libelleToastRecalcul(avant, apres);
    expect(toast.title).toBe('Bulletin recalculé');
    expect(toast.description).toContain('Heures sup.');
    expect(toast.description).toContain('2');
    expect(toast.description).toContain('4');
    expect(toast.description).toContain('1 800');
    expect(toast.description).toContain('1 900');
    expect(toast.description).toContain('1 400');
    expect(toast.description).toContain('1 480');
  });

  it('ne invente pas un chiffre si un montant manque', () => {
    expect(libelleToastRecalcul(avant, null).description).toBe(MESSAGE_COMPARAISON_INDISPONIBLE);
    expect(
      libelleToastRecalcul(avant, { ...apres, net_a_payer: null }).description
    ).toBe(MESSAGE_COMPARAISON_INDISPONIBLE);
    expect(libelleToastRecalcul(null, apres).description).toBe(MESSAGE_COMPARAISON_INDISPONIBLE);
  });
});

describe('montants depuis la ligne ou la réponse', () => {
  it('lit les trois champs, ou null', () => {
    expect(
      montantsDepuisLigne({ heures_sup: 1, salaire_brut: 2, net_a_payer: 3 })
    ).toEqual({ heures_sup: 1, salaire_brut: 2, net_a_payer: 3 });
    expect(montantsDepuisReponse({})).toEqual({
      heures_sup: null,
      salaire_brut: null,
      net_a_payer: null,
    });
  });
});

describe('libellés écran', () => {
  it('le bouton dit quoi relancer, le message de validation dit de recalculer', () => {
    expect(libelleBoutonRecalculerTout(3)).toBe('Recalculer tout ce qui a changé (3)');
    expect(MESSAGE_A_RECALCULER).toMatch(/recalculez avant de valider/i);
  });
});
