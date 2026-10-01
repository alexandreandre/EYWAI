import { describe, expect, it } from 'vitest';

import {
  MENTION_RIB_A_COMPLETER,
} from '@/features/employees/utils/creationSalarie';
import {
  ETAPE_ABSENCES,
  ETAPE_BULLETINS,
  ETAPE_CALENDRIERS,
  ETAPE_CONFLITS,
  ETAPE_RIB,
  ETAPE_SORTIES,
  MESSAGE_ABSENCES_A_CONFIRMER,
  lectureCalendriersASaisir,
  lectureConflitsArret,
  listeControleDuMois,
  type EntreeListeControle,
  type Lecture,
} from './listeControleMois';

const OK = <T>(valeur: T): Lecture<T> => ({ statut: 'ok', valeur });
const CHARGEMENT: Lecture<never> = { statut: 'chargement' };
const ERREUR: Lecture<never> = { statut: 'erreur' };
const INDISPONIBLE: Lecture<never> = { statut: 'indisponible' };

const JEANNE = {
  id: 'e-1',
  first_name: 'Jeanne',
  last_name: 'Essai',
  hire_date: '2020-01-15',
};

const PAUL = {
  id: 'e-2',
  first_name: 'Paul',
  last_name: 'Essai',
  hire_date: '2019-03-01',
};

function entree(overrides: Partial<EntreeListeControle> = {}): EntreeListeControle {
  return {
    year: 2026,
    month: 9,
    salaries: [JEANNE, PAUL],
    bulletinsParSalarie: OK({
      'e-1': [{ year: 2026, month: 9, a_recalculer: false, origine: 'calcule' }],
      'e-2': [{ year: 2026, month: 9, a_recalculer: false, origine: 'calcule' }],
    }),
    departs: OK([]),
    calendriersASaisir: OK([]),
    conflitsArret: OK([]),
    ...overrides,
  };
}

function etape(resultat: ReturnType<typeof listeControleDuMois>, id: string) {
  const trouvee = resultat.etapes.find((e) => e.id === id);
  expect(trouvee, `étape ${id}`).toBeDefined();
  return trouvee!;
}

