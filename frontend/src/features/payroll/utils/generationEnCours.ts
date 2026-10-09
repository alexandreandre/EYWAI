/**
 * La génération du mois tourne dans le navigateur, bulletin par bulletin.
 * Quitter la page l'arrêtait sans un mot, et fermer le suivi effaçait les
 * échecs (revue du 05/10). Ici : le bandeau, la question avant de quitter, le
 * récapitulatif des échecs et la note laissée quand la page est quittée quand
 * même.
 */

import { monthYearLabel } from './payrollMonth';

export const CLE_INTERRUPTION = 'eywai.paie.generationInterrompue';

export const RAISON_ECHEC_INCONNUE =
  'La génération a échoué sans message : ouvrez la ligne et relancez-la.';

export type InterruptionGeneration = {
  companyId: string;
  faits: number;
  total: number;
};

export type EntreeJournalGeneration = {
  id: string;
  employeeId: string;
  employeeName: string;
  year: number;
  month: number;
  status: 'success' | 'warning' | 'error';
  error?: string;
};

export type EchecGeneration = {
  cle: string;
  employeeId: string;
  nom: string;
  mois: string;
  raison: string;
};

type Stockage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export function libelleBandeauGeneration(faits: number, total: number): string {
  return `Génération en cours (${faits}/${total}) : ne quittez pas cette page.`;
}

export function questionQuitterGeneration(faits: number, total: number): string {
  const restants = Math.max(0, total - faits);
  return (
    `Une génération est en cours (${faits}/${total}). Quitter la page l’arrête : ` +
    `${restants > 1 ? `les ${restants} bulletins restants ne seront pas générés` : 'le bulletin restant ne sera pas généré'}. ` +
    'Quitter quand même ?'
  );
}

/**
 * Un clic sur ce lien remplace-t-il la page par une autre page de
 * l'application ? Un autre site déclenche déjà la question du navigateur.
 */
export function lienQuitteLaPage(
  lien: { href: string | null; target: string | null; download: boolean },
  ici: { origin: string; pathname: string }
): boolean {
  const href = lien.href?.trim();
  if (!href || href.startsWith('#')) return false;
  if (lien.download) return false;
  if (lien.target && lien.target !== '_self') return false;
  let url: URL;
  try {
    url = new URL(href, ici.origin);
  } catch {
    return false;
  }
  if (url.origin !== ici.origin) return false;
  return url.pathname !== ici.pathname;
}

export function recapitulatifEchecs(journal: readonly EntreeJournalGeneration[]): EchecGeneration[] {
  return journal
    .filter((entree) => entree.status === 'error')
    .map((entree) => ({
      cle: entree.id,
      employeeId: entree.employeeId,
      nom: entree.employeeName,
      mois: monthYearLabel(entree.month, entree.year),
      raison: entree.error?.trim() || RAISON_ECHEC_INCONNUE,
    }));
}

export function noterInterruption(stockage: Stockage | null | undefined, info: InterruptionGeneration): void {
  try {
    stockage?.setItem(CLE_INTERRUPTION, JSON.stringify(info));
  } catch {
    // Stockage plein ou interdit : la note est une aide, pas une garde.
  }
}

export function lireInterruption(
  stockage: Stockage | null | undefined,
  companyId: string | null | undefined
): InterruptionGeneration | null {
  if (!stockage || !companyId) return null;
  try {
    const brut = stockage.getItem(CLE_INTERRUPTION);
    if (!brut) return null;
    const info = JSON.parse(brut) as Partial<InterruptionGeneration>;
    if (info.companyId !== companyId) return null;
    if (typeof info.faits !== 'number' || typeof info.total !== 'number') return null;
    return { companyId: info.companyId, faits: info.faits, total: info.total };
  } catch {
    return null;
  }
}

export function oublierInterruption(stockage: Stockage | null | undefined): void {
  try {
    stockage?.removeItem(CLE_INTERRUPTION);
  } catch {
    // Rien à faire.
  }
}

export function phraseInterruption(info: InterruptionGeneration): string {
  return (
    `La dernière génération s’est arrêtée quand la page a été quittée : ` +
    `${info.faits} bulletin${info.faits > 1 ? 's' : ''} sur ${info.total} traité${info.faits > 1 ? 's' : ''}. ` +
    'Les autres sont encore « À générer » : relancez « Générer le mois ».'
  );
}

export type PhaseModaleGeneration = 'select' | 'running' | 'done';

/**
 * Phase de la fenêtre de génération groupée d'après celle du suivi. Quand le
 * suivi revient au repos en pleine génération (annulation), la fenêtre revient
 * à la sélection : sans cela elle restait sur « Génération en cours… », sans
 * bouton ni fermeture possible.
 */
export function phaseModaleApres(
  phaseSuivi: 'idle' | 'running' | 'done',
  phaseFenetre: PhaseModaleGeneration
): PhaseModaleGeneration {
  if (phaseSuivi === 'running') return 'running';
  if (phaseSuivi === 'done') return 'done';
  return phaseFenetre === 'running' ? 'select' : phaseFenetre;
}

/** Ce que dit Martine quand la RH arrête une génération en cours. */
export function phraseAnnulation(generes: number, total: number, enCours: boolean): string {
  const restants = Math.max(0, total - generes);
  const faits =
    generes === 0
      ? 'aucun bulletin généré'
      : `${generes} bulletin${generes > 1 ? 's' : ''} généré${generes > 1 ? 's' : ''}`;
  let phrase = `Génération arrêtée : ${faits} sur ${total}.`;
  if (restants === 1) phrase += ' Le bulletin restant reste « À générer ».';
  else if (restants > 1) phrase += ` Les ${restants} autres restent « À générer ».`;
  if (enCours) phrase += ' Le bulletin en cours au moment de l’arrêt est à vérifier.';
  return phrase;
}

/**
 * Phrase sous le suivi une fois la génération terminée. La fermeture
 * automatique n'est annoncée que là où elle a lieu (fenêtre du Mode Groupé) :
 * sur la page Paie, le suivi reste jusqu'à ce qu'on le ferme.
 */
export function texteFinDeSuivi(
  journal: readonly { status: 'success' | 'warning' | 'error' }[],
  fermetureAutomatique: boolean
): string | null {
  if (journal.some((e) => e.status === 'error')) return null;
  if (journal.some((e) => e.status === 'warning')) {
    return 'Des bulletins ont été générés avec des alertes — ouvrez-les pour corriger.';
  }
  return fermetureAutomatique ? 'Fermeture automatique dans quelques secondes…' : null;
}
