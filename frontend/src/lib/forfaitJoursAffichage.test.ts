import { describe, expect, it } from 'vitest';
import { PHRASE_FORFAIT_JOURS_SANS_HEURES_SUP, modelesSemaineProposes } from './forfaitJoursAffichage';

const modeles = [
  { name: '35 h (7 h/jour)', template: { 1: '7', 2: '7', 3: '7', 4: '7', 5: '7' } },
  { name: 'Lundi au jeudi (jours)', template: { 1: '1', 2: '1', 3: '1', 4: '1', 5: '0' } },
  { name: 'Mi-temps 4 h', template: { 1: '4', 2: '4' } },
];

describe('forfait jours : affichage', () => {
  it('la phrase dit que le temps se compte en jours', () => {
    expect(PHRASE_FORFAIT_JOURS_SANS_HEURES_SUP).toBe(
      'Au forfait jours, pas d’heures supplémentaires : le temps se compte en jours.'
    );
  });

  it('un salarié au forfait jours ne se voit proposer que les modèles en jours', () => {
    expect(modelesSemaineProposes(modeles, true).map((m) => m.name)).toEqual(['Lundi au jeudi (jours)']);
  });

  it('un salarié en heures voit tous les modèles', () => {
    expect(modelesSemaineProposes(modeles, false)).toHaveLength(3);
  });
});