describe('listeControleDuMois — pas de coche verte sans preuve', () => {
  it('coche les étapes prouvées et laisse les absences à confirmer', () => {
    const resultat = listeControleDuMois(entree());
    expect(etape(resultat, ETAPE_CALENDRIERS).etat).toBe('fait');
    expect(etape(resultat, ETAPE_CONFLITS).etat).toBe('fait');
    expect(etape(resultat, ETAPE_BULLETINS).etat).toBe('fait');
    expect(etape(resultat, ETAPE_SORTIES).etat).toBe('fait');
    expect(etape(resultat, ETAPE_RIB).etat).toBe('fait');
    expect(etape(resultat, ETAPE_ABSENCES).etat).toBe('a_confirmer');
    expect(etape(resultat, ETAPE_ABSENCES).detail).toBe(MESSAGE_ABSENCES_A_CONFIRMER);
  });

  it('n’affiche jamais les absences comme faites, même sans anomalie', () => {
    const resultat = listeControleDuMois(entree());
    expect(etape(resultat, ETAPE_ABSENCES).etat).not.toBe('fait');
    expect(resultat.actions.some((a) => a.id.startsWith('absences'))).toBe(true);
  });

  it('calendriers incomplets (periode_a_saisir) : à faire, pas faits', () => {
    const resultat = listeControleDuMois(
      entree({ calendriersASaisir: OK(['e-1']) })
    );
    expect(etape(resultat, ETAPE_CALENDRIERS).etat).toBe('a_faire');
  });

  it('calendriers illisibles : à confirmer, jamais une coche verte', () => {
    expect(etape(listeControleDuMois(entree({ calendriersASaisir: ERREUR })), ETAPE_CALENDRIERS).etat).toBe(
      'a_confirmer'
    );
    expect(
      etape(listeControleDuMois(entree({ calendriersASaisir: CHARGEMENT })), ETAPE_CALENDRIERS).etat
    ).not.toBe('fait');
  });

  it('conflit arrêt/heures (A2) : à faire', () => {
    const resultat = listeControleDuMois(entree({ conflitsArret: OK(['e-2']) }));
    expect(etape(resultat, ETAPE_CONFLITS).etat).toBe('a_faire');
  });

  it('conflits indisponibles : à confirmer, pas une liste vide prise pour « aucun »', () => {
    expect(
      etape(listeControleDuMois(entree({ conflitsArret: INDISPONIBLE })), ETAPE_CONFLITS).etat
    ).toBe('a_confirmer');
    expect(
      etape(listeControleDuMois(entree({ conflitsArret: ERREUR })), ETAPE_CONFLITS).etat
    ).toBe('a_confirmer');
  });

  it('un bulletin manquant du mois : à faire', () => {
    const resultat = listeControleDuMois(
      entree({
        bulletinsParSalarie: OK({
          'e-1': [{ year: 2026, month: 9, a_recalculer: false, origine: 'calcule' }],
        }),
      })
    );
    expect(etape(resultat, ETAPE_BULLETINS).etat).toBe('a_faire');
  });

  it('seul a_recalculer true compte comme périmé (A5)', () => {
    const base = {
      'e-1': [{ year: 2026, month: 9, a_recalculer: null, origine: 'calcule' }],
      'e-2': [{ year: 2026, month: 9, a_recalculer: false, origine: 'calcule' }],
    };
    expect(
      etape(listeControleDuMois(entree({ bulletinsParSalarie: OK(base) })), ETAPE_BULLETINS).etat
    ).toBe('fait');

    const perime = {
      ...base,
      'e-1': [{ year: 2026, month: 9, a_recalculer: true, origine: 'calcule' }],
    };
    expect(
      etape(listeControleDuMois(entree({ bulletinsParSalarie: OK(perime) })), ETAPE_BULLETINS).etat
    ).toBe('a_faire');
  });

  it('un bulletin repris ne se marque pas à recalculer', () => {
    const resultat = listeControleDuMois(
      entree({
        bulletinsParSalarie: OK({
          'e-1': [{ year: 2026, month: 9, a_recalculer: true, origine: 'importe' }],
          'e-2': [{ year: 2026, month: 9, a_recalculer: false, origine: 'calcule' }],
        }),
      })
    );
    expect(etape(resultat, ETAPE_BULLETINS).etat).toBe('fait');
  });

  it('un salarié hors période d’emploi n’exige pas de bulletin ce mois-ci', () => {
    const resultat = listeControleDuMois(
      entree({
        salaries: [
          JEANNE,
          { ...PAUL, hire_date: '2026-10-01' },
        ],
        bulletinsParSalarie: OK({
          'e-1': [{ year: 2026, month: 9, a_recalculer: false, origine: 'calcule' }],
        }),
      })
    );
    expect(etape(resultat, ETAPE_BULLETINS).etat).toBe('fait');
  });

  it('une fin de contrat dans le mois, sans départ : sorties à faire (B1)', () => {
    const resultat = listeControleDuMois(
      entree({
        salaries: [{ ...JEANNE, contract_end_date: '2026-09-15' }, PAUL],
        departs: OK([]),
      })
    );
    expect(etape(resultat, ETAPE_SORTIES).etat).toBe('a_faire');
  });

  it('un départ créé pour cette fin de contrat : sorties faites', () => {
    const resultat = listeControleDuMois(
      entree({
        salaries: [{ ...JEANNE, contract_end_date: '2026-09-15', current_exit_id: 'exit-1' }, PAUL],
        departs: OK([
          { employee_id: 'e-1', last_working_day: '2026-09-15', status: 'demission_effective' },
        ]),
      })
    );
    expect(etape(resultat, ETAPE_SORTIES).etat).toBe('fait');
  });

  it('un dernier jour travaillé hors du mois affiché ne compte pas', () => {
    const resultat = listeControleDuMois(
      entree({
        salaries: [{ ...JEANNE, contract_end_date: '2026-08-31' }, PAUL],
        departs: OK([]),
      })
    );
    expect(etape(resultat, ETAPE_SORTIES).etat).toBe('fait');
  });

  it('départs illisibles : à confirmer, pas « aucune sortie »', () => {
    expect(etape(listeControleDuMois(entree({ departs: ERREUR })), ETAPE_SORTIES).etat).toBe(
      'a_confirmer'
    );
  });

  it('RIB manquant via missing_payroll_fields (A6), pas un autre champ', () => {
    const avecRib = listeControleDuMois(
      entree({
        salaries: [
          { ...JEANNE, missing_payroll_fields: ['Coordonnées bancaires (RIB)'] },
          PAUL,
        ],
      })
    );
    expect(etape(avecRib, ETAPE_RIB).etat).toBe('a_faire');
    expect(etape(avecRib, ETAPE_RIB).detail).toContain(MENTION_RIB_A_COMPLETER);

    const autreChamp = listeControleDuMois(
      entree({
        salaries: [
          { ...JEANNE, missing_payroll_fields: ['Numéro de sécurité sociale'] },
          PAUL,
        ],
      })
    );
    expect(etape(autreChamp, ETAPE_RIB).etat).toBe('fait');
  });

  it('un salarié hors actifs n’est pas dans la revue pré-paie : calendriers et conflits à confirmer', () => {
    const resultat = listeControleDuMois(
      entree({
        salaries: [{ ...JEANNE, employment_status: 'en_sortie' }, PAUL],
        calendriersASaisir: OK([]),
        conflitsArret: OK([]),
      })
    );
    expect(etape(resultat, ETAPE_CALENDRIERS).etat).toBe('a_confirmer');
    expect(etape(resultat, ETAPE_CONFLITS).etat).toBe('a_confirmer');
  });
});

