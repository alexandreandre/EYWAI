import { describe, expect, it } from 'vitest';
import type { PayrollVariableRule } from '@/api/payrollVariables';
import {
  MODELES_PRIMES_POINTAGE,
  direPlage,
  erreurDeLaRegle,
  montantIgnore,
  phraseJoursDuSalarie,
  phraseJoursSansHeureDArrivee,
  plageAutourDe,
  trierLaSimulation,
} from './primesPointage';

const regle = (r: Partial<PayrollVariableRule>): PayrollVariableRule => ({
  code: 'x',
  label: 'X',
  enabled: true,
  rule_type: 'per_worked_day',
  amount: 10,
  conditions: {},
  generation_mode: 'auto',
  sort_order: 0,
  ...r,
});

describe('plageAutourDe', () => {
  it('« 4 » donne le poste de 4 h, une heure de chaque côté', () => {
    expect(plageAutourDe('4')).toEqual({ de: '03:00', a: '05:00' });
    expect(plageAutourDe('4h')).toEqual({ de: '03:00', a: '05:00' });
    expect(plageAutourDe('12 h')).toEqual({ de: '11:00', a: '13:00' });
    expect(plageAutourDe('12h30')).toEqual({ de: '11:30', a: '13:30' });
    expect(plageAutourDe('04:00')).toEqual({ de: '03:00', a: '05:00' });
  });
  it('reste dans la journée', () => {
    expect(plageAutourDe('0')).toEqual({ de: '00:00', a: '01:00' });
    expect(plageAutourDe('23')).toEqual({ de: '22:00', a: '23:59' });
  });
  it('refuse ce qui n’est pas une heure', () => {
    expect(plageAutourDe('')).toBeNull();
    expect(plageAutourDe('matin')).toBeNull();
    expect(plageAutourDe('25')).toBeNull();
  });
});

describe('direPlage', () => {
  it('dit « vers 4 h » pour une plage centrée, sinon les bornes', () => {
    expect(direPlage({ de: '03:00', a: '05:00' })).toBe('vers 4 h');
    expect(direPlage({ de: '11:30', a: '13:30' })).toBe('vers 12 h 30');
    expect(direPlage({ de: '03:30', a: '04:30' })).toBe('de 03:30 à 04:30');
  });
});

describe('modèles', () => {
  it('cochent les exclusions de la population qui pointe', () => {
    for (const m of MODELES_PRIMES_POINTAGE) {
      expect(m.regle.conditions).toMatchObject({
        exclure_forfait_jours: true,
        exclure_cadres: true,
        exclure_alternants: true,
      });
    }
  });
  it('n’imposent aucun montant (pas de 6 € par défaut)', () => {
    for (const m of MODELES_PRIMES_POINTAGE) expect(m.regle.amount).toBeNull();
  });
});

describe('erreurDeLaRegle', () => {
  it('exige un montant, sauf heures payées ou majoration en %', () => {
    expect(erreurDeLaRegle({ label: 'Panier', rule_type: 'per_worked_day', amount: 0 }, [], null)).toBe(
      'Indiquez le montant de la prime.',
    );
    expect(
      erreurDeLaRegle({ label: 'Pause', rule_type: 'per_worked_day', amount: null, conditions: { heures_par_jour: 0.5 } }, [], null),
    ).toBeNull();
    expect(
      erreurDeLaRegle({ label: 'Nuit', rule_type: 'per_night_hour', amount: null, conditions: { majoration_pct: 50 } }, [], null),
    ).toBeNull();
    expect(erreurDeLaRegle({ label: 'Km', rule_type: 'per_astreinte_weekend_km', amount: null }, [], null)).toBeNull();
  });
  it('refuse un libellé déjà pris, sauf la règle elle-même', () => {
    const existantes = [regle({ id: 'a', label: 'Panier' })];
    expect(erreurDeLaRegle({ label: ' panier ', rule_type: 'per_worked_day', amount: 10 }, existantes, null)).toMatch(
      /déjà « panier »/,
    );
    expect(erreurDeLaRegle({ label: 'Panier', rule_type: 'per_worked_day', amount: 10 }, existantes, 'a')).toBeNull();
  });
  it('laisse modifier une règle existante : retenue négative, taux, ancien doublon de libellé', () => {
    expect(erreurDeLaRegle({ label: 'Retenue', rule_type: 'fixed_monthly', amount: -20 }, [], null)).toBeNull();
    expect(erreurDeLaRegle({ label: 'Taux', rule_type: 'fixed_monthly', amount: null, rate: 1.5 }, [], null)).toBeNull();
    const doublons = [regle({ id: 'a', label: 'Prime' }), regle({ id: 'b', label: 'Prime' })];
    expect(erreurDeLaRegle({ label: 'Prime', rule_type: 'fixed_monthly', amount: 10 }, doublons, 'a')).toBeNull();
  });
  it('une majoration ou des heures à 0 ne remplacent pas le montant', () => {
    expect(montantIgnore({ rule_type: 'per_night_hour', conditions: { majoration_pct: 0 } })).toBeNull();
    expect(montantIgnore({ rule_type: 'per_worked_day', conditions: { heures_par_jour: 0 } })).toBeNull();
  });
  it('exige un libellé', () => {
    expect(erreurDeLaRegle({ label: '  ', rule_type: 'fixed_monthly', amount: 10 }, [], null)).toMatch(/libellé/);
  });
});

