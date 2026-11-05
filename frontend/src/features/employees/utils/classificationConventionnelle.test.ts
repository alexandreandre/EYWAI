import { describe, expect, it } from 'vitest';
import {
  classificationAvecPcs,
  CLASSIFICATION_VIDE,
  GROUPE_NON_PRECISE,
  classificationGardee,
  classificationPourEnvoi,
  estClassificationVide,
  grilleAvecClassificationHabituelle,
  libelleClassification,
  valeurDuChoix,
} from './classificationConventionnelle';

const GRILLE_COEFFICIENT_SEUL = [700, 710, 720].map((coefficient) => ({
  groupe_emploi: GROUPE_NON_PRECISE,
  classe_emploi: 0,
  coefficient,
}));
const GRILLE_PAR_CLASSE = [
  { groupe_emploi: 'A', classe_emploi: 1, coefficient: 130 },
  { groupe_emploi: 'C', classe_emploi: 5, coefficient: 170 },
];

describe('une classification vide ne se remplit pas d’office', () => {
  it('le départ est vide', () => {
    expect(estClassificationVide(CLASSIFICATION_VIDE)).toBe(true);
    expect(estClassificationVide({ groupe_emploi: ' ', classe_emploi: '', coefficient: '' })).toBe(true);
    expect(estClassificationVide(null)).toBe(true);
    expect(estClassificationVide({ groupe_emploi: GROUPE_NON_PRECISE, classe_emploi: 0, coefficient: 700 })).toBe(
      false,
    );
  });

  it('une liste vide montre « Choisir une classification » (aucune valeur choisie)', () => {
    expect(valeurDuChoix(CLASSIFICATION_VIDE)).toBeUndefined();
    expect(valeurDuChoix({ groupe_emploi: GROUPE_NON_PRECISE, classe_emploi: 0, coefficient: 700 })).toBe(
      'Non précisé-0-700',
    );
  });
});

describe('quand la grille de la convention arrive', () => {
  it('garde la classification choisie si la grille la connaît', () => {
    const choisie = GRILLE_COEFFICIENT_SEUL[1];
    expect(classificationGardee(choisie, GRILLE_COEFFICIENT_SEUL)).toEqual(choisie);
  });

  it('sinon la vide : la RH choisit, rien n’est pris d’office (plus la première ligne)', () => {
    expect(
      classificationGardee({ groupe_emploi: 'C', classe_emploi: 6, coefficient: 240 }, GRILLE_COEFFICIENT_SEUL),
    ).toEqual(CLASSIFICATION_VIDE);
    expect(classificationGardee(CLASSIFICATION_VIDE, GRILLE_COEFFICIENT_SEUL)).toEqual(CLASSIFICATION_VIDE);
  });
});

describe('la classification habituelle de la société, proposée sans être choisie', () => {
  it('sous une grille à coefficient seul, elle perd le groupe et la classe inventés', () => {
    // Groupe « C » et classe recopiée du coefficient : la valeur d'office d'avant.
    const habituelle = { groupe_emploi: 'C', classe_emploi: 710, coefficient: 710 };
    expect(grilleAvecClassificationHabituelle(GRILLE_COEFFICIENT_SEUL, habituelle)).toEqual(GRILLE_COEFFICIENT_SEUL);
    const ailleurs = { groupe_emploi: 'C', classe_emploi: 830, coefficient: 830 };
    expect(grilleAvecClassificationHabituelle(GRILLE_COEFFICIENT_SEUL, ailleurs)).toEqual([
      ...GRILLE_COEFFICIENT_SEUL,
      { groupe_emploi: GROUPE_NON_PRECISE, classe_emploi: 0, coefficient: 830 },
    ]);
  });

  it('sous une grille par classe, elle s’ajoute telle quelle si la grille ne la connaît pas', () => {
    const habituelle = { groupe_emploi: 'D', classe_emploi: 7, coefficient: 190 };
    expect(grilleAvecClassificationHabituelle(GRILLE_PAR_CLASSE, habituelle)).toEqual([
      ...GRILLE_PAR_CLASSE,
      habituelle,
    ]);
    expect(grilleAvecClassificationHabituelle(GRILLE_PAR_CLASSE, GRILLE_PAR_CLASSE[1])).toEqual(GRILLE_PAR_CLASSE);
    expect(grilleAvecClassificationHabituelle(GRILLE_PAR_CLASSE, null)).toEqual(GRILLE_PAR_CLASSE);
  });
});

describe('le libellé d’une classification', () => {
  it('« Coeff. 700 » seul quand le groupe n’est pas précisé et la classe à 0', () => {
    expect(libelleClassification({ groupe_emploi: GROUPE_NON_PRECISE, classe_emploi: 0, coefficient: 700 })).toBe(
      'Coeff. 700',
    );
  });

  it('groupe, classe et coefficient sinon', () => {
    expect(libelleClassification({ groupe_emploi: 'C', classe_emploi: 5, coefficient: 170 })).toBe(
      'Groupe C - Classe 5 - Coeff. 170',
    );
    expect(libelleClassification({ groupe_emploi: 'C', classe_emploi: 5, coefficient: undefined })).toBe(
      'Groupe C - Classe 5',
    );
  });
});

describe('ce qui part au serveur', () => {
  it('sans convention ou sans saisie : aucune classification', () => {
    expect(classificationPourEnvoi(CLASSIFICATION_VIDE)).toEqual({});
    expect(classificationPourEnvoi({ groupe_emploi: '', classe_emploi: undefined, coefficient: undefined })).toEqual(
      {},
    );
  });

  it('un coefficient seul se range en « Non précisé », classe 0, comme la grille de la plasturgie', () => {
    expect(classificationPourEnvoi({ groupe_emploi: '', classe_emploi: undefined, coefficient: 700 })).toEqual({
      groupe_emploi: GROUPE_NON_PRECISE,
      classe_emploi: 0,
      coefficient: 700,
    });
  });

  it('une classification complète part telle quelle ; une classe absente n’est pas inventée', () => {
    expect(classificationPourEnvoi({ groupe_emploi: 'C', classe_emploi: 5, coefficient: 170 })).toEqual({
      groupe_emploi: 'C',
      classe_emploi: 5,
      coefficient: 170,
    });
    expect(classificationPourEnvoi({ groupe_emploi: ' D ', classe_emploi: '', coefficient: '190' })).toEqual({
      groupe_emploi: 'D',
      coefficient: 190,
    });
  });
});

describe('le code PCS-ESE choisi à la création part avec la classification', () => {
  it('ajoute le code sans toucher au reste', () => {
    expect(classificationAvecPcs({ groupe_emploi: 'C', classe_emploi: 6, coefficient: 240 }, '674a')).toEqual({
      groupe_emploi: 'C',
      classe_emploi: 6,
      coefficient: 240,
      pcs: '674a',
    });
  });
  it('sans code, rien de plus', () => {
    expect(classificationAvecPcs({ groupe_emploi: '', classe_emploi: undefined, coefficient: undefined }, '')).toEqual({});
    expect(classificationAvecPcs(undefined, '  ')).toEqual({});
  });
  it('un code seul, sans classification', () => {
    expect(classificationAvecPcs(undefined, '9999')).toEqual({ pcs: '9999' });
  });
});
