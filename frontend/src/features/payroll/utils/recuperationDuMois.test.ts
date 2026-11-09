import { describe, expect, it } from 'vitest';
import {
  CONSEQUENCE_DU_CHOIX,
  heuresFr,
  jouerLeGeste,
  lireRecuperation,
} from '@/features/payroll/utils/recuperationDuMois';

describe('lireRecuperation', () => {
  it("rien quand la société paie ses heures sup", () => {
    expect(lireRecuperation({ pied_de_page: { solde_conges: {} } })).toBeNull();
    expect(lireRecuperation(null)).toBeNull();
  });

  it('heures du mois au compteur et solde', () => {
    const etat = lireRecuperation({
      modulation_account: { hs_realisees: 4, hs_credited: 4, hs_paid: 0, repos_credite: 5, regle: 'account_all' },
      pied_de_page: { solde_conges: { recuperation: { solde: 7, paye: 0, payable: 2 } } },
    });
    expect(etat).toEqual({
      heuresSupDuMois: 4,
      heuresSupAuCompteur: 4,
      reposCredite: 5,
      payeesCeMois: false,
      solde: 7,
      soldePaye: 0,
      soldePayable: 2,
      regle: 'compteur',
      auCompteurCeMois: false,
    });
  });

  it('le choix « payer ce mois-ci » se relit', () => {
    const etat = lireRecuperation({
      modulation_account: { hs_realisees: 4, hs_credited: 0, hs_paid: 4, repos_credite: 0, paye_ce_mois: true },
      pied_de_page: { solde_conges: { recuperation: { solde: 2, paye: 0 } } },
    });
    expect(etat?.payeesCeMois).toBe(true);
  });
});

describe('règles', () => {
  it('société qui paie : salarié avec un solde repris', () => {
    const etat = lireRecuperation({
      modulation_account: { hs_realisees: 0, regle: 'pay_all' },
      pied_de_page: { solde_conges: { recuperation: { solde: 20, payable: 20 } } },
    });
    expect(etat?.regle).toBe('payees');
    expect(etat?.soldePayable).toBe(20);
  });

  it('société qui paie : salarié sans compteur mais avec des heures sup', () => {
    const etat = lireRecuperation({
      modulation_account: { hs_realisees: 4, hs_paid: 4, regle: 'pay_all' },
      pied_de_page: { solde_conges: {} },
    });
    expect(etat?.heuresSupDuMois).toBe(4);
    expect(etat?.solde).toBe(0);
  });

  it('société qui paie : salarié sans compteur ni heures sup, rien à dire', () => {
    expect(
      lireRecuperation({
        modulation_account: { hs_realisees: 0, regle: 'pay_all' },
        pied_de_page: { solde_conges: {} },
      }),
    ).toBeNull();
  });
});

describe('textes', () => {
  it('heures en français', () => {
    expect(heuresFr(1.25)).toBe('1,25 h');
    expect(heuresFr(2)).toBe('2 h');
  });

  it("la conséquence est dite à l'écran", () => {
    expect(CONSEQUENCE_DU_CHOIX).toContain("exonération d'impôt");
    expect(CONSEQUENCE_DU_CHOIX).toContain('perdent');
  });
});

describe('jouerLeGeste (R-322)', () => {
  const noter = () => {
    const appels: string[] = [];
    return {
      appels,
      trace: (nom: string) => async () => {
        appels.push(nom);
      },
    };
  };

  it('recalcul réussi : rien à défaire', async () => {
    const { appels, trace } = noter();
    const issue = await jouerLeGeste(trace('geste'), trace('regen'), trace('defaire'), false);
    expect(issue).toEqual({ kind: 'recalcule' });
    expect(appels).toEqual(['geste', 'regen']);
  });

  it('geste refusé : rien à recalculer ni à défaire', async () => {
    const { appels, trace } = noter();
    const erreur = new Error('refus');
    const issue = await jouerLeGeste(
      () => Promise.reject(erreur),
      trace('regen'),
      trace('defaire'),
      false,
    );
    expect(issue).toEqual({ kind: 'refuse', erreur });
    expect(appels).toEqual([]);
  });

  it('bulletin retouché : enregistré, pas de recalcul', async () => {
    const { appels, trace } = noter();
    const issue = await jouerLeGeste(trace('geste'), trace('regen'), trace('defaire'), true);
    expect(issue).toEqual({ kind: 'sans_recalcul' });
    expect(appels).toEqual(['geste']);
  });

  it('recalcul en échec : le geste est défait', async () => {
    const { appels, trace } = noter();
    const erreur = new Error('calcul impossible');
    const issue = await jouerLeGeste(
      trace('geste'),
      () => Promise.reject(erreur),
      trace('defaire'),
      false,
    );
    expect(issue).toEqual({ kind: 'defait', erreur });
    expect(appels).toEqual(['geste', 'defaire']);
  });

  it('recalcul en échec et geste non défait : on le dit', async () => {
    const { appels, trace } = noter();
    const erreur = new Error('calcul impossible');
    const issue = await jouerLeGeste(
      trace('geste'),
      () => Promise.reject(erreur),
      () => Promise.reject(new Error('coupure')),
      false,
    );
    expect(issue).toEqual({ kind: 'non_defait', erreur });
    expect(appels).toEqual(['geste']);
  });
});
