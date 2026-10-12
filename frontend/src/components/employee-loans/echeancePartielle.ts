/**
 * L'explication d'une échéance de prêt retenue en partie, pour le volet du
 * prêt : la même règle que l'alerte du bulletin (rejeu G.3, 11/10/2026).
 */

type Echeance = {
  installment_number: number;
  year: number;
  month: number;
  total_due: number;
  capital_paid?: number;
  interest_paid?: number;
  status: string;
};

const FORMAT_EUROS = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const centimes = (valeur: number) => Math.round(valeur * 100) / 100;

/** Une échéance entamée sans être soldée : « Partielle » au volet du prêt. */
export function estEcheancePartielle(echeance: Echeance): boolean {
  const preleve = (echeance.capital_paid ?? 0) + (echeance.interest_paid ?? 0);
  if (echeance.status === 'partial') return true;
  return echeance.status === 'pending' && preleve > 0;
}

/** Combien, sur combien, la règle et le sort du reliquat ; null sinon. */
export function explicationEcheancePartielle(echeance: Echeance): string | null {
  if (!estEcheancePartielle(echeance)) return null;
  const preleve = centimes((echeance.capital_paid ?? 0) + (echeance.interest_paid ?? 0));
  const reliquat = centimes(Math.max(0, echeance.total_due - preleve));
  const periode = `${String(echeance.month).padStart(2, '0')}/${echeance.year}`;
  return (
    `Échéance n° ${echeance.installment_number} (${periode}) : ` +
    `${FORMAT_EUROS.format(preleve)} retenus sur ${FORMAT_EUROS.format(echeance.total_due)} prévus. ` +
    'Chaque mois, la retenue est limitée au dixième du salaire exigible (article L3251-3 ' +
    "du Code du travail), dans la limite du net à payer ; l'alerte du bulletin donne le détail. " +
    `Le reliquat de ${FORMAT_EUROS.format(reliquat)} reste dû : il sera retenu seul sur le ` +
    "bulletin suivant, et les échéances suivantes glissent d'un mois."
  );
}

type EcheanceDuTableau = Echeance & { id?: string };

type RetenueSurBulletin = {
  installment_id?: string | null;
  year: number;
  month: number;
};

/** La période d'une ligne du tableau ; `prevue` : celle de l'échéancier, si elle a glissé. */
export type PeriodeEcheance = { periode: string; prevue: string | null };

const indexMois = (year: number, month: number) => year * 12 + (month - 1);

const libellePeriode = (index: number) =>
  `${String((index % 12) + 1).padStart(2, '0')}/${Math.floor(index / 12)}`;

/**
 * Pour chaque échéance, dans l'ordre reçu, le premier bulletin qui pourra la
 * retenir. La règle est celle de la paie (`get_unsettled_installments_for_payroll`) :
 * un bulletin retient au plus une échéance par prêt, la plus ancienne non
 * soldée, et jamais avant sa période. Une échéance retenue en partie reprend
 * donc son reliquat seule au bulletin suivant, et les suivantes glissent.
 * Les échéances payées ou ignorées gardent leur période.
 */
export function periodesDesEcheances(
  echeances: EcheanceDuTableau[],
  retenues: RetenueSurBulletin[]
): PeriodeEcheance[] {
  const ordre = [...echeances].sort((a, b) => a.installment_number - b.installment_number);
  const parNumero = new Map<number, PeriodeEcheance>();
  let dernierBulletin: number | null = null;
  const occuper = (index: number) => {
    dernierBulletin = dernierBulletin === null ? index : Math.max(dernierBulletin, index);
  };
  for (const echeance of ordre) {
    const propre = indexMois(echeance.year, echeance.month);
    const sansGlissement = { periode: libellePeriode(propre), prevue: null };
    const bulletins = retenues
      .filter((r) => echeance.id && r.installment_id === echeance.id)
      .map((r) => indexMois(r.year, r.month));
    const derniereRetenue = bulletins.length ? Math.max(...bulletins) : null;
    if (echeance.status === 'skipped') {
      parNumero.set(echeance.installment_number, sansGlissement);
    } else if (echeance.status === 'paid') {
      occuper(derniereRetenue ?? propre);
      parNumero.set(echeance.installment_number, sansGlissement);
    } else if (estEcheancePartielle(echeance)) {
      // Le reliquat est repris seul au bulletin qui suit la dernière retenue.
      occuper((derniereRetenue ?? propre) + 1);
      parNumero.set(echeance.installment_number, sansGlissement);
    } else {
      const premier: number =
        dernierBulletin === null ? propre : Math.max(propre, dernierBulletin + 1);
      occuper(premier);
      parNumero.set(echeance.installment_number, {
        periode: libellePeriode(premier),
        prevue: premier === propre ? null : libellePeriode(propre),
      });
    }
  }
  return echeances.map(
    (e) =>
      parNumero.get(e.installment_number) ?? {
        periode: libellePeriode(indexMois(e.year, e.month)),
        prevue: null,
      }
  );
}

/** La légende du tableau quand une période a glissé ; null sinon. */
export function legendePeriodesDecalees(periodes: PeriodeEcheance[]): string | null {
  if (!periodes.some((p) => p.prevue)) return null;
  return (
    "Un bulletin ne retient qu'une échéance par prêt : quand une échéance est retenue " +
    'en partie, les suivantes glissent. La période affichée est celle du premier ' +
    "bulletin qui pourra les retenir ; « prévue » rappelle la date de l'échéancier."
  );
}
