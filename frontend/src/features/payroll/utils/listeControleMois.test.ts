import { describe, expect, it } from 'vitest';

import {
  MENTION_RIB_A_COMPLETER,
} from '@/features/employees/utils/creationSalarie';
import {
  ETAPE_ABSENCES,
  ETAPE_BULLETINS,
  ETAPE_CALENDRIERS,
  ETAPE_CONFLITS,
  ETAPE_DECLARATIONS,
  ETAPE_RIB,
  ETAPE_SORTIES,
  ETAPE_VALIDES,
  MESSAGE_ABSENCES_A_CONFIRMER,
  lectureCalendriersASaisir,
  lectureConflitsArret,
  listeControleDuMois,
  phraseListeControle,
  type ExportPourControle,
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

function exportFait(export_type: string, overrides: Partial<ExportPourControle> = {}): ExportPourControle {
  return {
    export_type,
    status: 'generated',
    generated_at: '2026-10-04T09:00:00Z',
    a_refaire: false,
    ...overrides,
  };
}

const DSN = exportFait('dsn_mensuelle');
const COMPTA = exportFait('od_globale');

function entree(overrides: Partial<EntreeListeControle> = {}): EntreeListeControle {
  return {
    year: 2026,
    month: 9,
    salaries: [JEANNE, PAUL],
    bulletinsParSalarie: OK({
      'e-1': [{ year: 2026, month: 9, a_recalculer: false, origine: 'calcule', status: 'valide' }],
      'e-2': [{ year: 2026, month: 9, a_recalculer: false, origine: 'calcule', status: 'valide' }],
    }),
    departs: OK([]),
    calendriersASaisir: OK([]),
    conflitsArret: OK([]),
    exportsDuMois: OK([DSN, COMPTA]),
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

  it('un salarié hors revue pré-paie (embauche en cours) : calendriers et conflits à confirmer', () => {
    const resultat = listeControleDuMois(
      entree({
        salaries: [{ ...JEANNE, employment_status: 'en_onboarding' }, PAUL],
        calendriersASaisir: OK([]),
        conflitsArret: OK([]),
      })
    );
    expect(etape(resultat, ETAPE_CALENDRIERS).etat).toBe('a_confirmer');
    expect(etape(resultat, ETAPE_CONFLITS).etat).toBe('a_confirmer');
  });

  it('un salarié en sortie est dans la revue pré-paie : ses calendriers et conflits comptent', () => {
    const resultat = listeControleDuMois(
      entree({
        salaries: [{ ...JEANNE, employment_status: 'en_sortie' }, PAUL],
        calendriersASaisir: OK([]),
        conflitsArret: OK([]),
      })
    );
    expect(etape(resultat, ETAPE_CALENDRIERS).etat).toBe('fait');
    expect(etape(resultat, ETAPE_CONFLITS).etat).toBe('fait');
  });

  it('liste des salariés illisible : calendriers, conflits, bulletins, sorties et RIB à confirmer', () => {
    const resultat = listeControleDuMois(
      entree({
        salaries: [],
        lectureSalaries: ERREUR,
        calendriersASaisir: OK(['e-1']),
        conflitsArret: OK(['e-1']),
        bulletinsParSalarie: OK({}),
        departs: OK([]),
      })
    );
    for (const id of [ETAPE_CALENDRIERS, ETAPE_CONFLITS, ETAPE_BULLETINS, ETAPE_SORTIES, ETAPE_RIB]) {
      expect(etape(resultat, id).etat, id).toBe('a_confirmer');
      expect(etape(resultat, id).etat, id).not.toBe('fait');
    }
  });

  it('une liste salariés vide lue avec succès peut encore être prouvée', () => {
    const resultat = listeControleDuMois(
      entree({
        salaries: [],
        lectureSalaries: OK([]),
        calendriersASaisir: OK([]),
        conflitsArret: OK([]),
        bulletinsParSalarie: OK({}),
        departs: OK([]),
      })
    );
    expect(etape(resultat, ETAPE_CALENDRIERS).etat).toBe('fait');
    expect(etape(resultat, ETAPE_CONFLITS).etat).toBe('fait');
    expect(etape(resultat, ETAPE_BULLETINS).etat).toBe('fait');
    expect(etape(resultat, ETAPE_SORTIES).etat).toBe('fait');
    expect(etape(resultat, ETAPE_RIB).etat).toBe('fait');
  });
});

describe('« c’est fini » : bulletins validés, DSN et export comptable faits — revue du 05/10', () => {
  it('tous les bulletins validés : fait', () => {
    expect(etape(listeControleDuMois(entree()), ETAPE_VALIDES).etat).toBe('fait');
  });

  it('un brouillon ou un bulletin manquant reste à valider', () => {
    const resultat = listeControleDuMois(
      entree({
        bulletinsParSalarie: OK({
          'e-1': [{ year: 2026, month: 9, a_recalculer: false, origine: 'calcule', status: 'brouillon' }],
        }),
      })
    );
    const valides = etape(resultat, ETAPE_VALIDES);
    expect(valides.etat).toBe('a_faire');
    expect(valides.detail).toBe('2 bulletins restent à valider.');
    const action = resultat.actions.find((a) => a.id === ETAPE_VALIDES);
    expect(action?.href).toBe('/payroll?view=month&month=2026-09');
    expect(action?.ensuite).toContain('Valider les bulletins prêts');
  });

  it('un bulletin repris de l’ancien logiciel ne se valide pas : il compte comme fait', () => {
    const resultat = listeControleDuMois(
      entree({
        bulletinsParSalarie: OK({
          'e-1': [{ year: 2026, month: 9, origine: 'importe', status: null }],
          'e-2': [{ year: 2026, month: 9, origine: 'calcule', status: 'valide' }],
        }),
      })
    );
    expect(etape(resultat, ETAPE_VALIDES).etat).toBe('fait');
  });

  it('bulletins illisibles : validés à confirmer, jamais cochés', () => {
    expect(etape(listeControleDuMois(entree({ bulletinsParSalarie: ERREUR })), ETAPE_VALIDES).etat).toBe(
      'a_confirmer'
    );
  });

  it('DSN et export comptable du mois générés : fait', () => {
    expect(etape(listeControleDuMois(entree()), ETAPE_DECLARATIONS).etat).toBe('fait');
    const quadra = listeControleDuMois(
      entree({ exportsDuMois: OK([DSN, exportFait('export_cabinet_quadra')]) })
    );
    expect(etape(quadra, ETAPE_DECLARATIONS).etat).toBe('fait');
  });

  it('il manque l’un ou l’autre : à faire, en disant lequel', () => {
    const sansCompta = etape(listeControleDuMois(entree({ exportsDuMois: OK([DSN]) })), ETAPE_DECLARATIONS);
    expect(sansCompta.etat).toBe('a_faire');
    expect(sansCompta.detail).toBe('L’export comptable du mois n’est pas fait.');

    const rien = etape(listeControleDuMois(entree({ exportsDuMois: OK([]) })), ETAPE_DECLARATIONS);
    expect(rien.detail).toBe('La DSN du mois n’est pas faite. L’export comptable du mois n’est pas fait.');
  });

  it('un journal de paie ou un export annulé ne compte pas', () => {
    const resultat = listeControleDuMois(
      entree({
        exportsDuMois: OK([exportFait('journal_paie'), exportFait('dsn_mensuelle', { status: 'cancelled' }), COMPTA]),
      })
    );
    expect(etape(resultat, ETAPE_DECLARATIONS).detail).toBe('La DSN du mois n’est pas faite.');
  });

  it('un export fait avant le dernier calcul est à refaire', () => {
    const resultat = listeControleDuMois(
      entree({ exportsDuMois: OK([exportFait('dsn_mensuelle', { a_refaire: true }), COMPTA]) })
    );
    const declarations = etape(resultat, ETAPE_DECLARATIONS);
    expect(declarations.etat).toBe('a_faire');
    expect(declarations.detail).toBe('La DSN est à refaire : un bulletin du mois a changé depuis.');
    expect(resultat.actions.find((a) => a.id === ETAPE_DECLARATIONS)?.href).toBe('/exports');
  });

  it('historique des exports illisible ou non lu : à confirmer', () => {
    expect(etape(listeControleDuMois(entree({ exportsDuMois: ERREUR })), ETAPE_DECLARATIONS).etat).toBe(
      'a_confirmer'
    );
    expect(
      etape(listeControleDuMois(entree({ exportsDuMois: undefined })), ETAPE_DECLARATIONS).etat
    ).toBe('a_confirmer');
  });

  it('tout est fait : la liste dit que la paie du mois est terminée', () => {
    expect(phraseListeControle(listeControleDuMois(entree()))).toBe(
      'Paie du mois terminée : bulletins validés, DSN et export comptable faits. Confirmez vous-même que les absences étaient toutes saisies.'
    );
  });

  it('sinon, elle compte ce qui reste', () => {
    expect(phraseListeControle(listeControleDuMois(entree({ exportsDuMois: OK([DSN]) })))).toBe(
      '1 point à traiter, d’après les données.'
    );
    expect(
      phraseListeControle(listeControleDuMois(entree({ exportsDuMois: OK([]), bulletinsParSalarie: OK({}) })))
    ).toBe('3 points à traiter, d’après les données.');
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
