import type { BasePrevoyance, LigneFormulePrevoyance } from '@/api/prevoyanceFormules';
import { fractionDuTexteTaux, texteDuTauxPrevoyance } from '@/features/employees/utils/prevoyance';

/**
 * Une ligne telle que la fenêtre la montre : taux en %, en texte. Le forfait
 * social n'y est pas : il suit la loi (8 % à partir de 11 salariés), pas la
 * ligne ; une valeur ancienne passe telle quelle dans `autres`.
 */
export interface LigneSaisie {
  libelle: string;
  salarial: string;
  patronal: string;
  base: BasePrevoyance;
  /** Les clés que la fenêtre ne montre pas, rendues telles quelles. */
  autres: Record<string, unknown>;
}

export const BASES_PREVOYANCE: Array<{ valeur: BasePrevoyance; libelle: string }> = [
  { valeur: 'brut_plafonne', libelle: 'Tranche A (salaire plafonné)' },
  { valeur: 'tranche_2', libelle: 'Tranche B (au-delà du plafond)' },
  { valeur: 'brut', libelle: 'Salaire brut entier' },
];

export function ligneVide(): LigneSaisie {
  return { libelle: '', salarial: '', patronal: '', base: 'brut_plafonne', autres: {} };
}

export function saisieDesLignes(lignes: LigneFormulePrevoyance[]): LigneSaisie[] {
  return lignes.map(({ libelle, salarial, patronal, base, id: _id, ...autres }) => ({
    libelle: String(libelle ?? ''),
    salarial: texteDuTauxPrevoyance(salarial),
    patronal: texteDuTauxPrevoyance(patronal),
    base: (base as BasePrevoyance | null | undefined) || 'brut_plafonne',
    autres,
  }));
}

export function lignesDeLaSaisie(saisie: LigneSaisie[]): { lignes: LigneFormulePrevoyance[]; erreur: string | null } {
  if (saisie.length === 0) return { lignes: [], erreur: 'Ajoutez au moins une ligne.' };
  const lignes: LigneFormulePrevoyance[] = [];
  for (const [index, ligne] of saisie.entries()) {
    const libelle = ligne.libelle.trim();
    if (libelle.length < 2) return { lignes: [], erreur: `Ligne ${index + 1} : libellé requis.` };
    const taux = [ligne.salarial, ligne.patronal].map(fractionDuTexteTaux);
    if (taux.some((t) => t === null)) {
      return { lignes: [], erreur: `Ligne ${index + 1} : saisissez un taux en %, par exemple 0,78.` };
    }
    const [salarial, patronal] = taux as number[];
    lignes.push({ ...ligne.autres, libelle, salarial, patronal, base: ligne.base });
  }
  return { lignes, erreur: null };
}
