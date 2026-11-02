import type {
  CategoriePrevoyance,
  FormulePrevoyance,
  LigneFormulePrevoyance,
} from '@/api/prevoyanceFormules';

/** Une ligne telle que la fiche la porte (l'identifiant en plus). */
export type LignePrevoyanceFiche = LigneFormulePrevoyance & { id: string };

/** La base que le moteur prend quand une ligne n'en dit rien. */
const BASE_PAR_DEFAUT = 'brut_plafonne';

export function formulesPourLeStatut(formules: FormulePrevoyance[], cadre: boolean): FormulePrevoyance[] {
  return formules.filter(
    (f) => f.is_active && (f.statut_categoriel === 'tous' || (f.statut_categoriel === 'cadre') === cadre),
  );
}

/** Les lignes de la formule, copiées pour la fiche. */
export function lignesDeLaFormule(formule: FormulePrevoyance): LignePrevoyanceFiche[] {
  return formule.lignes.map((ligne, index) => ({
    ...structuredClone(ligne),
    id: `prevoyance_${index + 1}`,
  }));
}

function cle(ligne: Partial<LigneFormulePrevoyance>): string {
  const { id: _id, base, libelle, salarial, patronal, forfait_social, ...autres } = ligne as Record<string, unknown>;
  const taux = [salarial, patronal, forfait_social].map((v) => Math.round(Number(v ?? 0) * 1e8) / 1e8);
  const reste = Object.keys(autres)
    .sort()
    .map((k) => `${k}=${JSON.stringify(autres[k])}`);
  return JSON.stringify([String(libelle ?? '').trim(), ...taux, String(base || BASE_PAR_DEFAUT), reste]);
}

/** Les lignes de la fiche ne sont plus celles de la formule. */
export function lignesModifiees(lignes: Array<Partial<LigneFormulePrevoyance>> | undefined, formule: FormulePrevoyance): boolean {
  const a = (lignes ?? []).map(cle);
  const b = formule.lignes.map(cle);
  return a.length !== b.length || a.some((k, i) => k !== b[i]);
}

export function messageFichesAMettreAJour(nombre: number): string {
  return nombre === 1
    ? '1 fiche a encore les anciennes lignes de cette formule.'
    : `${nombre} fiches ont encore les anciennes lignes de cette formule.`;
}

export function messageFichesMisesAJour(nombre: number): string {
  if (nombre === 0) return 'Aucune fiche à mettre à jour.';
  return nombre === 1
    ? '1 fiche mise à jour : ses brouillons sont à recalculer.'
    : `${nombre} fiches mises à jour : leurs brouillons sont à recalculer.`;
}

export function libelleCategorie(categorie: CategoriePrevoyance): string {
  return { cadre: 'Cadres', non_cadre: 'Non-cadres', tous: 'Tous les salariés' }[categorie];
}
