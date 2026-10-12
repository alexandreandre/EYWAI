import { describe, expect, it } from 'vitest';

import {
  explicationAffichee,
  messageDuCalculEnCours,
  phraseBrutDeLaPrime,
  requeteBrutDeLaPrime,
  verrouDuCalcul,
} from './brutDeLaPrime';

// Lot 30 : la fenêtre des primes envoyait le net voulu POUR LA PRIME au calcul
// inverse d'un bulletin entier (127,60 € proposés pour 100 € nets, quel que
// soit le salarié ; puis 136,20 € sans convergence avec le moteur complet). Elle
// demande désormais le mode « prime » : le brut qui ajoute ce net au bulletin
// du mois du salarié. Et elle dit ce que le brut proposé représente.

const espaces = (texte: string | null) => (texte ?? '').replace(/[\u00a0\u202f]/g, ' ');

describe('la fenêtre des primes demande le brut d’une prime, pas d’un bulletin', () => {
  it('envoie le mode « prime », le mois du bulletin et les cases de la prime', () => {
    expect(
      requeteBrutDeLaPrime({
        employeeId: 'emp',
        netVoulu: 100,
        month: 10,
        year: 2026,
        soumiseACotisations: true,
        soumiseAImpot: false,
      })
    ).toEqual({
      employee_id: 'emp',
      net_target: 100,
      net_type: 'net_a_payer',
      month: 10,
      year: 2026,
      mode: 'prime',
      prime_soumise_a_cotisations: true,
      prime_soumise_a_impot: false,
    });
  });
});

describe('la fenêtre dit ce que le brut proposé représente', () => {
  const resultat = {
    brut_calcule: 127.73,
    net_obtenu: 100,
    ecart: 0,
    convergence: true,
    cout_employeur: 150.72,
    month: 10,
    year: 2026,
  };

  it('le net ajouté au bulletin du mois, sur quoi il est calculé, et le coût', () => {
    expect(espaces(phraseBrutDeLaPrime(resultat))).toBe(
      'Une prime de 127,73 € bruts ajoute 100,00 € au net à payer d’octobre 2026 de ce ' +
        'salarié : calcul sur son bulletin du mois (son salaire et les saisies déjà ' +
        'enregistrées). Coût pour l’employeur : 150,72 €.'
    );
  });

  it('dit le net obtenu quand il n’atteint pas le net voulu au centime', () => {
    expect(
      espaces(
        phraseBrutDeLaPrime({ ...resultat, net_obtenu: 99.97, ecart: -0.03, convergence: false })
      )
    ).toContain('ajoute 99,97 € (100,00 € voulus) au net à payer');
  });

  it('écrit « d’avril » et « de mai »', () => {
    expect(espaces(phraseBrutDeLaPrime({ ...resultat, month: 4 }))).toContain(
      'net à payer d’avril 2026'
    );
    expect(espaces(phraseBrutDeLaPrime({ ...resultat, month: 5 }))).toContain(
      'net à payer de mai 2026'
    );
  });
});

describe('la phrase ne survit pas à ce qu’elle décrit', () => {
  const calcul = {
    texte: 'Une prime de 129,27 € bruts ajoute 100,00 €…',
    montant: 129.27,
    soumiseACotisations: true,
    soumiseAImpot: true,
  };
  const saisie = { amount: 129.27, is_socially_taxed: true, is_taxable: true };

  it('reste tant que le montant et les cases sont ceux du calcul', () => {
    expect(explicationAffichee(calcul, saisie)).toBe(calcul.texte);
  });

  it('s’efface si le montant est retouché, si une case change, ou sans calcul', () => {
    expect(explicationAffichee(calcul, { ...saisie, amount: 130 })).toBeNull();
    expect(explicationAffichee(calcul, { ...saisie, amount: '' })).toBeNull();
    expect(explicationAffichee(calcul, { ...saisie, is_taxable: false })).toBeNull();
    expect(explicationAffichee(calcul, { ...saisie, is_socially_taxed: false })).toBeNull();
    expect(explicationAffichee(null, saisie)).toBeNull();
  });
});

// Lot 31 : le calcul prend quelques secondes (16,7 s mesurées au lot 30). La
// fenêtre dit ce qu'elle fait pendant l'attente, et un second clic ne relance
// pas un calcul déjà parti.
describe('pendant le calcul, la fenêtre dit ce qu’elle fait et ne se relance pas', () => {
  it('dit sur quel bulletin elle calcule', () => {
    expect(espaces(messageDuCalculEnCours(10, 2026))).toBe(
      'Calcul sur le bulletin d’octobre 2026 de ce salarié…'
    );
    expect(espaces(messageDuCalculEnCours(5, 2026))).toBe(
      'Calcul sur le bulletin de mai 2026 de ce salarié…'
    );
  });

  it('un second clic pendant le calcul ne relance rien', () => {
    const verrou = verrouDuCalcul();

    expect(verrou.prendre()).toBe(true);
    expect(verrou.prendre()).toBe(false);
    expect(verrou.prendre()).toBe(false);
  });

  it('le calcul fini, réussi ou non, le bouton relance', () => {
    const verrou = verrouDuCalcul();

    verrou.prendre();
    verrou.rendre();

    expect(verrou.prendre()).toBe(true);
  });
});
