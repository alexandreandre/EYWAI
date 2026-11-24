import type { CalculationMode, SalarySeizureStatus, SalarySeizureUpdate } from '@/api/saisiesAvances';
import { eurosFr } from '@/lib/paliersAffichage';

type SaisieMontant = {
  calculation_mode: CalculationMode;
  amount?: number | null;
  percentage?: number | null;
};

/**
 * Libellé du montant d'une saisie sur salaire.
 *
 * Les décimaux Postgres arrivent en chaîne via l'API (« 46.49 ») : on
 * convertit avant de formater. Appeler `toFixed` directement sur la valeur
 * faisait tomber toute la page Saisies sur salaire en écran blanc dès
 * qu'une saisie existait (salarié 140, 12/09).
 */
export function libelleMontantSaisie(saisie: SaisieMontant): string {
  if (saisie.calculation_mode === 'fixe' && saisie.amount) {
    const montant = Number(saisie.amount);
    if (Number.isFinite(montant)) return `${montant.toFixed(2)}€`;
  }
  if (saisie.calculation_mode === 'pourcentage' && saisie.percentage) {
    return `${saisie.percentage}%`;
  }
  return 'Barème légal';
}

/**
 * Nombre de personnes à charge saisi dans le formulaire.
 *
 * Chacune relève les seuils du barème légal de la quotité saisissable
 * (R3252-3 du Code du travail) : un entier, jamais négatif ; vide ou illisible,
 * aucune.
 */
export function personnesACharge(texte: string): number {
  const nombre = Math.floor(Number(texte));
  return Number.isFinite(nombre) && nombre > 0 ? nombre : 0;
}

export function libellePersonnesACharge(nombre: number | null | undefined): string {
  const n = Number(nombre) || 0;
  if (n <= 0) return 'Aucune';
  return n === 1 ? '1 personne' : `${n} personnes`;
}

/**
 * Montant en euros tapé dans un champ : « 1 200,50 », « 300.25 ».
 * Vide : null (aucun montant). Négatif ou illisible : undefined (refusé).
 */
export function montantSaisi(texte: string): number | null | undefined {
  const brut = texte.replace(/[\s\u00a0\u202f€]/g, '').replace(',', '.');
  if (brut === '') return null;
  const montant = Number(brut);
  if (!Number.isFinite(montant) || montant < 0) return undefined;
  return Math.round(montant * 100) / 100;
}

/** Un décimal reçu de l'API, en nombre (il arrive parfois en texte). */
function enNombre(valeur: unknown): number | null {
  if (valeur === null || valeur === undefined || valeur === '') return null;
  const n = Number(valeur);
  return Number.isFinite(n) ? n : null;
}

type SaisieReste = {
  montant_total?: number | null;
  reste_du?: number | null;
};

/**
 * Le reste dû d'une saisie qui a un montant total : « Reste dû : 600,00 € sur
 * 1 000,00 € », ou « Soldée » ; null sans montant total (la saisie court sans
 * fin, rien à dire).
 */
export function libelleResteDu(saisie: SaisieReste): string | null {
  const total = enNombre(saisie.montant_total);
  if (total === null) return null;
  const reste = enNombre(saisie.reste_du) ?? total;
  if (reste <= 0) return `Soldée (${eurosFr(total)})`;
  return `Reste dû : ${eurosFr(reste)} sur ${eurosFr(total)}`;
}

const LIBELLES_STATUT: Record<SalarySeizureStatus, string> = {
  active: 'Active',
  suspended: 'Suspendue',
  closed: 'Clôturée',
};

/**
 * Dette soldée : un montant total et plus rien de dû. Rien n'est plus retenu,
 * sans que le statut change (il reprend seul si le reste dû remonte).
 */
export function estSoldee(saisie: SaisieReste): boolean {
  return enNombre(saisie.montant_total) !== null && (enNombre(saisie.reste_du) ?? 1) <= 0;
}

/** Le statut à l'écran : une saisie dont la dette est soldée dit « Soldée ». */
export function libelleStatutSaisie(saisie: SaisieReste & { status: SalarySeizureStatus }): string {
  if (saisie.status !== 'suspended' && estSoldee(saisie)) return 'Soldée';
  return LIBELLES_STATUT[saisie.status] ?? saisie.status;
}

/**
 * Ce qu'il faut envoyer au serveur quand la RH modifie la mensualité ou le
 * montant total à l'écran : seulement ce qui change. Un total vidé est
 * effacé (null). Rend un texte d'erreur si un montant est refusé.
 */
export function modificationDesMontants(
  saisie: { calculation_mode: CalculationMode; amount?: number | null; montant_total?: number | null },
  champs: { mensualite: string; total: string }
): SalarySeizureUpdate | string {
  const modification: SalarySeizureUpdate = {};
  if (saisie.calculation_mode !== 'pourcentage') {
    const mensualite = montantSaisi(champs.mensualite);
    if (mensualite === undefined) return 'Mensualité illisible : un montant en euros, positif.';
    if (mensualite === null && saisie.calculation_mode === 'fixe') {
      return 'Une saisie à montant fixe a besoin d’une mensualité.';
    }
    // Vidée au barème légal : effacée, la retenue reprend la quotité du mois.
    if (mensualite !== enNombre(saisie.amount)) {
      modification.amount = mensualite;
    }
  }
  const total = montantSaisi(champs.total);
  if (total === undefined) return 'Montant total illisible : un montant en euros, positif.';
  if (total !== enNombre(saisie.montant_total)) {
    modification.montant_total = total;
  }
  return modification;
}
