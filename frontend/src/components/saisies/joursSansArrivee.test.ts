import { describe, expect, it } from 'vitest';
import {
  cleDuMois,
  compterJoursReels,
  etatInitialDesJours,
  montantPourLeNombre,
  recevoirJours,
  texteDeLEncadre,
} from './joursSansArrivee';

const REGLES = [
  { code: 'panier_jour', label: 'Panier', enabled: true, rule_type: 'per_worked_day', amount: 7.6, conditions: {}, generation_mode: 'auto', sort_order: 0 },
  { code: 'pause_payee', label: 'Pause payée', enabled: true, rule_type: 'per_worked_day', amount: null, conditions: { heures_par_jour: 0.5 }, generation_mode: 'auto', sort_order: 1 },
] as never;

describe('nombre de paniers corrigé : le montant suit (relecture L19, 27/11)', () => {
  it('saisie générée : nombre × montant de la règle', () => {
    expect(montantPourLeNombre({ description: 'Auto: panier_jour', amount: 114, payroll_quantity: 15 }, 14, REGLES)).toBe(106.4);
  });

  it('saisie à la main : le prix d\'un panier ne change pas', () => {
    expect(montantPourLeNombre({ description: '', amount: 114, payroll_quantity: 15 }, 14, REGLES)).toBe(106.4);
  });

  it('sans prix connu : rien à proposer', () => {
    expect(montantPourLeNombre({ description: 'Auto: pause_payee', amount: 20, payroll_quantity: null }, 14, REGLES)).toBeNull();
    expect(montantPourLeNombre({ description: '', amount: 20, payroll_quantity: null }, 14, REGLES)).toBeNull();
  });
});

describe('encadré des jours sans heure d\'arrivée (relecture L19, 27/11)', () => {
  const jours = [
    { employee_id: 'a', rule_label: 'Panier', dates: ['2026-10-05', '2026-10-06'] },
    { employee_id: 'a', rule_label: 'Pause payée', dates: ['2026-10-05', '2026-10-06'] },
    { employee_id: 'b', rule_label: 'Panier', dates: ['2026-10-05'] },
  ];

  it('compte des jours réels, pas des lignes salarié × règle', () => {
    expect(compterJoursReels(jours)).toBe(3);
  });

  it('lecture en cours : dit, jamais silencieux', () => {
    const etat = etatInitialDesJours(2026, 10);
    expect(texteDeLEncadre(etat)).toBe("Vérification des heures d'arrivée…");
  });

  it('une réponse d\'un autre mois est ignorée', () => {
    const etat = etatInitialDesJours(2026, 11);
    expect(recevoirJours(etat, cleDuMois(2026, 10), jours)).toBe(etat);
    expect(recevoirJours(etat, cleDuMois(2026, 11), jours).etat).toEqual(jours);
  });

  it('une lecture qui échoue est dite', () => {
    const etat = recevoirJours(etatInitialDesJours(2026, 10), cleDuMois(2026, 10), 'erreur');
    expect(texteDeLEncadre(etat)).toBe(
      "Les jours travaillés sans heure d'arrivée n'ont pas pu être relus au calendrier : vérifiez-les avant la paie.",
    );
  });

  it('rien à dire une fois lus sans jour', () => {
    expect(texteDeLEncadre(recevoirJours(etatInitialDesJours(2026, 10), cleDuMois(2026, 10), []))).toBeNull();
  });
});
