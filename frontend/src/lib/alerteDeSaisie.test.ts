import { describe, expect, it } from 'vitest';
import { alerteDeSaisie } from './alerteDeSaisie';

describe('alerte de saisie d’une ligne du calendrier (retour du 10/11)', () => {
  it('nomme les jours qui bloquent et dit comment passer outre', () => {
    const alerte = alerteDeSaisie(
      {
        rowStatus: 'a_saisir',
        joursASaisir: [
          { jour: 27, motif: 'prevu_sans_reel' },
          { jour: 28, motif: 'prevu_sans_reel' },
        ],
        dernierJourJuge: null,
        dernierJourContrat: null,
      },
      2026,
      10,
    );
    expect(alerte?.jours).toBe('27/10–28/10 (heures réelles non saisies)');
    expect(alerte?.detail).toContain('Générer quand même');
  });

  it('dit que les jours après l’arrêté des variables comptent pour le mois suivant', () => {
    const alerte = alerteDeSaisie(
      { rowStatus: 'saisi', joursASaisir: [], dernierJourJuge: 25, dernierJourContrat: null },
      2026,
      10,
    );
    expect(alerte).toBeNull();
    const bornes = alerteDeSaisie(
      {
        rowStatus: 'a_saisir',
        joursASaisir: [{ jour: 3, motif: 'prevu_sans_heures' }],
        dernierJourJuge: 25,
        dernierJourContrat: null,
      },
      2026,
      10,
    );
    expect(bornes?.detail).toContain('après le 25/10');
  });

  it('dit la sortie quand elle borne le mois', () => {
    const alerte = alerteDeSaisie(
      {
        rowStatus: 'a_saisir',
        joursASaisir: [{ jour: 1, motif: 'prevu_sans_reel' }],
        dernierJourJuge: 2,
        dernierJourContrat: 2,
      },
      2026,
      10,
    );
    expect(alerte?.detail).toContain('sortie le 02/10');
  });

  it('une ligne saisie n’a pas d’alerte', () => {
    expect(
      alerteDeSaisie(
        { rowStatus: 'saisi', joursASaisir: [], dernierJourJuge: null, dernierJourContrat: null },
        2026,
        10,
      ),
    ).toBeNull();
  });
});
