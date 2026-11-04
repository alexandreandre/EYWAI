import { describe, expect, it } from 'vitest';
import {
  dateDuJourAParis,
  jourDeMiseADisposition,
  ligneBulletinsDeSortie,
  phraseRemiseALaValidation,
  remiseALaValidation,
  textesRemiseDuLot,
} from './remiseALaValidation';

const OCTOBRE = { annee: 2026, mois: 10 };

describe('le jour réglé par la société, lu comme le serveur', () => {
  it('sans réglage, le 1er du mois suivant', () => {
    expect(jourDeMiseADisposition({})).toBe(1);
    expect(jourDeMiseADisposition({ bulletins_mise_a_disposition_jour: null })).toBe(1);
  });

  it('0 = dès la validation ; au-delà de 28, le 28 ; négatif, booléen ou illisible : le 1er', () => {
    expect(jourDeMiseADisposition({ bulletins_mise_a_disposition_jour: 0 })).toBe(0);
    expect(jourDeMiseADisposition({ bulletins_mise_a_disposition_jour: 5 })).toBe(5);
    expect(jourDeMiseADisposition({ bulletins_mise_a_disposition_jour: '3' })).toBe(3);
    expect(jourDeMiseADisposition({ bulletins_mise_a_disposition_jour: 35 })).toBe(28);
    expect(jourDeMiseADisposition({ bulletins_mise_a_disposition_jour: -2 })).toBe(1);
    expect(jourDeMiseADisposition({ bulletins_mise_a_disposition_jour: true })).toBe(1);
    expect(jourDeMiseADisposition({ bulletins_mise_a_disposition_jour: 'le 5' })).toBe(1);
  });

  it('réglages de la société introuvables : aucun jour', () => {
    expect(jourDeMiseADisposition(undefined)).toBeNull();
    expect(jourDeMiseADisposition(null)).toBeNull();
  });
});

describe('le jour de Paris', () => {
  it('passe minuit à Paris avant Londres', () => {
    expect(dateDuJourAParis(new Date('2026-11-03T23:30:00Z'))).toBe('2026-11-04');
    expect(dateDuJourAParis(new Date('2026-11-03T22:59:00Z'))).toBe('2026-11-03');
    expect(dateDuJourAParis(new Date('2026-07-01T22:00:00Z'))).toBe('2026-07-02');
  });
});

describe('ce que promet la validation d’octobre', () => {
  it('validés avant la date : visibles le 1er novembre, encore corrigeables', () => {
    const remise = remiseALaValidation({ ...OCTOBRE, jour: 1, aujourdhui: '2026-10-30' });
    expect(remise).toEqual({ cas: 'plus_tard', remisLe: '2026-11-01' });
    expect(phraseRemiseALaValidation(remise, { ...OCTOBRE, nombre: 12 })).toBe(
      'Visibles par les salariés le 1er novembre. Jusque-là, vous pouvez encore les corriger.',
    );
  });

  it('validés après la date (le 4 novembre) : visibles et figés tout de suite', () => {
    const remise = remiseALaValidation({ ...OCTOBRE, jour: 1, aujourdhui: '2026-11-04' });
    expect(remise).toEqual({ cas: 'des_maintenant' });
    expect(phraseRemiseALaValidation(remise, { ...OCTOBRE, nombre: 12 })).toBe(
      'Visibles par les salariés dès maintenant, et figés : une erreur se corrigera sur le bulletin de novembre, par une régularisation.',
    );
  });

  it('validés le jour même de la remise : visibles tout de suite', () => {
    expect(remiseALaValidation({ ...OCTOBRE, jour: 4, aujourdhui: '2026-11-04' })).toEqual({
      cas: 'des_maintenant',
    });
    expect(remiseALaValidation({ ...OCTOBRE, jour: 5, aujourdhui: '2026-11-04' })).toEqual({
      cas: 'plus_tard',
      remisLe: '2026-11-05',
    });
  });

  it('réglage « dès la validation » (jour 0) : visibles tout de suite, même en avance', () => {
    expect(remiseALaValidation({ ...OCTOBRE, jour: 0, aujourdhui: '2026-10-25' })).toEqual({
      cas: 'des_maintenant',
    });
  });

  it('réglage introuvable : aucune date promise', () => {
    const remise = remiseALaValidation({ ...OCTOBRE, jour: null, aujourdhui: '2026-11-04' });
    expect(remise).toEqual({ cas: 'inconnue' });
    const phrase = phraseRemiseALaValidation(remise, { ...OCTOBRE, nombre: 3 });
    expect(phrase).toBe(
      'Visibles par les salariés à la date de mise à disposition de la société (onglet « Paramètres paie ») ; à partir de cette date, ils ne se modifient plus.',
    );
    expect(phrase).not.toMatch(/\d/);
  });

  it('un seul bulletin : le singulier', () => {
    expect(
      phraseRemiseALaValidation({ cas: 'plus_tard', remisLe: '2026-11-05' }, { ...OCTOBRE, nombre: 1 }),
    ).toBe('Visible par le salarié le 5 novembre. Jusque-là, vous pouvez encore le corriger.');
    expect(phraseRemiseALaValidation({ cas: 'des_maintenant' }, { ...OCTOBRE, nombre: 1 })).toContain(
      'Visible par le salarié dès maintenant, et figé',
    );
  });
});

