import type {
  GraviteRelecture,
  PreparationRelecture,
  RelectureIa,
  SocieteARelire,
} from '@/api/relectureIa';

export function texteProgression(relecture: Pick<RelectureIa, 'traites' | 'total'>): string {
  return `Relecture en cours : ${relecture.traites} sur ${relecture.total}.`;
}

/** Le coût dit à Elsa : toujours une estimation, jamais « 0,00 € » pour un vrai lot. */
export function coutAffiche(euros: number): string {
  if (euros > 0 && euros < 0.01) return 'moins de 0,01 €';
  return `environ ${euros.toLocaleString('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} €`;
}

/** Pourquoi le bouton est grisé, ou null s'il peut servir. */
export function raisonBoutonGrise(preparation: PreparationRelecture | undefined): string | null {
  if (!preparation) return null;
  if (preparation.blocage) return preparation.blocage;
  if (preparation.societes.length === 0) return 'Aucun bulletin généré pour ce mois : rien à relire.';
  if (preparation.total_a_relire === 0) {
    return 'Rien à relire : tous les bulletins de ce mois ont déjà été relus depuis leur dernière modification.';
  }
  return null;
}

export interface SelectionRelecture {
  nombre: number;
  companyIds: string[];
  /** null : tous les salariés à relire des sociétés cochées. */
  employeeIds: string[] | null;
}

/** Ce que les cases de la fenêtre lancent réellement, et donc ce qui sera facturé. */
export function selectionRelecture(
  societes: SocieteARelire[],
  societesDecochees: ReadonlySet<string>,
  salariesExclus: ReadonlySet<string>,
): SelectionRelecture {
  const cochees = societes.filter((s) => !societesDecochees.has(s.company_id));
  const retenus = cochees.flatMap((s) =>
    s.salaries.filter((p) => !salariesExclus.has(p.employee_id)).map((p) => ({ ...p, societe: s.company_id })),
  );
  const toutLeMonde = cochees.every((s) => s.salaries.every((p) => !salariesExclus.has(p.employee_id)));
  return {
    nombre: retenus.reduce((total, p) => total + p.bulletins, 0),
    companyIds: [...new Set(retenus.map((p) => p.societe))],
    employeeIds: toutLeMonde ? null : retenus.map((p) => p.employee_id),
  };
}

export function libelleGravite(gravite: GraviteRelecture): string {
  return gravite === 'important' ? 'Important' : 'À vérifier';
}
