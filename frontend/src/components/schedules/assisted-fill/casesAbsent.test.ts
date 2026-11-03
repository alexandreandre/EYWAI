import { describe, expect, it } from 'vitest';

import { TYPE_ABSENT_A_TYPER } from '@/lib/absentATyper';
import {
  absentsMarques,
  basculerAbsent,
  joursPourEnregistrement,
  joursVides,
  phraseAvantEnregistrement,
  type JourRevu,
} from './casesAbsent';

// Semaine du lundi 12 au vendredi 16 octobre 2026.
const PERIODE = { debut: '2026-10-12', fin: '2026-10-16', annee: 2026, mois: 10 };

const lu = (jour: number, heures: number | null, type = 'travail'): JourRevu => ({
  jour,
  heures,
  type,
  nature: 'reel',
});

describe('jours vides d’une ligne de l’import', () => {
  it('liste les jours lus sans heures et les jours ouvrés du document non lus', () => {
    const jours = [lu(12, 7), lu(13, null), lu(15, 7), lu(16, 0)];
    expect(joursVides(jours, PERIODE)).toEqual([
      { jour: 13, annee: 2026, mois: 10, lu: true },
      { jour: 14, annee: 2026, mois: 10, lu: false },
      { jour: 16, annee: 2026, mois: 10, lu: true },
    ]);
  });

  it('un jour déjà typé (congé, arrêt…) n’est pas vide', () => {
    expect(joursVides([lu(12, null, 'arret_maladie')], { ...PERIODE, fin: '2026-10-12' })).toEqual(
      []
    );
  });

  it('sans période connue, seuls les jours lus sans heures comptent', () => {
    expect(joursVides([lu(12, null), lu(13, 7)], { annee: 2026, mois: 10 })).toEqual([
      { jour: 12, annee: 2026, mois: 10, lu: true },
    ]);
  });

  it('un jour coché absent reste dans la liste, coché', () => {
    const jours = basculerAbsent([lu(12, 7)], { jour: 14, annee: 2026, mois: 10, lu: false }, true);
    expect(joursVides(jours, PERIODE).find((j) => j.jour === 14)).toEqual({
      jour: 14,
      annee: 2026,
      mois: 10,
      lu: true,
    });
  });
});

describe('cocher et décocher « absent »', () => {
  it('cocher un jour non lu l’ajoute, marqué absent, sans heures', () => {
    const jours = basculerAbsent([lu(12, 7)], { jour: 14, annee: 2026, mois: 10, lu: false }, true);
    expect(jours).toEqual([
      lu(12, 7),
      {
        jour: 14,
        heures: null,
        type: TYPE_ABSENT_A_TYPER,
        nature: 'reel',
        year: 2026,
        month: 10,
        ajoutParCase: true,
      },
    ]);
  });

  it('décocher un jour ajouté par la case le retire (rien n’est écrit ce jour-là)', () => {
    const coche = basculerAbsent([lu(12, 7)], { jour: 14, annee: 2026, mois: 10, lu: false }, true);
    expect(basculerAbsent(coche, { jour: 14, annee: 2026, mois: 10, lu: true }, false)).toEqual([
      lu(12, 7),
    ]);
  });

  it('cocher un jour lu sans heures change son type', () => {
    const jours = basculerAbsent([lu(13, null)], { jour: 13, annee: 2026, mois: 10, lu: true }, true);
    expect(jours[0].type).toBe(TYPE_ABSENT_A_TYPER);
    expect(jours[0].heures).toBeNull();
  });

  it('décocher rend le jour vide, de type travail', () => {
    const coche = basculerAbsent([lu(13, null)], { jour: 13, annee: 2026, mois: 10, lu: true }, true);
    expect(basculerAbsent(coche, { jour: 13, annee: 2026, mois: 10, lu: true }, false)).toEqual([
      lu(13, null),
    ]);
  });
});

describe('enregistrement', () => {
  it('un jour absent part au prévu (le type) et au réel (vide)', () => {
    const jours = [lu(12, 7), { ...lu(13, null), type: TYPE_ABSENT_A_TYPER, ajoutParCase: true }];
    expect(joursPourEnregistrement(jours)).toEqual([
      lu(12, 7),
      { jour: 13, heures: null, type: TYPE_ABSENT_A_TYPER, nature: 'prevu' },
      { jour: 13, heures: null, type: TYPE_ABSENT_A_TYPER, nature: 'reel' },
    ]);
  });

  it('la phrase avant d’enregistrer annonce le blocage', () => {
    expect(phraseAvantEnregistrement(0)).toBeNull();
    expect(phraseAvantEnregistrement(1)).toBe(
      '1 jour marqué « absent » : la paie de ce salarié restera bloquée tant que vous ne lui aurez pas donné son type au calendrier (congé, RTT, arrêt ou absence non payée).'
    );
    expect(phraseAvantEnregistrement(3)).toBe(
      '3 jours marqués « absent » : la paie restera bloquée tant que vous ne leur aurez pas donné leur type au calendrier (congé, RTT, arrêt ou absence non payée).'
    );
  });

  it('le récapitulatif liste les salariés et leurs jours absents', () => {
    expect(
      absentsMarques([
        { employeeId: 'e1', nom: 'Salariée Une', jours: [lu(12, 7), { ...lu(14, null), type: TYPE_ABSENT_A_TYPER }] },
        { employeeId: 'e2', nom: 'Salarié Deux', jours: [lu(12, 7)] },
      ])
    ).toEqual([{ employeeId: 'e1', nom: 'Salariée Une', jours: [14] }]);
  });
});
