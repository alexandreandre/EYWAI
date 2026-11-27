import { describe, expect, it } from 'vitest';
import { horairesSaisis, libelleArrivee, sansHoraires } from './horairesDuJour';

describe('horairesSaisis (éditeur du jour)', () => {
  it('une arrivée saisie part avec les heures faites', () => {
    expect(horairesSaisis({ arrivee: '07:00', depart: '', heuresFaites: '7', travaille: true })).toEqual({
      horaires: { debut: '07:00', fin: null },
    });
  });

  it('des champs vides effacent les horaires', () => {
    expect(horairesSaisis({ arrivee: '', depart: '', heuresFaites: '7', travaille: true })).toEqual({
      horaires: { debut: null, fin: null },
    });
  });

  it('une arrivée sans heures faites est refusée, avec la raison', () => {
    expect(horairesSaisis({ arrivee: '07:00', depart: '', heuresFaites: '', travaille: true })).toEqual({
      refus: 'Saisissez les heures faites : l’heure d’arrivée n’est gardée que sur un jour travaillé.',
    });
  });

  it('un jour non travaillé n’envoie aucun horaire', () => {
    expect(horairesSaisis({ arrivee: '07:00', depart: '15:00', heuresFaites: '0', travaille: false })).toEqual({
      horaires: { debut: null, fin: null },
    });
  });
});

describe('affichage et enregistrement', () => {
  it('la case dit l’arrivée', () => {
    expect(libelleArrivee({ debut: '07:00' })).toBe('Arrivée 07:00');
    expect(libelleArrivee({ debut: null })).toBeNull();
    expect(libelleArrivee(undefined)).toBeNull();
  });

  it('le calendrier du mois n’envoie pas les horaires qu’il n’a pas changés', () => {
    expect(
      sansHoraires([{ jour: 1, type: 'travail', heures_faites: 7, debut: '07:00', fin: '14:00' }]),
    ).toEqual([{ jour: 1, type: 'travail', heures_faites: 7 }]);
  });
});
