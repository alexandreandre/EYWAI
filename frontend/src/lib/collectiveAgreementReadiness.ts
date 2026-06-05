export type ReadinessLevel = 'ready' | 'partial' | 'missing';

export type CompletudeNiveau = 'complet' | 'partiel' | 'inconnu' | string | undefined;

export function hasPayrollGridFromRules(
  rules?: Record<string, unknown> | null
): boolean {
  if (!rules) return false;
  const legacy = rules.salaires_minima as unknown[] | undefined;
  if (Array.isArray(legacy) && legacy.length > 0) return true;
  const grilles = rules.grilles_salaires as Array<{ minima?: unknown[] }> | undefined;
  return Boolean(
    grilles?.some((g) => Array.isArray(g.minima) && g.minima.length > 0)
  );
}

export function getPayrollGridUnavailableReason(status?: {
  has_rules?: boolean;
  latest_log_error?: string | null;
  rules?: Record<string, unknown> | null;
} | null): string | null {
  if (!status) return 'Statut des règles paie indisponible.';
  if (hasPayrollGridFromRules(status.rules)) return null;
  if (status.latest_log_error) {
    return status.latest_log_error;
  }
  if (status.has_rules) {
    const completude = status.rules?.completude as
      | { avertissements?: string[] }
      | undefined;
    const hint = completude?.avertissements?.[0];
    if (hint) return hint;
    return 'Aucune grille salariale extraite — relancez « Mettre à jour » depuis Légifrance.';
  }
  return 'Règles paie non extraites — importez ou mettez à jour la convention.';
}

export function getReadiness(params: {
  hasText: boolean;
  hasRules: boolean;
  hasPayrollGrid?: boolean;
  completudeNiveau?: CompletudeNiveau;
}): ReadinessLevel {
  const { hasText, hasRules, hasPayrollGrid, completudeNiveau } = params;

  if (!hasText && !hasRules && !hasPayrollGrid) {
    return 'missing';
  }

  if (hasPayrollGrid && hasText && completudeNiveau === 'complet') {
    return 'ready';
  }

  if (hasPayrollGrid && hasText) {
    return 'partial';
  }

  if (hasRules || hasText) {
    return 'partial';
  }

  return 'missing';
}

export function getReadinessLabel(level: ReadinessLevel): string {
  switch (level) {
    case 'ready':
      return 'Prêt pour la paie';
    case 'partial':
      return 'Partiellement configuré';
    default:
      return 'À configurer';
  }
}

export function getTextAvailabilityLabel(hasText: boolean): string {
  return hasText ? 'Texte officiel' : 'Texte manquant';
}

/** Extrait l'URL Légifrance stockée dans la description catalogue (import KALI). */
export function extractLegifranceUrlFromDescription(
  description?: string | null
): string | null {
  if (!description) return null;
  const match = description.match(/Source Légifrance\s*:\s*(https?:\/\/\S+)/i);
  if (!match?.[1]) return null;
  return match[1].replace(/[)\],.]+$/, '');
}

export function getReadinessFromRulesStatus(status?: {
  has_rules?: boolean;
  text_source?: string | null;
  rules?: Record<string, unknown> | null;
} | null): ReadinessLevel {
  if (!status) return 'missing';

  const hasText =
    status.text_source === 'kali' ||
    status.text_source === 'text' ||
    status.text_source === 'pdf';

  const completude = status.rules?.completude as { niveau?: CompletudeNiveau } | undefined;

  return getReadiness({
    hasText,
    hasRules: Boolean(status.has_rules),
    hasPayrollGrid: hasPayrollGridFromRules(status.rules),
    completudeNiveau: completude?.niveau,
  });
}

export function hasCachedTextFromSource(textSource?: string | null): boolean {
  return textSource === 'kali' || textSource === 'text' || textSource === 'pdf';
}
