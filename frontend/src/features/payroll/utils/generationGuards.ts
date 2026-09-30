import { sanitizeBackendMessage } from '@/lib/errorMessages';
import { lireJoursEnConflit, type JourEnConflit } from './heuresSurArret';

/**
 * Gardes de génération des bulletins (lot 3 « génération sûre »).
 *
 * Le backend refuse la génération avec un `detail` structuré `{ code, message }` :
 *   - 422 `calendrier_incomplet` → se force en repostant `force_calendrier_incomplet` ;
 *   - 409 `bulletin_valide`      → se force en repostant `regenerer_bulletin_valide`.
 * Une génération forcée répond alors avec des `warnings` `{ code, message }`
 * (`calendrier_incomplet_force`, `bulletin_valide_regenere`).
 *
 * Un backend plus ancien (detail texte, erreurs de validation FastAPI…) ne
 * produit AUCUN refus structuré : tout retombe sur la gestion d'erreur générique.
 */

export type GenerationRefusalCode =
  | 'calendrier_incomplet'
  | 'bulletin_valide'
  | 'heures_sur_jour_d_arret'
  | 'arrets_illisibles';

/**
 * Les deux refus de calendrier/bulletin se forcent d'un clic explicite. Les deux
 * autres, jamais : `heures_sur_jour_d_arret` ne se règle que par une correction,
 * `arrets_illisibles` que par un nouvel essai.
 */
export const estForcable = (code: GenerationRefusalCode): boolean =>
  code === 'calendrier_incomplet' || code === 'bulletin_valide';

export type RefusalFenetre = {
  debut: string;
  fin: string;
  semaines: number[];
  origine: string;
};

/** Détails de la période à saisir joints au 422 `calendrier_incomplet` (backend ≥ 20/09/2026). */
export type RefusalDetails = {
  fenetre: RefusalFenetre | null;
  joursManquants: string[];
  joursInformatifs: string[];
};

export type GenerationRefusal = {
  code: GenerationRefusalCode;
  message: string;
  details?: RefusalDetails;
  /** Jours où des heures sont saisies sur un arrêt (`heures_sur_jour_d_arret`). */
  jours?: JourEnConflit[];
};

const isoDates = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];

function extractRefusalDetails(detail: Record<string, unknown>): RefusalDetails | undefined {
  const brut = detail as {
    fenetre?: unknown;
    jours_manquants?: unknown;
    jours_informatifs?: unknown;
  };
  if (!('jours_manquants' in brut) && !('fenetre' in brut)) return undefined;
  let fenetre: RefusalFenetre | null = null;
  if (brut.fenetre && typeof brut.fenetre === 'object') {
    const f = brut.fenetre as Partial<RefusalFenetre>;
    if (typeof f.debut === 'string' && typeof f.fin === 'string') {
      fenetre = {
        debut: f.debut,
        fin: f.fin,
        semaines: Array.isArray(f.semaines)
          ? f.semaines.filter((s): s is number => typeof s === 'number')
          : [],
        origine: typeof f.origine === 'string' ? f.origine : 'regle',
      };
    }
  }
  return {
    fenetre,
    joursManquants: isoDates(brut.jours_manquants),
    joursInformatifs: isoDates(brut.jours_informatifs),
  };
}

/** Avertissement structuré renvoyé après un forçage explicite. */
export type GenerationGuardWarning = {
  code: string;
  message: string;
};

const REFUSAL_FALLBACK_MESSAGES: Record<GenerationRefusalCode, string> = {
  calendrier_incomplet:
    'Le calendrier du mois est incomplet : des jours restent à saisir.',
  bulletin_valide: 'Un bulletin validé existe déjà pour cette période.',
  heures_sur_jour_d_arret:
    'Des heures sont saisies un jour d’arrêt ou d’absence : corrigez-les avant de générer le bulletin.',
  arrets_illisibles:
    'Les arrêts du salarié n’ont pas pu être lus, donc rien n’a été calculé. Réessayez dans un instant.',
};

/** Libellés des dialogues de refus (titre, action de forçage, libellé court). */
export const REFUSAL_DIALOG_LABELS: Record<
  GenerationRefusalCode,
  { title: string; actionLabel: string; shortLabel: string }
