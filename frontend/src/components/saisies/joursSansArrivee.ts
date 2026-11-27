/**
 * Primes du mois : l'encadré des jours travaillés sans heure d'arrivée et le
 * nombre de paniers corrigé (L19, relecture du 27/11).
 */
import type { JoursSansHeureDArrivee, PayrollVariableRule } from '@/api/payrollVariables';

/** Les règles dont le montant est nombre × montant de la règle (comme `alertes_paniers`). */
const TYPES_NOMBRE_FOIS_MONTANT = new Set(['per_worked_day', 'per_shift_type']);

function arrondi(montant: number): number {
  return Math.round(montant * 100) / 100;
}

/** Le montant d'un panier selon la règle qui a écrit la saisie (« Auto: <code> »), ou null. */
export function montantUnitaireDeLaRegle(
  saisie: { description?: string | null },
  regles: PayrollVariableRule[],
): number | null {
  const description = saisie.description ?? '';
  if (!description.startsWith('Auto:')) return null;
  const code = description.slice('Auto:'.length).trim();
  const regle = regles.find((r) => r.code.trim() === code);
  if (!regle || !TYPES_NOMBRE_FOIS_MONTANT.has(regle.rule_type) || regle.amount == null) return null;
  const conditions = (regle.conditions ?? {}) as Record<string, unknown>;
  if (conditions.heures_par_jour) return null;
  return Number(regle.amount);
}

/**
 * Le montant qui va avec un nombre de paniers corrigé : nombre × montant de la
 * règle pour une saisie générée, sinon le prix d'un panier de la saisie (montant
 * ÷ ancien nombre). null quand le prix ne se connaît pas : le montant reste.
 */
export function montantPourLeNombre(
  saisie: { description?: string | null; amount: number; payroll_quantity?: number | null },
  nombre: number,
  regles: PayrollVariableRule[],
): number | null {
  const unitaire = montantUnitaireDeLaRegle(saisie, regles);
  if (unitaire != null) return arrondi(unitaire * nombre);
  const ancien = Number(saisie.payroll_quantity ?? 0);
  if (ancien > 0) return arrondi((saisie.amount * nombre) / ancien);
  return null;
}

/** Des jours réels : un salarié et une date comptent une fois, quelles que soient les règles. */
export function compterJoursReels(jours: Pick<JoursSansHeureDArrivee, 'employee_id' | 'dates'>[]): number {
  return new Set(jours.flatMap((j) => j.dates.map((d) => `${j.employee_id}|${d}`))).size;
}

export function cleDuMois(year: number, month: number): string {
  return `${year}-${month}`;
}

export type EtatDesJours = {
  cle: string;
  etat: 'lecture' | 'erreur' | JoursSansHeureDArrivee[];
};

/** Au changement de mois : la liste repart de zéro, en lecture. */
export function etatInitialDesJours(year: number, month: number): EtatDesJours {
  return { cle: cleDuMois(year, month), etat: 'lecture' };
}

/** Une réponse d'un autre mois que celui affiché est ignorée. */
export function recevoirJours(
  courant: EtatDesJours,
  cle: string,
  reponse: JoursSansHeureDArrivee[] | 'erreur',
): EtatDesJours {
  if (cle !== courant.cle) return courant;
  return { cle, etat: reponse };
}

/** Ce que l'encadré dit tant qu'il n'a pas de liste à montrer ; null s'il n'a rien à dire. */
export function texteDeLEncadre(etat: EtatDesJours): string | null {
  if (etat.etat === 'lecture') return "Vérification des heures d'arrivée…";
  if (etat.etat === 'erreur') {
    return "Les jours travaillés sans heure d'arrivée n'ont pas pu être relus au calendrier : vérifiez-les avant la paie.";
  }
  return null;
}
