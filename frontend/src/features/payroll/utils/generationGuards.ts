import { sanitizeBackendMessage } from '@/lib/errorMessages';

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

export type GenerationRefusalCode = 'calendrier_incomplet' | 'bulletin_valide';

export type GenerationRefusal = {
  code: GenerationRefusalCode;
  message: string;
};

/** Avertissement structuré renvoyé après un forçage explicite. */
export type GenerationGuardWarning = {
  code: string;
  message: string;
};

const REFUSAL_FALLBACK_MESSAGES: Record<GenerationRefusalCode, string> = {
  calendrier_incomplet:
    'Le calendrier du mois est incomplet : des jours restent à saisir.',
  bulletin_valide: 'Un bulletin validé existe déjà pour cette période.',
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
};

/**
 * Extrait un refus structuré (422 `calendrier_incomplet` / 409 `bulletin_valide`)
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
  if (status !== 422 && status !== 409) return null;
  if (!data || typeof data !== 'object') return null;
  const detail = (data as { detail?: unknown }).detail;
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return null;
  const { code, message } = detail as { code?: unknown; message?: unknown };

  let refusalCode: GenerationRefusalCode | null = null;
  if (status === 422 && code === 'calendrier_incomplet') {
    refusalCode = 'calendrier_incomplet';
  } else if (status === 409 && code === 'bulletin_valide') {
    refusalCode = 'bulletin_valide';
  }
  if (!refusalCode) return null;

  const cleaned =
    typeof message === 'string' ? sanitizeBackendMessage(message) : null;
  return { code: refusalCode, message: cleaned ?? REFUSAL_FALLBACK_MESSAGES[refusalCode] };
}

/**
 * Normalise les `warnings` de la réponse de génération : le backend y mêle des
 * chaînes (alertes RH du moteur) et des objets `{ code, message }` (gardes
 * forcées). Renvoie les messages affichables et, à part, les avertissements de
 * garde structurés (à remonter en toast).
 */
export function splitGenerationWarnings(warnings: unknown): {
  messages: string[];
  guardWarnings: GenerationGuardWarning[];
} {
  const messages: string[] = [];
  const guardWarnings: GenerationGuardWarning[] = [];
  if (!Array.isArray(warnings)) return { messages, guardWarnings };

  for (const item of warnings) {
    if (typeof item === 'string') {
      if (item.trim()) messages.push(item);
      continue;
    }
    if (item && typeof item === 'object') {
      const { code, message } = item as { code?: unknown; message?: unknown };
      if (typeof message === 'string' && message.trim()) {
        messages.push(message);
        if (typeof code === 'string' && code.trim()) {
          guardWarnings.push({ code, message });
        }
      }
    }
  }
  return { messages, guardWarnings };
}
