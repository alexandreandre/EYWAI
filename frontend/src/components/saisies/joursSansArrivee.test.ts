import { describe, expect, it } from 'vitest';
import {
  cleDuMois,
  compterJoursReels,
  etatInitialDesJours,
  lignesParSalarie,
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

describe('encadré : une ligne par salarié (L23, 28/11)', () => {
  const memes = ['2026-10-19', '2026-10-20'];
  it('les groupes d\'un salarié tiennent sur une ligne, dans l\'ordre reçu', () => {
    const lignes = lignesParSalarie([
      { employee_id: 'a', first_name: 'A', last_name: 'B', rule_label: 'Panier, Prime de nuit', rule_labels: ['Panier', 'Prime de nuit'], dates: memes },
      { employee_id: 'b', first_name: 'C', last_name: 'D', rule_label: 'Panier', rule_labels: ['Panier'], dates: memes.slice(0, 1) },
      { employee_id: 'a', first_name: 'A', last_name: 'B', rule_label: 'Panier de nuit', rule_labels: ['Panier de nuit'], dates: memes.slice(1) },
    ]);
    expect(lignes.map((l) => l.employee_id)).toEqual(['a', 'b']);
    expect(lignes[0].phrase).toBe(
      "Panier, Prime de nuit : 2 jours travaillés sans heure d'arrivée (19/10, 20/10) : aucun compté ces jours-là. Importez les pointages ou saisissez l'heure d'arrivée au calendrier. "
        + "Panier de nuit : 1 jour travaillé sans heure d'arrivée (20/10) : aucun compté ce jour-là. Importez les pointages ou saisissez l'heure d'arrivée au calendrier.",
    );
    expect(lignes[1]).toMatchObject({ first_name: 'C', last_name: 'D' });
  });
});
