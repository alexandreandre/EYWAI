import { describe, it, expect } from 'vitest';
import {
  estLigneHeuresSupConjoncturelle,
  leMoteurRecalculera,
  lienVariablesDuMois,
  nombreDeLignesModifiees,
  resumeAutomatique,
  totalHeuresSupConjoncturelles,
} from './payslipDerivedLines';

/** Bulletin calqué sur BUGNY juillet 2026. */
const lignes = (h25: number, h50: number) => [
  { libelle: 'Salaire de base', quantite: 151.67 },
  { libelle: 'Heures suppl. structurelles majorées à 25%', quantite: 17.33 },
  { libelle: 'Heures suppl. majorées à 25%', quantite: h25 },
  { libelle: 'Heures suppl. majorées à 50%', quantite: h50 },
];

describe('totalHeuresSupConjoncturelles', () => {
  it('additionne les deux paliers, sans les structurelles', () => {
    expect(totalHeuresSupConjoncturelles(lignes(12, 3.5))).toBe(15.5);
  });

  it('rend zéro sur un bulletin sans heures supplémentaires', () => {
    expect(totalHeuresSupConjoncturelles([])).toBe(0);
    expect(totalHeuresSupConjoncturelles(undefined)).toBe(0);
  });
});

describe('leMoteurRecalculera', () => {
  it('oui quand le total change', () => {
    expect(leMoteurRecalculera(lignes(12, 3.5), lignes(13, 3.5))).toBe(true);
  });

  it('oui quand un seul palier tombe à zéro, l’autre subsistant', () => {
    expect(leMoteurRecalculera(lignes(12, 3.5), lignes(0, 3.5))).toBe(true);
  });

  it('non quand les deux paliers sont remis à zéro', () => {
    // Le moteur n'y voit pas une déclaration : il repartirait du calendrier
    // et rétablirait les heures. Ne rien promettre.
    expect(leMoteurRecalculera(lignes(12, 3.5), lignes(0, 0))).toBe(false);
  });

  it('non quand la répartition change à total constant', () => {
    // 12 + 3,5 = 13 + 2,5 : le moteur compare les totaux et ne bouge pas,
    // alors que les taux diffèrent (17,85 € contre 21,42 €).
    expect(leMoteurRecalculera(lignes(12, 3.5), lignes(13, 2.5))).toBe(false);
  });

  it('non quand rien n’a bougé', () => {
    expect(leMoteurRecalculera(lignes(12, 3.5), lignes(12, 3.5))).toBe(false);
  });
});

describe('estLigneHeuresSupConjoncturelle', () => {
  it('reconnaît les heures supplémentaires conjoncturelles', () => {
    expect(estLigneHeuresSupConjoncturelle('Heures suppl. majorées à 25%')).toBe(true);
    expect(estLigneHeuresSupConjoncturelle('Heures suppl. majorées à 50%')).toBe(true);
  });

  it('écarte les structurelles : elles viennent du contrat, pas du mois', () => {
    expect(
      estLigneHeuresSupConjoncturelle('Heures suppl. structurelles majorées à 25%')
    ).toBe(false);
  });

  it('écarte les heures complémentaires du temps partiel', () => {
    expect(
      estLigneHeuresSupConjoncturelle('Heures complémentaires majorées à 10%')
    ).toBe(false);
  });

  it('écarte le salaire de base, les primes et les lignes sans libellé', () => {
    expect(estLigneHeuresSupConjoncturelle('Salaire de base')).toBe(false);
    expect(estLigneHeuresSupConjoncturelle('Panier repas')).toBe(false);
    expect(estLigneHeuresSupConjoncturelle("Prime d'ancienneté (3 ans, 2 %)")).toBe(
      false
    );
    expect(estLigneHeuresSupConjoncturelle('')).toBe(false);
    expect(estLigneHeuresSupConjoncturelle(undefined)).toBe(false);
  });
});

describe('lienVariablesDuMois', () => {
  it('cible la page Primes sur le bon mois et le bon salarié', () => {
    expect(lienVariablesDuMois({ employeeId: 'abc', year: 2026, month: 7 })).toBe(
      '/saisies?year=2026&month=7&employee=abc'
    );
  });

  it('reste utilisable sans salarié', () => {
    expect(lienVariablesDuMois({ year: 2026, month: 12 })).toBe(
      '/saisies?year=2026&month=12'
    );
  });
});

describe('resumeAutomatique', () => {
  it('décrit la correction des heures supplémentaires quand la RH n’écrit rien', () => {
    // Bugny, 12/09 : 12 h + 3,5 h corrigées en 19 h + 6,5 h, résumé laissé vide.
    expect(resumeAutomatique(lignes(12, 3.5), lignes(19, 6.5))).toBe(
      'Correction des heures supplémentaires : 15,5 h → 25,5 h'
    );
  });

  it('reste générique quand les heures sup n’ont pas bougé', () => {
    expect(resumeAutomatique(lignes(12, 3.5), lignes(12, 3.5))).toBe(
      'Modification manuelle du bulletin'
    );
  });

  it('écrit les heures entières sans décimale', () => {
    expect(resumeAutomatique(lignes(12, 0), lignes(13, 0))).toBe(
      'Correction des heures supplémentaires : 12 h → 13 h'
    );
  });
});

describe('nombreDeLignesModifiees', () => {
  const original = {
    calcul_du_brut: lignes(12, 3.5),
    details_absences: [{ libelle: 'Absence injustifiée du 07/07/26 (base)', quantite: 7 }],
    details_conges: [],
  };

  it('compte les lignes qui ont changé, section par section', () => {
    const edite = {
      ...original,
      calcul_du_brut: lignes(19, 6.5),
      details_absences: [{ libelle: 'Absence injustifiée du 07/07/26 (base)', quantite: 7.63 }],
    };
    // Deux lignes d'heures sup et une ligne d'absence.
    expect(nombreDeLignesModifiees(original, edite)).toBe(3);
  });

  it('compte une ligne ajoutée ou retirée', () => {
    const ajout = { ...original, details_conges: [{ libelle: 'Nouveau congé', quantite: 1 }] };
    expect(nombreDeLignesModifiees(original, ajout)).toBe(1);
    const retrait = { ...original, details_absences: [] };
    expect(nombreDeLignesModifiees(original, retrait)).toBe(1);
  });

  it('rend zéro sans changement ou sans données', () => {
    expect(nombreDeLignesModifiees(original, { ...original })).toBe(0);
    expect(nombreDeLignesModifiees(undefined, original)).toBe(0);
  });
});