describe('actions en attente', () => {
  it('chaque étape non cochée devient une ligne : quoi, où cliquer, ce qu’elle doit voir', () => {
    const resultat = listeControleDuMois(
      entree({
        calendriersASaisir: OK(['e-1']),
        conflitsArret: OK(['e-1']),
        bulletinsParSalarie: OK({}),
        salaries: [
          { ...JEANNE, contract_end_date: '2026-09-15', missing_payroll_fields: ['Coordonnées bancaires (RIB)'] },
        ],
        departs: OK([]),
      })
    );
    const ids = resultat.actions.map((a) => a.id);
    expect(ids).toEqual(
      expect.arrayContaining([
        'calendriers',
        'conflits',
        'absences',
        'bulletins',
        'sorties',
        'rib',
      ])
    );
    for (const action of resultat.actions) {
      expect(action.quoi.length).toBeGreaterThan(8);
      expect(action.ouCliquer.length).toBeGreaterThan(2);
      expect(action.href.startsWith('/')).toBe(true);
      expect(action.ensuite.length).toBeGreaterThan(8);
    }
  });

  it('ne recopie aucun nom de salarié dans les textes', () => {
    const resultat = listeControleDuMois(
      entree({
        calendriersASaisir: OK(['e-1']),
        salaries: [{ ...JEANNE, contract_end_date: '2026-09-15' }],
        departs: OK([]),
      })
    );
    const textes = [
      ...resultat.etapes.map((e) => `${e.libelle} ${e.detail}`),
      ...resultat.actions.map((a) => `${a.quoi} ${a.ouCliquer} ${a.ensuite}`),
    ].join(' ');
    expect(textes).not.toMatch(/Jeanne|Paul|Essai/i);
  });

  it('une étape faite n’a pas d’action', () => {
    const resultat = listeControleDuMois(entree());
    expect(resultat.actions.map((a) => a.id)).toEqual(['absences']);
  });
});

describe('lecture des anomalies pré-paie', () => {
  it('calendriers : jours_manquants, même justifiés — pas la résolution', () => {
    expect(
      lectureCalendriersASaisir({
        chargement: false,
        erreur: false,
        anomalies: [
          {
            type: 'heures_non_saisies',
            status: 'justifie',
            employee_id: 'e-1',
            jours_manquants: ['2026-09-07'],
          },
          {
            type: 'heures_non_saisies',
            status: 'a_traiter',
            employee_id: 'e-2',
            jours_manquants: [],
          },
          {
            type: 'ecart_heures',
            status: 'a_traiter',
            employee_id: 'e-3',
            jours_manquants: ['2026-09-01'],
          },
        ],
      })
    ).toEqual(OK(['e-1']));
  });

  it('calendriers en erreur : pas une liste vide', () => {
    expect(lectureCalendriersASaisir({ chargement: false, erreur: true })).toEqual(ERREUR);
    expect(lectureCalendriersASaisir({ chargement: true, erreur: false })).toEqual(CHARGEMENT);
  });

  it('conflits : champ absent = indisponible, pas « aucun conflit »', () => {
    expect(lectureConflitsArret({ chargement: false, erreur: false })).toEqual(INDISPONIBLE);
    expect(
      lectureConflitsArret({
        chargement: false,
        erreur: false,
        heures_sur_arret: [],
      })
    ).toEqual(OK([]));
    expect(
      lectureConflitsArret({
        chargement: false,
        erreur: false,
        heures_sur_arret: [{ employee_id: 'e-1', jours: [{ jour: 7 }] }],
      })
    ).toEqual(OK(['e-1']));
  });
});
