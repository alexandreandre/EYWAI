import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import {
  afficherAsterisque,
  lignesAvecExplication,
  texteInfobulle,
} from './explicationsLignes';

describe('afficherAsterisque', () => {
  it('uniquement quand une explication est présente', () => {
    expect(afficherAsterisque({ libelle: 'Heures suppl. majorées à 25%', explication: '16 h à 25 %' })).toBe(
      true
    );
    expect(afficherAsterisque({ libelle: 'Salaire de base' })).toBe(false);
    expect(afficherAsterisque({ libelle: 'HS', explication: null })).toBe(false);
  });

  it('jamais pour une info-bulle vide', () => {
    expect(afficherAsterisque({ libelle: 'HS', explication: '' })).toBe(false);
    expect(afficherAsterisque({ libelle: 'HS', explication: '   ' })).toBe(false);
  });
});

describe('texteInfobulle', () => {
  it('rend le texte d’origine, jamais une chaîne vide', () => {
    expect(texteInfobulle({ explication: 'Absence : arrêt maladie du 1er au 30/09' })).toBe(
      'Absence : arrêt maladie du 1er au 30/09'
    );
    expect(texteInfobulle({ explication: '  ' })).toBeNull();
    expect(texteInfobulle({})).toBeNull();
  });
});

describe('lignesAvecExplication', () => {
  it('ne retient que les lignes déjà expliquées par le bulletin', () => {
    const lignes = lignesAvecExplication({
      calcul_du_brut: [
        { libelle: 'Salaire de base', gain: 2000 },
        {
          libelle: 'Heures suppl. majorées à 25%',
          quantite: 16,
          explication: '16 h à 25 % : 4 h par semaine au-delà de 39 h, semaines 35 à 38',
        },
      ],
      details_absences: [
        {
          libelle: 'Absence arrêt maladie du 01/09 au 30/09',
          explication: 'Absence : arrêt maladie du 1er au 30/09',
        },
      ],
      details_conges: [{ libelle: 'Absence congés payés', perte: 100 }],
      structure_cotisations: {
        bloc_allegements: [
          {
            libelle: 'Réduction générale de cotisations patronales',
            explication: 'Réduction générale : régularisation depuis janvier',
          },
        ],
      },
    });
    expect(lignes.map((l) => l.libelle)).toEqual([
      'Heures suppl. majorées à 25%',
      'Absence arrêt maladie du 01/09 au 30/09',
      'Réduction générale de cotisations patronales',
    ]);
    expect(lignes.every((l) => l.explication.trim().length > 0)).toBe(true);
  });

  it('ne recalcule rien : sans explication côté bulletin, rien à afficher', () => {
    expect(
      lignesAvecExplication({
        calcul_du_brut: [{ libelle: 'Heures suppl. majorées à 25%', quantite: 8 }],
        details_absences: [{ libelle: 'Absence arrêt maladie du 01/09 au 30/09' }],
      })
    ).toEqual([]);
  });
});

describe('cadre « D’où viennent ces lignes » : chaque astérisque ouvre sa propre info-bulle', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../components/LignesExpliquees.tsx'),
    'utf8'
  );

  it('l’info-bulle d’une ligne ne retient pas le pointeur qui passe à la ligne suivante', () => {
    // Sans cela, l'info-bulle ouverte garde une zone de passage vers elle : le survol de
    // l'astérisque de la ligne du dessous reste sans réponse (cas des heures sup puis
    // de la réduction générale).
    expect(source).toMatch(/<Tooltip[^>]*\bdisableHoverableContent\b/);
  });

  it('seule une ligne expliquée porte l’astérisque', () => {
    expect(source).toContain('afficherAsterisque(ligne)');
  });
});
