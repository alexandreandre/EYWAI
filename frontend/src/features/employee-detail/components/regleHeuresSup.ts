import type { HsRoutingPolicy, RegleHeuresSupSalarie } from '@/api/modulation';

/** Les trois choix de la fiche ; « societe » vaut null en base. */
export type ChoixRegleHeuresSup = 'societe' | 'pay_all' | 'account_all';

export function choixDeLaRegle(regle: RegleHeuresSupSalarie): ChoixRegleHeuresSup {
  return regle ?? 'societe';
}

export function regleDuChoix(choix: ChoixRegleHeuresSup): RegleHeuresSupSalarie {
  return choix === 'societe' ? null : choix;
}

const REGLE_DE_LA_SOCIETE: Record<HsRoutingPolicy, string> = {
  pay_all: 'heures sup payées au bulletin',
  account_all: 'toutes les heures sup au compteur de récupération',
  franchise: 'les premières heures sup du mois au compteur, le reste payé',
  manual: 'heures sup payées ou mises au compteur au cas par cas, chaque mois',
};

/** La phrase qui dit, sous le choix, ce qui arrive aux heures sup du salarié. */
export function phraseDuChoix(choix: ChoixRegleHeuresSup, regleSociete: HsRoutingPolicy): string {
  if (choix === 'pay_all') {
    return 'Ses heures sup sont payées sur son bulletin chaque mois, quelle que soit la règle de la société (alternants, par exemple).';
  }
  if (choix === 'account_all') {
    return 'Ses heures sup vont toujours à son compteur de récupération (au-delà du plafond, elles sont payées).';
  }
  return `Comme les autres salariés : ${REGLE_DE_LA_SOCIETE[regleSociete]}.`;
}

/** La ligne de l'écran du compteur de la société ; null quand personne n'a sa règle. */
export function phraseSalariesReglePropre(nombre: number | undefined): string | null {
  if (!nombre || nombre <= 0) return null;
  const sujet = nombre === 1 ? '1 salarié suit' : `${nombre} salariés suivent`;
  const fiche = nombre === 1 ? 'sa fiche' : 'leur fiche';
  return `${sujet} une autre règle, posée sur ${fiche} (onglet « Primes et autres »).`;
}
