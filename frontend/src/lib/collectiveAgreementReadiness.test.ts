import { describe, expect, it } from 'vitest';
import {
  getReadiness,
  getReadinessFromRulesStatus,
  getReadinessLabel,
  getTextAvailabilityLabel,
  extractLegifranceUrlFromDescription,
  hasCachedTextFromSource,
} from './collectiveAgreementReadiness';

describe('getReadiness', () => {
  it('retourne missing sans texte ni règles', () => {
    expect(getReadiness({ hasText: false, hasRules: false })).toBe('missing');
  });

  it('retourne ready avec règles complètes et grille', () => {
    expect(
      getReadiness({
        hasText: true,
        hasRules: true,
        hasPayrollGrid: true,
        completudeNiveau: 'complet',
      })
    ).toBe('ready');
  });

  it('retourne partial avec règles partielles', () => {
    expect(
      getReadiness({
        hasText: true,
        hasRules: true,
        hasPayrollGrid: true,
        completudeNiveau: 'partiel',
      })
    ).toBe('partial');
  });

  it('retourne partial avec texte seul', () => {
    expect(getReadiness({ hasText: true, hasRules: false })).toBe('partial');
  });

  it('retourne partial avec règles seules sans complétude complet', () => {
    expect(getReadiness({ hasText: false, hasRules: true })).toBe('partial');
  });
});

describe('getReadinessLabel', () => {
  it('mappe les trois niveaux', () => {
    expect(getReadinessLabel('ready')).toBe('Prêt pour la paie');
    expect(getReadinessLabel('partial')).toBe('Partiellement configuré');
    expect(getReadinessLabel('missing')).toBe('À configurer');
  });
});

describe('getTextAvailabilityLabel', () => {
  it('indique la disponibilité du texte', () => {
    expect(getTextAvailabilityLabel(true)).toBe('Texte officiel');
    expect(getTextAvailabilityLabel(false)).toBe('Texte manquant');
  });
});

describe('extractLegifranceUrlFromDescription', () => {
  it('extrait l’URL Légifrance depuis la description KALI', () => {
    const url = extractLegifranceUrlFromDescription(
      'Convention métallurgie\n\nSource Légifrance : https://www.legifrance.gouv.fr/conv_coll/id/KALICONT123/'
    );
    expect(url).toBe('https://www.legifrance.gouv.fr/conv_coll/id/KALICONT123/');
  });

  it('retourne null si absent', () => {
    expect(extractLegifranceUrlFromDescription(null)).toBeNull();
    expect(extractLegifranceUrlFromDescription('Sans lien')).toBeNull();
  });
});

describe('getReadinessFromRulesStatus', () => {
  it('dérive le statut depuis rules-status', () => {
    expect(
      getReadinessFromRulesStatus({
        has_rules: true,
        text_source: 'kali',
        rules: {
          completude: { niveau: 'complet' },
          salaires_minima: [{ coefficient: 240, valeur: 2500 }],
        },
      })
    ).toBe('ready');
  });

  it('retourne missing si status absent', () => {
    expect(getReadinessFromRulesStatus(null)).toBe('missing');
  });
});

describe('hasCachedTextFromSource', () => {
  it('accepte kali, text et pdf', () => {
    expect(hasCachedTextFromSource('kali')).toBe(true);
    expect(hasCachedTextFromSource('text')).toBe(true);
    expect(hasCachedTextFromSource('pdf')).toBe(true);
    expect(hasCachedTextFromSource(null)).toBe(false);
  });
});
