/**
 * Le brut d'une prime pour un net voulu, dans la fenêtre des primes (lot 30).
 *
 * La fenêtre demande le mode « prime » du calcul inverse : le brut qui ajoute
 * le net voulu au net à payer avant impôt sur le revenu du bulletin du mois du salarié (son salaire et
 * ses saisies), et non le brut d'un bulletin entier dont le net vaudrait ce
 * montant. Elle dit ensuite ce que le brut proposé représente.
 */

import type { ReverseCalculationRequest, ReverseCalculationResponse } from '@/api/simulation';

const FORMAT_EUROS = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const MOIS = [
  'janvier',
  'février',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'août',
  'septembre',
  'octobre',
  'novembre',
  'décembre',
];

/** « d’octobre 2026 », « de mai 2026 ». */
function duMois(month: number, year: number): string {
  const nom = MOIS[month - 1] ?? '';
  return /^[aeiouyéèêàâîôû]/i.test(nom) ? `d’${nom} ${year}` : `de ${nom} ${year}`;
}

export function requeteBrutDeLaPrime(params: {
  employeeId: string;
  netVoulu: number;
  month: number;
  year: number;
  soumiseACotisations: boolean;
  soumiseAImpot: boolean;
}): ReverseCalculationRequest {
  return {
    employee_id: params.employeeId,
    net_target: params.netVoulu,
    net_type: 'net_a_payer',
    month: params.month,
    year: params.year,
    mode: 'prime',
    prime_soumise_a_cotisations: params.soumiseACotisations,
    prime_soumise_a_impot: params.soumiseAImpot,
  };
}

type ResultatPrime = Pick<
  ReverseCalculationResponse,
  'brut_calcule' | 'net_obtenu' | 'ecart' | 'convergence' | 'cout_employeur' | 'month' | 'year'
>;

/** Ce que le brut proposé représente, dit sous le champ de la fenêtre. */
export function phraseBrutDeLaPrime(resultat: ResultatPrime): string {
  const { brut_calcule: brut, net_obtenu: net, ecart, convergence, cout_employeur: cout } = resultat;
  const voulu = net - ecart;
  const ajoute = convergence
    ? FORMAT_EUROS.format(net)
    : `${FORMAT_EUROS.format(net)} (${FORMAT_EUROS.format(voulu)} voulus)`;
  const mois = resultat.month && resultat.year ? ` ${duMois(resultat.month, resultat.year)}` : '';
  return (
    `Une prime de ${FORMAT_EUROS.format(brut)} bruts ajoute ${ajoute} au net à payer avant impôt sur le revenu${mois} ` +
    'de ce salarié : calcul sur son bulletin du mois (son salaire et les saisies déjà ' +
    `enregistrées). Coût pour l’employeur : ${FORMAT_EUROS.format(cout)}. ` +
    'Le net visé est avant impôt sur le revenu : le taux personnel du salarié n’y entre pas.'
  );
}

/** Un calcul du brut de la prime : sa phrase, et le montant et les cases qu'elle décrit. */
export type CalculBrutDeLaPrime = {
  texte: string;
  montant: number;
  soumiseACotisations: boolean;
  soumiseAImpot: boolean;
};

/**
 * La phrase à afficher sous le champ : celle du calcul tant que le montant et
 * les cases « soumise » de la prime sont ceux qu'elle décrit ; null sinon.
 */
export function explicationAffichee(
  calcul: CalculBrutDeLaPrime | null,
  saisie: { amount: number | ''; is_socially_taxed: boolean; is_taxable: boolean }
): string | null {
  if (!calcul || saisie.amount === '') return null;
  const memeMontant = Math.abs(Number(saisie.amount) - calcul.montant) < 0.005;
  const memesCases =
    saisie.is_socially_taxed === calcul.soumiseACotisations &&
    saisie.is_taxable === calcul.soumiseAImpot;
  return memeMontant && memesCases ? calcul.texte : null;
}

/** Ce que la fenêtre dit pendant le calcul (lot 31) : « Calcul sur le bulletin d’octobre 2026 de ce salarié… ». */
export function messageDuCalculEnCours(month: number, year: number): string {
  return `Calcul sur le bulletin ${duMois(month, year)} de ce salarié…`;
}

/**
 * Un seul calcul à la fois : un second clic pendant le calcul ne relance rien.
 * `prendre()` dit si le calcul peut partir ; `rendre()` le libère, qu'il ait
 * réussi ou non.
 */
export function verrouDuCalcul(): { prendre: () => boolean; rendre: () => void } {
  let enCours = false;
  return {
    prendre: () => {
      if (enCours) return false;
      enCours = true;
      return true;
    },
    rendre: () => {
      enCours = false;
    },
  };
}
