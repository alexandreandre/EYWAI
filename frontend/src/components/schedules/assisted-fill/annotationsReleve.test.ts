import { describe, expect, it } from 'vitest';

import {
  annotationsDesLignes,
  estAnnotationReleve,
  lireAnnotationsReleve,
  phraseAnnotations,
} from './annotationsReleve';

const SEMAINE_39 =
  'Relevé à relire — Martine a retenu les heures du badge, pas les annotations : ' +
  'lun 21/09 « CP » ; mar 22/09 « ?????? absent 7,5 » ; mer 23/09 « PANIERS 3 » ; ' +
  'ven 25/09 « +1 », badgeage incomplet, 3,53 h lues.';
const SEMAINE_40 =
  'Relevé à relire — Martine a retenu les heures du badge, pas les annotations : ' +
  'lun 28/09 badgeage incomplet, aucune heure lue.';

describe('annotations du relevé MBC (lot L18, Elsa 26/11)', () => {
  it('reconnaît le message du serveur', () => {
    expect(estAnnotationReleve(SEMAINE_39)).toBe(true);
    expect(estAnnotationReleve('Jour 3 : pointage incomplet')).toBe(false);
  });

  it('lit chaque jour à part, avec son annotation entière', () => {
    expect(lireAnnotationsReleve(SEMAINE_39)).toEqual([
      { jour: 'lun 21/09', annotation: '« CP »' },
      { jour: 'mar 22/09', annotation: '« ?????? absent 7,5 »' },
      { jour: 'mer 23/09', annotation: '« PANIERS 3 »' },
      { jour: 'ven 25/09', annotation: '« +1 », badgeage incomplet, 3,53 h lues' },
    ]);
  });

  it('regroupe par salarié, toutes semaines confondues, sans doublon', () => {
    const groupes = annotationsDesLignes([
      { cle: 'a', nom: 'Jean Exemple', warnings: [SEMAINE_39, SEMAINE_40, SEMAINE_39, 'Autre remarque'] },
      { cle: 'b', nom: 'Sans annotation', warnings: ['Jour 3 : pointage incomplet'] },
    ]);
    expect(groupes).toHaveLength(1);
    expect(groupes[0].nom).toBe('Jean Exemple');
    expect(groupes[0].jours.map((j) => j.jour)).toEqual([
      'lun 21/09',
      'mar 22/09',
      'mer 23/09',
      'ven 25/09',
      'lun 28/09',
    ]);
  });

  it('résume le nombre de jours et de salariés', () => {
    expect(phraseAnnotations(1, 1)).toBe('1 jour annoté sur le relevé');
    expect(phraseAnnotations(5, 2)).toBe('5 jours annotés sur le relevé, pour 2 salariés');
  });

  it('un message illisible reste montré tel quel', () => {
    expect(lireAnnotationsReleve('Relevé à relire — format inattendu')).toEqual([
      { jour: '', annotation: 'Relevé à relire — format inattendu' },
    ]);
  });
});
