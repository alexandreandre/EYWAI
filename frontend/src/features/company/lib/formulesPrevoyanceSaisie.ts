import type { BasePrevoyance, LigneFormulePrevoyance } from '@/api/prevoyanceFormules';
import { fractionDuTexteTaux, texteDuTauxPrevoyance } from '@/features/employees/utils/prevoyance';

/** Une ligne telle que la fenêtre la montre : taux en %, en texte. */
export interface LigneSaisie {
  libelle: string;
  salarial: string;
  patronal: string;
  forfait_social: string;
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
  return { libelle: '', salarial: '', patronal: '', forfait_social: '', base: 'brut_plafonne', autres: {} };
}

export function saisieDesLignes(lignes: LigneFormulePrevoyance[]): LigneSaisie[] {
  return lignes.map(({ libelle, salarial, patronal, forfait_social, base, id: _id, ...autres }) => ({
    libelle: String(libelle ?? ''),
    salarial: texteDuTauxPrevoyance(salarial),
    patronal: texteDuTauxPrevoyance(patronal),
    forfait_social: texteDuTauxPrevoyance(forfait_social),
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
    const taux = [ligne.salarial, ligne.patronal, ligne.forfait_social].map(fractionDuTexteTaux);
    if (taux.some((t) => t === null)) {
      return { lignes: [], erreur: `Ligne ${index + 1} : saisissez un taux en %, par exemple 0,78.` };
    }
    const [salarial, patronal, forfait_social] = taux as number[];
    lignes.push({ ...ligne.autres, libelle, salarial, patronal, forfait_social, base: ligne.base });
  }
  return { lignes, erreur: null };
}
