import { describe, expect, it } from 'vitest';
import { horairesAEnvoyer, horairesSaisis, libelleArrivee, lireHeure, noteHorairesJourNonTravaille } from './horairesDuJour';

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

  it('un jour non travaillé efface les horaires, et le dit', () => {
    expect(horairesSaisis({ arrivee: '07:00', depart: '15:00', heuresFaites: '0', travaille: false })).toEqual({
      horaires: { debut: null, fin: null },
    });
    expect(noteHorairesJourNonTravaille('07:00', '')).toBe(
      'Jour non travaillé : l’arrivée (07:00) sera effacée à l’enregistrement.',
    );
    expect(noteHorairesJourNonTravaille('07:00', '15:00')).toBe(
      'Jour non travaillé : l’arrivée (07:00) et le départ (15:00) seront effacés à l’enregistrement.',
    );
    expect(noteHorairesJourNonTravaille('', '')).toBeNull();
  });
});

describe('affichage et enregistrement', () => {
  it('la case dit l’arrivée', () => {
    expect(libelleArrivee({ debut: '07:00' })).toBe('Arrivée 07:00');
    expect(libelleArrivee({ debut: null })).toBeNull();
    expect(libelleArrivee(undefined)).toBeNull();
  });

  it('le calendrier du mois renvoie l’arrivée qu’il connaît (gardée à la main), sans le départ', () => {
    expect(
      horairesAEnvoyer([{ jour: 1, type: 'travail', heures_faites: 6, debut: '07:00', fin: '14:00' }]),
    ).toEqual([{ jour: 1, type: 'travail', heures_faites: 6, debut: '07:00' }]);
  });

  it('une arrivée vidée part vide, pour que le serveur l’efface', () => {
    expect(
      horairesAEnvoyer([{ jour: 2, type: 'travail', heures_faites: null, debut: null, fin: null }]),
    ).toEqual([{ jour: 2, type: 'travail', heures_faites: null, debut: null, fin: null }]);
  });

  it('un jour sans horaire n’en envoie pas', () => {
    expect(horairesAEnvoyer([{ jour: 3, type: 'travail', heures_faites: 7 }])).toEqual([
      { jour: 3, type: 'travail', heures_faites: 7 },
    ]);
  });
});

describe('lireHeure : une heure tapée au clavier, quel que soit le navigateur (e2e 38 du 27/11)', () => {
  it('accepte les façons courantes de l’écrire', () => {
    for (const saisie of ['7', '7h', '07h00', '7:00', '07:00', '700', '0700', ' 7 h ']) {
      expect(lireHeure(saisie)).toBe('07:00');
    }
    expect(lireHeure('13h30')).toBe('13:30');
    expect(lireHeure('4h05')).toBe('04:05');
  });

  it('vide : pas d’heure ; illisible : signalé', () => {
    expect(lireHeure('')).toBeNull();
    expect(lireHeure('25:00')).toBe('illisible');
    expect(lireHeure('7:75')).toBe('illisible');
    expect(lireHeure('sept heures')).toBe('illisible');
  });

  it('une heure illisible n’est jamais jetée en silence', () => {
    expect(horairesSaisis({ arrivee: '7:75', depart: '', heuresFaites: '7', travaille: true })).toEqual({
      refus: 'Heure d’arrivée illisible : tapez par exemple 07:00 ou 7h.',
    });
    expect(horairesSaisis({ arrivee: '7h', depart: '1530', heuresFaites: '7', travaille: true })).toEqual({
      horaires: { debut: '07:00', fin: '15:30' },
    });
  });
});
