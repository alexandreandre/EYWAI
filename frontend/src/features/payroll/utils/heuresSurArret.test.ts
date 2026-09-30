import { describe, expect, it } from 'vitest';
import {
  TITRE_INFO_BULLE_CONFLIT,
  choixApresCorrection,
  effacerLesJours,
  messageEchecEffacement,
  fusionnerJoursEnConflitImport,
  groupesParMois,
  lienModifierAbsence,
  lireJoursEnConflit,
  lireRefusApresCorrection,
  libelleDesJours,
  messageHeuresEffacees,
  natureDuConflit,
  prenomDe,
  estJourEnConflit,
  textesDuChoix,
} from './heuresSurArret';

const jour = (j: number, mois = 9, annee = 2026, heures = 9) => ({
  annee,
  mois,
  jour: j,
  heures,
});

describe('lireJoursEnConflit', () => {
  it('lit la liste du backend et ignore les entrées invalides', () => {
    expect(
      lireJoursEnConflit([
        { annee: 2026, mois: 9, jour: 7, heures: 9 },
        { annee: 2026, mois: 9, jour: 'x', heures: 1 },
        null,
        { annee: 2026, mois: 9, jour: 8, heures: 4.5 },
      ])
    ).toEqual([jour(7), jour(8, 9, 2026, 4.5)]);
  });
  it('rend une liste vide pour autre chose qu’un tableau', () => {
    expect(lireJoursEnConflit(undefined)).toEqual([]);
    expect(lireJoursEnConflit('7')).toEqual([]);
  });
});

describe('libelleDesJours', () => {
  it('un mois : 7, 8 et 9 septembre', () => {
    expect(libelleDesJours([jour(7), jour(8), jour(9)])).toBe('7, 8 et 9 septembre');
  });
  it('un seul jour', () => {
    expect(libelleDesJours([jour(1)])).toBe('1er septembre');
  });
  it('deux jours', () => {
    expect(libelleDesJours([jour(7), jour(8)])).toBe('7 et 8 septembre');
  });
  it('deux mois : chaque mois garde ses jours', () => {
    expect(libelleDesJours([jour(31, 8), jour(1), jour(2)])).toBe(
      '31 août et 1er et 2 septembre'
    );
  });
  it('trie par date', () => {
    expect(libelleDesJours([jour(9), jour(7)])).toBe('7 et 9 septembre');
  });
});

describe('messageHeuresEffacees', () => {
  it('confirme à l’écran les jours effacés', () => {
    expect(messageHeuresEffacees([jour(7), jour(8)])).toBe(
      'Heures effacées : 7 et 8 septembre.'
    );
  });
});

describe('groupesParMois', () => {
  it('un appel par (année, mois), jours triés sans doublon', () => {
    expect(groupesParMois([jour(2), jour(31, 8), jour(1), jour(2)])).toEqual([
      { annee: 2026, mois: 8, jours: [31] },
      { annee: 2026, mois: 9, jours: [1, 2] },
    ]);
  });
});

describe('natureDuConflit', () => {
  it('arrêt', () => {
    expect(
      natureDuConflit('Octavie est en arrêt, mais des heures sont saisies les 7, 8 et 9 septembre.')
    ).toBe('arret');
  });
  it('autre absence', () => {
    expect(
      natureDuConflit(
        'Octavie a une absence (congés payés), mais des heures sont saisies le 21 septembre.'
      )
    ).toBe('absence');
  });
  it('mélange : les deux phrases, traité comme une absence', () => {
    expect(
      natureDuConflit(
        'Octavie est en arrêt, mais des heures sont saisies le 7 septembre. Octavie a une absence (RTT), mais des heures sont saisies le 9 septembre.'
      )
    ).toBe('mixte');
  });
  it('message inconnu : absence, le plus neutre', () => {
    expect(natureDuConflit('autre chose')).toBe('absence');
  });
});

describe('prenomDe', () => {
  it('prend le premier mot', () => {
    expect(prenomDe('Octavie Martin')).toBe('Octavie');
  });
  it('rien si le nom est vide ou absent', () => {
    expect(prenomDe('  ')).toBeNull();
    expect(prenomDe(undefined)).toBeNull();
  });
  it('ne prend pas un identifiant pour un prénom', () => {
    expect(prenomDe('5f0c1c8e-2b2a-4c63-9d66-0c0f0f0f0f0f')).toBeNull();
  });
});

