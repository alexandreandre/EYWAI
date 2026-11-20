/**
 * Interrupteur « Tenir un compteur de récupération » de la carte Heures
 * supplémentaires : il ouvre le compteur (soldes, repos pris, bulletin) sans
 * toucher au paiement des heures sup.
 *
 * Moteur vérifié (modulation/payroll_hook.py) : avec la règle « payées »
 * (pay_all) et le compteur ouvert, le calendrier n'est pas touché et toutes les
 * heures sup restent payées ; seule une décision du mois prise pour un salarié
 * (« Mettre ces heures au compteur ») en met au compteur.
 */
import type { ModulationSettings } from '@/api/modulation';

export type EtatInterrupteurCompteur = {
  allume: boolean;
  /** Faux quand les heures sup vont au compteur : le compteur est alors indispensable. */
  modifiable: boolean;
  explication: string;
};

export function etatInterrupteurCompteur(
  reglage: Pick<
    ModulationSettings,
    'hour_account_enabled' | 'recovery_absence_enabled' | 'hs_routing_policy'
  >,
): EtatInterrupteurCompteur {
  const allume = Boolean(reglage.hour_account_enabled && reglage.recovery_absence_enabled);
  if (reglage.hour_account_enabled && reglage.hs_routing_policy !== 'pay_all') {
    return {
      allume: true,
      modifiable: false,
      explication:
        'Toujours tenu : les heures sup vont au compteur. Pour le couper, choisissez d’abord « Payées au bulletin ».',
    };
  }
  return {
    allume,
    modifiable: true,
    explication: allume
      ? 'Les heures sup restent payées. Le compteur s’affiche sur la fiche de chaque salarié (onglet Soldes) : vous pouvez y saisir un solde ou des repos pris, et le bulletin le montre dès qu’il y a un solde. Le couper le masque des fiches et des bulletins ; les soldes saisis restent enregistrés.'
      : 'Les heures sup restent payées. Allumé, le compteur s’affiche sur la fiche de chaque salarié (onglet Soldes) pour y saisir un solde ou des repos pris.',
  };
}

/** Ce qu'on envoie au serveur : les deux interrupteurs, jamais la règle de paiement. */
export function reglageCompteur(allumer: boolean): {
  hour_account_enabled: boolean;
  recovery_absence_enabled: boolean;
} {
  return { hour_account_enabled: allumer, recovery_absence_enabled: allumer };
}

/** Où s'allume le compteur, pour la fiche salarié. */
export const LIEN_REGLAGE_COMPTEUR = '/company?tab=paie&section=temps-travail';

/**
 * Phrase sous les soldes de la fiche salarié quand le compteur n'est pas tenu :
 * la ligne « Récupération » manque, on dit pourquoi et où l'allumer.
 * Rien tant que le réglage n'est pas lu (pas de fausse alerte au chargement).
 */
export function phraseCompteurCoupe(
  reglage:
    | Pick<ModulationSettings, 'hour_account_enabled' | 'recovery_absence_enabled' | 'hs_routing_policy'>
    | undefined,
): string | null {
  if (!reglage) return null;
  if (etatInterrupteurCompteur(reglage).allume) return null;
  return 'Pas de ligne Récupération : la société ne tient pas de compteur de récupération. Il s’allume dans Société › Paie › Temps de travail, carte Heures supplémentaires (« Tenir un compteur de récupération »).';
}
