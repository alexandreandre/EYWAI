/**
 * Modes de dépôt de la DSN proposés à l'écran.
 *
 * Il n'existe pas de certificat électronique pour déposer une DSN : le
 * déclarant est une personne (SIRET, nom, prénom, mot de passe). Le mode
 * `api_certificat` n'est donc plus proposé ; il reste dans le type et en base,
 * et une configuration qui l'aurait encore s'affiche lisiblement, sans planter.
 *
 * L'envoi direct par l'API (mode `api_declarant`) n'est pas branché : il est
 * montré, mais ne se choisit pas, pour ne rien promettre.
 */
import type { TransmissionMode } from '@/api/netEntreprises';

export interface ModeDepotOption {
  value: string;
  label: string;
  hint: string;
  /** false : visible dans la liste, mais non sélectionnable. */
  selectionnable: boolean;
}

const RIEN_NE_PART =
  "Rien ne part automatiquement : la DSN reste à déposer à la main sur net-entreprises.fr. Choisissez « Dépôt manuel » puis enregistrez.";

export const MODES_DEPOT_PROPOSES: readonly ModeDepotOption[] = [
  {
    value: 'manual',
    label: 'Dépôt manuel',
    hint: 'Martine prépare le fichier DSN ; le déclarant le dépose lui-même sur net-entreprises.fr, avec son compte.',
    selectionnable: true,
  },
  {
    value: 'api_declarant',
    label: 'Envoi direct par Martine (pas encore disponible)',
    hint: `L'envoi direct n'est pas encore branché. ${RIEN_NE_PART}`,
    selectionnable: false,
  },
];

/** Libellé d'un mode qui n'est plus proposé, ou inconnu de l'écran. */
function optionHorsListe(mode: string): ModeDepotOption {
  if (mode === 'api_certificat') {
    return {
      value: mode,
      label: 'Envoi par l’API (ancien réglage, inactif)',
      hint: `Ce réglage n'est plus proposé. ${RIEN_NE_PART}`,
      selectionnable: false,
    };
  }
  return {
    value: mode,
    label: `Réglage inconnu (${mode || 'vide'})`,
    hint: `Ce réglage n'est pas reconnu par l'écran. ${RIEN_NE_PART}`,
    selectionnable: false,
  };
}

/**
 * Options à afficher pour un mode enregistré : la liste proposée, plus le
 * mode enregistré s'il n'en fait pas partie (sinon la liste resterait muette).
 */
export function optionsModeDepot(modeEnregistre: TransmissionMode | string): ModeDepotOption[] {
  const proposes = [...MODES_DEPOT_PROPOSES];
  if (proposes.some((o) => o.value === modeEnregistre)) return proposes;
  return [...proposes, optionHorsListe(modeEnregistre)];
}

/** L'option qui décrit le mode enregistré (libellé et explication). */
export function optionModeDepot(modeEnregistre: TransmissionMode | string): ModeDepotOption {
  return (
    MODES_DEPOT_PROPOSES.find((o) => o.value === modeEnregistre) ?? optionHorsListe(modeEnregistre)
  );
}