describe('textesDuChoix', () => {
  it('arrêt avec prénom', () => {
    expect(textesDuChoix('arret', 'Octavie')).toEqual({
      effacer: 'Octavie était en arrêt : effacer ces heures',
      modifier: 'Octavie a travaillé : modifier l’arrêt',
    });
  });
  it('absence avec prénom', () => {
    expect(textesDuChoix('absence', 'Octavie')).toEqual({
      effacer: 'Octavie n’a pas travaillé ces jours-là : effacer ces heures',
      modifier: 'Octavie a travaillé : modifier l’absence',
    });
  });
  it('mélange : le texte des absences', () => {
    expect(textesDuChoix('mixte', 'Octavie').modifier).toBe(
      'Octavie a travaillé : modifier l’absence'
    );
  });
  it('sans prénom : « Le salarié », sans genre', () => {
    expect(textesDuChoix('arret', null)).toEqual({
      effacer: 'Le salarié était en arrêt : effacer ces heures',
      modifier: 'Le salarié a travaillé : modifier l’arrêt',
    });
    expect(textesDuChoix('absence', null).effacer).toBe(
      'Le salarié n’a pas travaillé ces jours-là : effacer ces heures'
    );
  });
});

describe('lienModifierAbsence', () => {
  it('ouvre l’écran des absences filtré sur le salarié', () => {
    expect(lienModifierAbsence('emp 1/é')).toBe('/leaves?employee=emp%201%2F%C3%A9');
  });
});

describe('lireRefusApresCorrection', () => {
  it('lit recalcul_refus du backend', () => {
    expect(
      lireRefusApresCorrection({
        code: 'heures_sur_jour_d_arret',
        message: 'X est en arrêt, mais des heures sont saisies le 7 septembre.',
        jours: [{ annee: 2026, mois: 9, jour: 7, heures: 9 }],
      })
    ).toEqual({
      code: 'heures_sur_jour_d_arret',
      message: 'X est en arrêt, mais des heures sont saisies le 7 septembre.',
      jours: [jour(7)],
    });
  });
  it('null si absent ou mal formé', () => {
    expect(lireRefusApresCorrection(null)).toBeNull();
    expect(lireRefusApresCorrection(undefined)).toBeNull();
    expect(lireRefusApresCorrection({ message: 'sans code' })).toBeNull();
  });
});

describe('choixApresCorrection', () => {
  const refus = {
    code: 'heures_sur_jour_d_arret',
    message: 'X est en arrêt, mais des heures sont saisies le 7 septembre.',
    jours: [{ annee: 2026, mois: 9, jour: 7, heures: 9 }],
  };
  it('heures sur arrêt : on propose le choix, pas « Régénérer »', () => {
    const d = choixApresCorrection({ recalcul_erreur: refus.message, recalcul_refus: refus });
    expect(d.kind).toBe('choix');
    if (d.kind === 'choix') {
      expect(d.refus.jours).toEqual([jour(7)]);
    }
  });
  it('autre refus ou simple erreur : « Régénérer » reste la sortie', () => {
    expect(
      choixApresCorrection({
        recalcul_erreur: 'Calcul impossible',
        recalcul_refus: { code: 'calendrier_incomplet', message: 'm', jours: [] },
      }).kind
    ).toBe('regenerer');
    expect(choixApresCorrection({ recalcul_erreur: 'Calcul impossible' }).kind).toBe(
      'regenerer'
    );
  });
  it('rien à dire si le recalcul a réussi', () => {
    expect(choixApresCorrection({ recalcul_erreur: null, recalcul_refus: null }).kind).toBe(
      'aucun'
    );
    expect(choixApresCorrection({}).kind).toBe('aucun');
  });
  it('refus d’heures sans jours lisibles : on retombe sur Régénérer avec le message', () => {
    expect(
      choixApresCorrection({
        recalcul_erreur: 'm',
        recalcul_refus: { code: 'heures_sur_jour_d_arret', message: 'm', jours: [] },
      }).kind
    ).toBe('regenerer');
  });
});

