import { pluriel } from '@/lib/pluriel';

/** Ce que compte le décompte « Échéances » : dit en toutes lettres, titres de séjour compris. */
export const TITRE_ECHEANCES =
  'Échéances : fins de CDD et de stage, périodes d’essai (15 jours), titres de séjour (30 jours)';

export function messageEcheances(nombre: number): string {
  return nombre === 0 ? 'Aucune échéance à venir.' : `${pluriel(nombre, 'salarié')} à traiter.`;
}