> = {
  calendrier_incomplet: {
    title: 'Calendrier incomplet',
    actionLabel: 'Générer quand même',
    shortLabel: 'calendrier incomplet',
  },
  bulletin_valide: {
    title: 'Bulletin validé',
    actionLabel: 'Régénérer (archive l’ancienne version)',
    shortLabel: 'bulletin validé',
  },
  heures_sur_jour_d_arret: {
    title: 'Heures saisies un jour d’arrêt',
    actionLabel: 'Corriger les heures',
    shortLabel: 'heures sur un jour d’arrêt',
  },
  arrets_illisibles: {
    title: 'Arrêts illisibles',
    actionLabel: 'Réessayer',
    shortLabel: 'arrêts illisibles',
  },
};

/**
 * Extrait un refus structuré (422 `calendrier_incomplet` / `heures_sur_jour_d_arret`,
 * 409 `bulletin_valide`, 503 `arrets_illisibles`)
 * d'une erreur HTTP. Renvoie `null` pour toute autre erreur — y compris un
 * backend ancien qui répond sans code structuré — afin de laisser la gestion
 * d'erreur générique s'appliquer.
 */
export function extractGenerationRefusal(error: unknown): GenerationRefusal | null {
  if (!error || typeof error !== 'object' || !('response' in error)) return null;
  const response = (error as { response?: { status?: number; data?: unknown } })
    .response;
  if (!response || typeof response !== 'object') return null;
  const { status, data } = response;
  if (status !== 422 && status !== 409 && status !== 503) return null;
  if (!data || typeof data !== 'object') return null;
  const detail = (data as { detail?: unknown }).detail;
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return null;
  const { code, message } = detail as { code?: unknown; message?: unknown };

  let refusalCode: GenerationRefusalCode | null = null;
  if (status === 422 && code === 'calendrier_incomplet') {
    refusalCode = 'calendrier_incomplet';
  } else if (status === 409 && code === 'bulletin_valide') {
    refusalCode = 'bulletin_valide';
  } else if (status === 422 && code === 'heures_sur_jour_d_arret') {
    refusalCode = 'heures_sur_jour_d_arret';
  } else if (status === 503 && code === 'arrets_illisibles') {
    refusalCode = 'arrets_illisibles';
  }
  if (!refusalCode) return null;

  const cleaned =
    typeof message === 'string' ? sanitizeBackendMessage(message) : null;
  const refusal: GenerationRefusal = {
    code: refusalCode,
    message: cleaned ?? REFUSAL_FALLBACK_MESSAGES[refusalCode],
  };
  if (refusalCode === 'calendrier_incomplet') {
    const details = extractRefusalDetails(detail as Record<string, unknown>);
    if (details) refusal.details = details;
  }
  if (refusalCode === 'heures_sur_jour_d_arret') {
    refusal.jours = lireJoursEnConflit((detail as { jours?: unknown }).jours);
  }
  return refusal;
}

/**
 * Normalise les `warnings` de la réponse de génération : le backend y mêle des
 * chaînes (alertes RH du moteur) et des objets `{ code, message }` (gardes
 * forcées). Renvoie les messages affichables et, à part, les avertissements de
 * garde structurés (à remonter en toast).
 */
export function splitGenerationWarnings(warnings: unknown): {
  messages: string[];
  /** Points à arbitrer (`severity: 'info'`) : montrés sans orange, hors du compte des alertes. */
  infos: string[];
  guardWarnings: GenerationGuardWarning[];
} {
  const messages: string[] = [];
  const infos: string[] = [];
  const guardWarnings: GenerationGuardWarning[] = [];
  if (!Array.isArray(warnings)) return { messages, infos, guardWarnings };

  for (const item of warnings) {
    if (typeof item === 'string') {
      if (item.trim()) messages.push(item);
      continue;
    }
    if (item && typeof item === 'object') {
      const { code, message, severity } = item as {
        code?: unknown;
        message?: unknown;
        severity?: unknown;
      };
      if (typeof message !== 'string' || !message.trim()) continue;
      if (severity === 'info') {
        infos.push(message);
        continue;
      }
      messages.push(message);
      if (typeof code === 'string' && code.trim()) {
        guardWarnings.push({ code, message });
      }
    }
  }
  return { messages, infos, guardWarnings };
}