describe('estJourEnConflit', () => {
  it('repère un jour de la liste du backend', () => {
    expect(estJourEnConflit(7, [7, 9])).toBe(true);
    expect(estJourEnConflit(8, [7, 9])).toBe(false);
    expect(estJourEnConflit(8, undefined)).toBe(false);
  });
  it('l’info-bulle est celle du brief', () => {
    expect(TITRE_INFO_BULLE_CONFLIT).toBe('Heures saisies pendant l’arrêt');
  });
});

describe('fusionnerJoursEnConflitImport', () => {
  const direct = [{ employee_id: 'e1', jours: [jour(7)] }];
  const lot = [{ employee_id: 'e2', jours: [jour(8), jour(9)] }];
  it('chemin direct : la réponse immédiate', () => {
    expect(fusionnerJoursEnConflitImport(direct, undefined)).toEqual(direct);
  });
  it('avec batch_id : la réponse est vide, le résumé du lot porte la liste', () => {
    expect(fusionnerJoursEnConflitImport([], lot)).toEqual(lot);
  });
  it('les deux sources : une ligne par salarié, jours réunis sans doublon', () => {
    expect(
      fusionnerJoursEnConflitImport(
        [{ employee_id: 'e1', jours: [jour(7)] }],
        [
          { employee_id: 'e1', jours: [jour(7), jour(10)] },
          { employee_id: 'e2', jours: [jour(8)] },
        ]
      )
    ).toEqual([
      { employee_id: 'e1', jours: [jour(7), jour(10)] },
      { employee_id: 'e2', jours: [jour(8)] },
    ]);
  });
  it('ignore les entrées mal formées', () => {
    expect(fusionnerJoursEnConflitImport(null, [{ jours: [jour(1)] }, 3])).toEqual([]);
  });
});

describe('effacerLesJours', () => {
  it('appelle le backend une fois par mois et rend tout ce qui a été effacé', async () => {
    const appels: unknown[] = [];
    const resultat = await effacerLesJours([jour(1), jour(31, 8), jour(2)], async (annee, mois, jours) => {
      appels.push([annee, mois, jours]);
    });
    expect(appels).toEqual([
      [2026, 8, [31]],
      [2026, 9, [1, 2]],
    ]);
    expect(resultat).toEqual({ ok: true, effaces: [jour(31, 8), jour(1), jour(2)] });
  });

  it('au premier refus : s’arrête, garde la raison et ce qui était déjà effacé', async () => {
    const erreur = new Error('refus');
    const resultat = await effacerLesJours([jour(31, 8), jour(1)], async (_a, mois) => {
      if (mois === 9) throw erreur;
    });
    expect(resultat).toEqual({
      ok: false,
      effaces: [jour(31, 8)],
      restants: [jour(1)],
      erreur,
    });
  });

  it('refus dès le premier mois : rien n’est effacé', async () => {
    const resultat = await effacerLesJours([jour(7)], async () => {
      throw new Error('x');
    });
    expect(resultat.ok).toBe(false);
    if (!resultat.ok) expect(resultat.effaces).toEqual([]);
  });
});

describe('messageEchecEffacement', () => {
  it('pluriel : « les 7 et 8 septembre »', () => {
    expect(messageEchecEffacement([jour(7), jour(8)], 'Réessayez.')).toContain(
      'seulement les 7 et 8 septembre.'
    );
  });
  it('dit la raison et que la génération n’a pas été relancée', () => {
    expect(messageEchecEffacement([], 'Le 9 septembre n’est ni un jour d’arrêt.')).toBe(
      'Les heures n’ont pas été effacées : Le 9 septembre n’est ni un jour d’arrêt. La génération n’a pas été relancée.'
    );
  });
  it('dit ce qui a été effacé avant le refus', () => {
    expect(messageEchecEffacement([jour(31, 8)], 'Réessayez.')).toBe(
      'Heures effacées seulement le 31 août. Le reste n’a pas pu l’être : Réessayez. La génération n’a pas été relancée.'
    );
  });
});
