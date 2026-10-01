/**
 * Report d'un net à payer négatif sur le mois suivant.
 *
 * Rien n'est viré le mois négatif ; la somme est reprise le mois suivant par
 * une saisie « sur le net » nommée « Report NAP négatif MM/AAAA ». Le calcul
 * ne change pas : on propose seulement la saisie, en un clic.
 */

import type { QueryKey } from '@tanstack/react-query';
import type { EtatReportNetNegatif, SaisieReportNetNegatif } from '@/api/payslips';
import { queryKeys } from '@/lib/queryKeys';
import { extractDetail, getApiErrorStatus, sanitizeBackendMessage } from '@/lib/errorMessages';
import { lienVariablesDuMois } from '@/features/payroll/utils/payslipDerivedLines';
import { clesAInvaliderApresBulletin } from '@/features/payroll/utils/invalidationsBulletin';

export type { EtatReportNetNegatif };

export type ActionReport = 'creer' | 'mettre_a_jour' | 'supprimer';

export interface VueReport {
  visible: boolean;
  texte: string;
  bouton: string | null;
  action: ActionReport | null;
  desactive: boolean;
  explication: string | null;
  lien: string | null;
}

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

function euros(montant: number): string {
  const texte = Math.abs(montant)
    .toFixed(2)
    .replace('.', ',')
    .replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return montant < 0 ? `−${texte}` : texte;
}

function moisEnLettres(annee: number, mois: number): string {
  return `${MOIS[mois - 1]} ${annee}`;
}

/** « de octobre » → « d’octobre ». */
function de(mot: string): string {
  return /^[aeiouyéèâîôûh]/i.test(mot) ? `d’${mot}` : `de ${mot}`;
}

function reportsDe(etat: EtatReportNetNegatif): SaisieReportNetNegatif[] {
  if (etat.saisies && etat.saisies.length > 0) return etat.saisies;
  return etat.saisie ? [etat.saisie] : [];
}

function joindreMontants(saisies: SaisieReportNetNegatif[]): string {
  const textes = saisies.map((s) => `${euros(Math.abs(s.amount))} €`);
  if (textes.length <= 1) return textes[0] ?? '';
  return `${textes.slice(0, -1).join(', ')} et ${textes[textes.length - 1]}`;
}

function montantDuReport(saisie: SaisieReportNetNegatif | null | undefined): number | null {
  return saisie ? Math.round(-saisie.amount * 100) / 100 : null;
}

const CACHEE: VueReport = {
  visible: false,
  texte: '',
  bouton: null,
  action: null,
  desactive: false,
  explication: null,
  lien: null,
};

export function vueDuReport(etat: EtatReportNetNegatif): VueReport {
  const ceMois = moisEnLettres(etat.annee, etat.mois);
  const suivant = moisEnLettres(etat.annee_suivante, etat.mois_suivant);
  const montant = etat.montant_a_reporter;
  const reports = reportsDe(etat);
  const existant = montantDuReport(reports[0] ?? etat.saisie);
  const autre = etat.autre_retenue_sur_le_net;
  const lien = lienVariablesDuMois({
    employeeId: etat.employee_id,
    year: etat.annee_suivante,
    month: etat.mois_suivant,
  });

  let vue: VueReport;
  if (reports.length > 1) {
    vue = {
      ...CACHEE,
      visible: true,
      texte:
        `Plusieurs reports existent déjà en ${suivant} : ${joindreMontants(reports)}. ` +
        'Chacun est déduit du net tant que la ligne existe. ' +
        'Ouvrez les saisies pour n’en garder qu’un.',
      lien,
    };
  } else if (autre && reports.length === 0) {
    vue = {
      ...CACHEE,
      visible: true,
      texte:
        `Une retenue sur le net de ${euros(Math.abs(autre.amount))} € existe déjà en ${suivant}, sous un autre nom. ` +
        'Ouvrez les saisies avant d’ajouter le report.',
      lien,
    };
  } else if (montant > 0 && existant === null) {
    vue = {
      ...CACHEE,
      visible: true,
      texte:
        `Net à payer négatif : ${euros(-montant)} €. Rien ne sera viré en ${ceMois}. ` +
        `Reprenez cette somme en ${suivant}.`,
      bouton: `Reporter ${euros(montant)} € sur ${suivant}`,
      action: 'creer',
    };
  } else if (montant > 0 && existant !== null && Math.abs(existant - montant) < 0.005) {
    vue = { ...CACHEE, visible: true, texte: `Reporté sur ${suivant} (${euros(montant)} €)`, lien };
  } else if (montant > 0 && existant !== null) {
    vue = {
      ...CACHEE,
      visible: true,
      texte: `Report à mettre à jour : ${euros(existant)} € → ${euros(montant)} €`,
      bouton: 'Mettre à jour le report',
      action: 'mettre_a_jour',
      lien,
    };
  } else if (existant !== null) {
    vue = {
      ...CACHEE,
      visible: true,
      texte: `Le net n’est plus négatif : supprimer le report ${de(suivant)} ?`,
      bouton: 'Supprimer le report',
      action: 'supprimer',
      lien,
    };
  } else {
    return CACHEE;
  }

  if (etat.verrou) {
    const geste =
      vue.action === 'supprimer' ? 'impossible d’en retirer le report' : 'impossible d’y reporter la somme';
    vue.desactive = true;
    vue.explication =
      etat.verrou === 'bulletin_valide'
        ? `Le bulletin ${de(suivant)} est déjà validé : ${geste}.`
        : `La paie ${de(suivant)} est clôturée : ${geste}.`;
  }
  return vue;
}

export function messageSuccesReport(action: ActionReport, etat: EtatReportNetNegatif): string {
  const saisies = `saisies ${de(MOIS[etat.mois_suivant - 1])}`;
  const montant = euros(etat.montant_a_reporter);
  if (action === 'creer') return `Report de ${montant} € créé dans les ${saisies}`;
  if (action === 'mettre_a_jour') return `Report mis à jour : ${montant} € dans les ${saisies}`;
  return `Report supprimé des ${saisies}`;
}

const ECHEC: Record<ActionReport, string> = {
  creer: 'Report non créé',
  mettre_a_jour: 'Report non mis à jour',
  supprimer: 'Report non supprimé',
};

export function messageEchecReport(action: ActionReport, erreur: unknown): string {
  const raison = sanitizeBackendMessage(extractDetail(erreur));
  if (raison) return `${ECHEC[action]} : ${raison}`;
  const statut = getApiErrorStatus(erreur);
  const cause = statut
    ? `le serveur n’a pas donné de raison (erreur ${statut})`
    : 'le serveur n’a pas répondu';
  return `${ECHEC[action]} : ${cause}. Réessayez, ou corrigez la saisie depuis l’écran Primes.`;
}

export interface ApiDuReport {
  executer: (payslipId: string, action: ActionReport, companyId: string) => Promise<unknown>;
}

/** L’écriture passe par l’endpoint du report : idempotente, et refusée si le mois suivant est verrouillé. */
export async function executerReport(
  action: ActionReport,
  etat: EtatReportNetNegatif,
  api: ApiDuReport
): Promise<void> {
  await api.executer(etat.payslip_id, action, etat.company_id);
}

/** L'état du report, les bulletins du salarié et la paie du mois. */
export function clesApresReport(companyId: string | undefined, employeeId: string): QueryKey[] {
  return [
    queryKeys.reportNetNegatifTous(companyId),
    queryKeys.saisies(companyId),
    ...clesAInvaliderApresBulletin(companyId, employeeId),
  ];
}
