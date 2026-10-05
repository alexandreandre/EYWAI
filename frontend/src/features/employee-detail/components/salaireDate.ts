/**
 * Changer le salaire de base avec une date d'effet (PUT /api/employees/{id}/salary).
 *
 * Dès qu'un salarié a un historique de salaire, chaque génération remet sur la
 * fiche le salaire de cet historique : le salaire de la fiche ne se change
 * plus dans le formulaire du profil, seulement ici.
 */
import type { SalaryHistoryEntry } from '@/api/augmentations';

/** Le salaire du profil est-il verrouillé par un historique daté ? */
export function salaireVerrouille(historique: SalaryHistoryEntry[] | undefined): boolean {
  return (historique?.length ?? 0) > 0;
}

function deuxChiffres(n: number): string {
  return String(n).padStart(2, '0');
}

function jourIso(date: Date): string {
  return `${date.getFullYear()}-${deuxChiffres(date.getMonth() + 1)}-${deuxChiffres(date.getDate())}`;
}

/** Le 1er du mois en cours (AAAA-MM-JJ) : une augmentation part d'ordinaire du 1er. */
export function dateEffetParDefaut(aujourdhui: Date): string {
  return `${aujourdhui.getFullYear()}-${deuxChiffres(aujourdhui.getMonth() + 1)}-01`;
}

/** Le nouveau salaire est-il déjà celui de la fiche (date d'effet passée ou du jour) ? */
export function salaireApplique(dateEffet: string, aujourdhui: Date): boolean {
  return dateEffet <= jourIso(aujourdhui);
}

/** « 2100,50 » → 2100,5 ; vide, illisible ou nul → null. */
export function lireMontant(saisie: string): number | null {
  const valeur = Number(saisie.trim().replace(/\s/g, '').replace(',', '.'));
  return saisie.trim() && Number.isFinite(valeur) && valeur > 0 ? valeur : null;
}

export function erreursChangementSalaire(saisie: { montant: string; dateEffet: string }): string[] {
  const erreurs: string[] = [];
  if (lireMontant(saisie.montant) === null) {
    erreurs.push('Saisissez le nouveau salaire de base mensuel brut.');
  }
  if (!saisie.dateEffet) erreurs.push('Choisissez la date d’effet.');
  return erreurs;
}

function euros(montant: number): string {
  const [entier, decimales] = montant.toFixed(2).split('.');
  return `${entier.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')},${decimales} €`;
}

function dateFr(iso: string): string {
  const [annee, mois, jour] = iso.slice(0, 10).split('-');
  return `${jour}/${mois}/${annee}`;
}

export function messageSalaireEnregistre(
  montant: number,
  dateEffet: string,
  aujourdhui: Date,
): string {
  const quoi = `Salaire de base : ${euros(montant)} à compter du ${dateFr(dateEffet)}.`;
  return salaireApplique(dateEffet, aujourdhui)
    ? `${quoi} Les bulletins concernés passent « À recalculer ».`
    : `${quoi} D’ici là, la fiche garde le salaire actuel.`;
}
