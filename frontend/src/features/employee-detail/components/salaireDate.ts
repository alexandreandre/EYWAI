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

/** Le texte au-dessus de « Changer le salaire », avec ou sans historique daté. */
export function texteSalaireActuel(
  salaire: number | null | undefined,
  avecHistorique: boolean,
): string {
  const actuel =
    salaire !== null && salaire !== undefined && Number.isFinite(Number(salaire)) && Number(salaire) > 0
      ? euros(Number(salaire))
      : '—';
  return avecHistorique
    ? `Salaire de base actuel : ${actuel}. Il suit l’historique des salaires : il se change avec une date d’effet.`
    : `Salaire de base actuel : ${actuel}. Aucun historique de salaire : « Changer le salaire » ` +
        'en ouvre un à partir de ce salaire, avec une date d’effet et le rappel des mois déjà payés.';
}

/**
 * Le salaire changé dans le champ de la fiche (salarié sans historique) n'est
 * pas daté : il remplace l'ancien sur tout bulletin recalculé, sans rappel. Le
 * dire dès que le champ change.
 */
export function avertissementSalaireNonDate(
  initial: number | null | undefined,
  courant: number | string | null | undefined,
): string | null {
  const avant = Number(initial);
  const apres = Number(courant);
  if (!initial || !Number.isFinite(avant) || courant === '' || courant === null || courant === undefined) {
    return null;
  }
  if (!Number.isFinite(apres) || Math.abs(apres - avant) < 0.005) return null;
  return (
    `Changé ici, le salaire n’est pas daté : il remplace ${euros(avant)} sur tout bulletin recalculé, ` +
    'sans rappel des mois déjà payés. Pour une augmentation à une date, utilisez « Changer le salaire ».'
  );
}

/**
 * Les salaires datés dans le futur, dits à côté du salaire actuel :
 * « Prévu : 2 100,00 € à partir du 01/11/2026. » Après « Nouveau contrat », la
 * fiche ne montrait que le salaire actuel, sans indice du changement prévu
 * (tournage H.5, scène 8).
 */
export function texteSalairePlanifie(
  historique: SalaryHistoryEntry[] | undefined,
  aujourdhui: Date,
): string | null {
  const jour = jourIso(aujourdhui);
  const prevus = (historique ?? [])
    .filter((ligne) => (ligne.planifiee ?? ligne.effective_date.slice(0, 10) > jour) === true)
    .filter((ligne) => Number(ligne.nouveau_salaire?.valeur) > 0)
    .sort((a, b) => a.effective_date.localeCompare(b.effective_date));
  if (prevus.length === 0) return null;
  const morceaux = prevus.map(
    (ligne) => `${euros(Number(ligne.nouveau_salaire.valeur))} à partir du ${dateFr(ligne.effective_date)}`,
  );
  return `Prévu : ${morceaux.join(', puis ')}.`;
}
