import { describe, expect, it } from 'vitest';
import {
  dateCourte,
  datesRetenues,
  erreurDePeriode,
  isoDuJourLocal,
  jourDeLaSemaine,
  jourLocalDeIso,
  moisDesDates,
} from './joursEnMasse';

const VENDREDI = 4;

describe('datesRetenues', () => {
  it('tous les vendredis du 01/12 au 31/12', () => {
    expect(
      datesRetenues({ du: '2026-12-01', au: '2026-12-31', joursSemaine: [VENDREDI], datesCliquees: [] }),
    ).toEqual(['2026-12-04', '2026-12-11', '2026-12-18', '2026-12-25']);
  });

  it('les bornes de la période sont comprises', () => {
    expect(
      datesRetenues({ du: '2026-12-04', au: '2026-12-11', joursSemaine: [VENDREDI], datesCliquees: [] }),
    ).toEqual(['2026-12-04', '2026-12-11']);
  });

  it('plusieurs jours de la semaine, sur deux mois et le passage à l’heure d’hiver', () => {
    expect(
      datesRetenues({ du: '2026-10-23', au: '2026-11-03', joursSemaine: [0, 4], datesCliquees: [] }),
    ).toEqual(['2026-10-23', '2026-10-26', '2026-10-30', '2026-11-02']);
  });

  it('aucun jour coché : la période seule ne donne rien', () => {
    expect(datesRetenues({ du: '2026-12-01', au: '2026-12-31', joursSemaine: [], datesCliquees: [] })).toEqual([]);
  });

  it('les dates cliquées s’ajoutent, sans doublon, triées', () => {
    expect(
      datesRetenues({
        du: '2026-12-01',
        au: '2026-12-15',
        joursSemaine: [VENDREDI],
        datesCliquees: ['2026-12-23', '2026-12-11', '2026-12-02'],
      }),
    ).toEqual(['2026-12-02', '2026-12-04', '2026-12-11', '2026-12-23']);
  });

  it('des dates cliquées sans période', () => {
    expect(datesRetenues({ du: '', au: '', joursSemaine: [VENDREDI], datesCliquees: ['2026-12-24'] })).toEqual([
      '2026-12-24',
    ]);
  });

  it('une période à l’envers ou illisible ne donne rien', () => {
    expect(datesRetenues({ du: '2026-12-31', au: '2026-12-01', joursSemaine: [VENDREDI], datesCliquees: [] })).toEqual(
      [],
    );
    expect(datesRetenues({ du: '2026-02-30', au: '2026-03-31', joursSemaine: [VENDREDI], datesCliquees: ['x'] })).toEqual(
      [],
    );
  });
});

describe('erreurDePeriode', () => {
  it('dit ce qui manque ou ce qui ne va pas', () => {
    expect(erreurDePeriode('', '')).toBeNull();
    expect(erreurDePeriode('2026-12-01', '')).toBe('Indiquez le début et la fin de la période.');
    expect(erreurDePeriode('2026-12-31', '2026-12-01')).toBe('La fin de la période est avant son début.');
    expect(erreurDePeriode('2026-12-01', '2026-12-31')).toBeNull();
  });
});

describe('outils de dates', () => {
  it('jour de la semaine, lundi = 0', () => {
    expect(jourDeLaSemaine('2026-12-04')).toBe(4);
    expect(jourDeLaSemaine('2026-12-07')).toBe(0);
    expect(jourDeLaSemaine('2026-12-06')).toBe(6);
  });

  it('mois couverts', () => {
    expect(moisDesDates(['2026-12-04', '2026-11-27', '2026-12-11'])).toEqual([
      { year: 2026, month: 11 },
      { year: 2026, month: 12 },
    ]);
  });

  it('date courte et aller-retour avec le calendrier', () => {
    expect(dateCourte('2026-12-04')).toBe('ven. 04/12/2026');
    expect(isoDuJourLocal(jourLocalDeIso('2026-12-04'))).toBe('2026-12-04');
  });
});
