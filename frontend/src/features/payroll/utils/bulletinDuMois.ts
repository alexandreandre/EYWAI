/**
 * Le bulletin d'un mois, par contrat (D3).
 *
 * Un mois où un contrat finit et un autre commence a deux bulletins : celui du
 * contrat de la fiche (clé nulle), et celui du contrat rangé, qui porte
 * `contract_period_id`. « Le bulletin du mois » est le premier : c'est lui
 * que la paie du mois génère, contrôle et valide sur la ligne du salarié.
 */

type BulletinDuMois = {
  year: number;
  month: number;
  contract_period_id?: string | null;
};

/** Le bulletin du contrat de la fiche pour ce mois. */
export function bulletinDuMois<T extends BulletinDuMois>(
  bulletins: readonly T[] | undefined,
  year: number,
  month: number,
): T | undefined {
  return (bulletins ?? []).find(
    (b) => b.year === year && b.month === month && !b.contract_period_id,
  );
}

/** Les bulletins des contrats rangés qui finissent ce mois-là. */
export function bulletinsDuContratPrecedent<T extends BulletinDuMois>(
  bulletins: readonly T[] | undefined,
  year: number,
  month: number,
): T[] {
  return (bulletins ?? []).filter(
    (b) =>
      b.year === year && b.month === month && Boolean(b.contract_period_id),
  );
}
