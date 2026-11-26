/**
 * Jours des mois voisins dans la grille d'un mois (retour d'Elsa du 26/11) :
 * la première et la dernière semaine sont souvent à cheval sur deux mois
 * (S40 : du 28/09 au 04/10). Ces jours s'affichent dans la grille, en lecture,
 * pour contrôler la semaine entière sans changer de mois.
 *
 * Grille du lundi au dimanche ; `mois` de 1 à 12.
 */

export interface JourVoisin {
  annee: number;
  mois: number;
  jour: number;
  date: Date;
}

export interface JoursVoisins {
  avant: JourVoisin[];
  apres: JourVoisin[];
}

function jourVoisin(date: Date): JourVoisin {
  return { annee: date.getFullYear(), mois: date.getMonth() + 1, jour: date.getDate(), date };
}

export function joursVoisins(annee: number, mois: number): JoursVoisins {
  const premier = new Date(annee, mois - 1, 1);
  const nbJours = new Date(annee, mois, 0).getDate();
  const decalage = (premier.getDay() + 6) % 7; // lundi = 0
  const avant: JourVoisin[] = [];
  for (let i = decalage; i > 0; i--) avant.push(jourVoisin(new Date(annee, mois - 1, 1 - i)));
  const reste = (7 - ((decalage + nbJours) % 7)) % 7;
  const apres: JourVoisin[] = [];
  for (let i = 1; i <= reste; i++) apres.push(jourVoisin(new Date(annee, mois - 1, nbJours + i)));
  return { avant, apres };
}

/** Numéro de semaine ISO 8601 (« S40 »). */
export function numeroDeSemaine(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const jour = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - jour);
  const debutAnnee = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d.getTime() - debutAnnee.getTime()) / 86_400_000 + 1) / 7);
}