describe('décembre se remet en janvier de l’année suivante', () => {
  const DECEMBRE = { annee: 2026, mois: 12 };

  it('avant la date : le 5 janvier 2027', () => {
    const remise = remiseALaValidation({ ...DECEMBRE, jour: 5, aujourdhui: '2026-12-28' });
    expect(remise).toEqual({ cas: 'plus_tard', remisLe: '2027-01-05' });
    expect(phraseRemiseALaValidation(remise, { ...DECEMBRE, nombre: 2 })).toBe(
      'Visibles par les salariés le 5 janvier 2027. Jusque-là, vous pouvez encore les corriger.',
    );
  });

  it('après la date : corrigé sur le bulletin de janvier 2027', () => {
    const remise = remiseALaValidation({ ...DECEMBRE, jour: 1, aujourdhui: '2027-01-04' });
    expect(phraseRemiseALaValidation(remise, { ...DECEMBRE, nombre: 2 })).toContain(
      'sur le bulletin de janvier 2027, par une régularisation.',
    );
  });

  it('mars se corrige sur le bulletin d’avril', () => {
    const remise = remiseALaValidation({ annee: 2027, mois: 3, jour: 1, aujourdhui: '2027-04-02' });
    expect(phraseRemiseALaValidation(remise, { annee: 2027, mois: 3, nombre: 2 })).toContain(
      "sur le bulletin d'avril, par une régularisation.",
    );
  });
});

describe('les bulletins de sortie du lot, visibles dès leur validation', () => {
  it('une ligne les nomme', () => {
    expect(ligneBulletinsDeSortie([])).toBeNull();
    expect(ligneBulletinsDeSortie(['Ève Exemple'])).toBe(
      "Le bulletin de sortie d'Ève Exemple est visible dès sa validation, et figé.",
    );
    expect(ligneBulletinsDeSortie(['Paul Exemple', 'Ève Exemple', 'Luc Exemple'])).toBe(
      'Les bulletins de sortie de Paul Exemple, Ève Exemple et Luc Exemple sont visibles dès leur validation, et figés.',
    );
  });

  it('la phrase de date ne compte que les autres bulletins', () => {
    const textes = textesRemiseDuLot({
      ...OCTOBRE,
      jour: 1,
      aujourdhui: '2026-10-30',
      nombre: 3,
      sorties: ['Paul Exemple'],
    });
    expect(textes.phrase).toBe(
      'Visibles par les salariés le 1er novembre. Jusque-là, vous pouvez encore les corriger.',
    );
    expect(textes.ligneSortie).toBe(
      'Le bulletin de sortie de Paul Exemple est visible dès sa validation, et figé.',
    );
  });

  it('un lot fait seulement de bulletins de sortie : pas de date', () => {
    const textes = textesRemiseDuLot({
      ...OCTOBRE,
      jour: 1,
      aujourdhui: '2026-10-30',
      nombre: 1,
      sorties: ['Paul Exemple'],
    });
    expect(textes.phrase).toBeNull();
    expect(textes.ligneSortie).not.toBeNull();
  });
});