describe('montantIgnore', () => {
  it('le dit quand des heures ou une majoration remplacent le montant', () => {
    expect(montantIgnore({ rule_type: 'per_worked_day', conditions: { heures_par_jour: 0.5 } })).toMatch(/taux horaire/);
    expect(montantIgnore({ rule_type: 'per_night_hour', conditions: { majoration_pct: 50 } })).toMatch(/taux horaire/);
    expect(montantIgnore({ rule_type: 'per_worked_day', conditions: {} })).toBeNull();
  });
});

describe('trierLaSimulation', () => {
  it('met toutes les alertes à part', () => {
    const r = trierLaSimulation({
      year: 2026,
      month: 10,
      dry_run: true,
      written_count: 0,
      preview: [
        { employee_id: '1', amount: 100, quantity: 10, details: { jours_travailles: 10 } },
        { employee_id: '2', amount: 0, quantity: 0, details: { jours_sans_heure_de_debut: 3 } },
        { employee_id: '3', amount: 0, quantity: 0, details: { skip_reason: 'taux_horaire_inconnu' } },
      ],
    } as never);
    expect(r.alertes.map((a) => a.employee_id)).toEqual(['2', '3']);
    expect(r.lignes.map((a) => a.employee_id)).toEqual(['1']);
  });
});

describe('jours travaillés sans heure d\'arrivée (L19, 26/11)', () => {
  it('donne le nombre et les dates, au singulier comme au pluriel', () => {
    expect(phraseJoursSansHeureDArrivee(2, ['2026-10-05', '2026-10-06'])).toBe(
      "2 jours travaillés sans heure d'arrivée, non comptés (05/10, 06/10) : heure d'arrivée à saisir au calendrier, ou absence à poser",
    );
    expect(phraseJoursSansHeureDArrivee(1, ['2026-10-11'])).toBe(
      "1 jour travaillé sans heure d'arrivée, non compté (11/10) : heure d'arrivée à saisir au calendrier, ou absence à poser",
    );
  });

  it('sans dates (simulation ancienne), le nombre seul', () => {
    expect(phraseJoursSansHeureDArrivee(3)).toBe(
      "3 jours travaillés sans heure d'arrivée, non comptés : heure d'arrivée à saisir au calendrier, ou absence à poser",
    );
  });

  it('un panier positif avec des jours non comptés reste une alerte', () => {
    const r = trierLaSimulation({
      year: 2026,
      month: 10,
      dry_run: true,
      written_count: 0,
      preview: [
        { employee_id: '1', amount: 190, quantity: 19, details: { jours_sans_heure_de_debut: 2, dates_sans_heure_de_debut: ['2026-10-05', '2026-10-06'] } },
      ],
    } as never);
    expect(r.alertes.map((a) => a.employee_id)).toEqual(['1']);
  });
});

describe("encadré de Primes du mois : aucun badge du mois (L19, 27/11)", () => {
  it('une seule phrase, sans les dates, quand aucun jour n\'a d\'heure d\'arrivée', () => {
    expect(
      phraseJoursDuSalarie({ rule_label: 'Panier', dates: ['2026-10-01', '2026-10-02', '2026-10-05'], aucun_badge: true }),
    ).toBe(
      "Panier : aucune heure d'arrivée sur la période (3 jours travaillés), aucun panier compté : importez les pointages, saisissez les heures d'arrivée au calendrier ou posez les absences.",
    );
  });

  it('les dates quand une partie des jours en a une', () => {
    expect(phraseJoursDuSalarie({ rule_label: 'Panier', dates: ['2026-10-05'], aucun_badge: false })).toBe(
      "Panier : 1 jour travaillé sans heure d'arrivée (05/10) : aucun compté ce jour-là. Importez les pointages, saisissez l'heure d'arrivée au calendrier ou posez l'absence.",
    );
  });

  it('les règles aux mêmes jours sont nommées ensemble (L23, 28/11)', () => {
    expect(
      phraseJoursDuSalarie({
        rule_label: 'Panier, Panier de nuit, Prime de nuit',
        rule_labels: ['Panier', 'Panier de nuit', 'Prime de nuit'],
        dates: ['2026-10-19', '2026-10-20'],
        aucun_badge: false,
      }),
    ).toBe(
      "Panier, Panier de nuit, Prime de nuit : 2 jours travaillés sans heure d'arrivée (19/10, 20/10) : aucun compté ces jours-là. Importez les pointages, saisissez l'heure d'arrivée au calendrier ou posez l'absence.",
    );
  });

  it("aucun badge : « aucun panier » seulement quand toutes les règles sont des paniers (L23)", () => {
    const base = { dates: ['2026-10-01', '2026-10-02'], aucun_badge: true };
    expect(phraseJoursDuSalarie({ ...base, rule_labels: ['Panier', 'Panier de nuit'] })).toBe(
      "Panier, Panier de nuit : aucune heure d'arrivée sur la période (2 jours travaillés), aucun panier compté : importez les pointages, saisissez les heures d'arrivée au calendrier ou posez les absences.",
    );
    expect(phraseJoursDuSalarie({ ...base, rule_labels: ['Panier', 'Prime de nuit'] })).toContain(
      '(2 jours travaillés), aucun jour compté :',
    );
  });

  it("une autre règle que le panier ne parle pas de panier", () => {
    expect(phraseJoursDuSalarie({ rule_label: 'Pause payée', dates: ['2026-10-01'], aucun_badge: true })).toContain(
      'aucun jour compté',
    );
  });
});
