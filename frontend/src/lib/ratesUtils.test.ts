import { describe, expect, it } from 'vitest';

import {
  buildRatesSnapshot,
  countChangedCategories,
  formatAvantagesEnNatureAmount,
  formatEffectifRange,
  formatHeuresSupPlage,
  formatIsoDateFr,
  formatPasZone,
  formatPayrollPercent,
  formatRateDisplayValue,
  formatRateKey,
  buildIjPlafondsDisplaySections,
  buildSmicDisplaySections,
  getCategoryTitle,
  resolvePssSections,
  resolveSmicSections,
  getRateDateColor,
  latestCotisationLastCheckedAt,
  pickAvantagesEnNatureValue,
  resolveCotisationLastCheckedAt,
  shouldShowCotisationInRates,
} from '@/lib/ratesUtils';
import type { Cotisation } from '@/lib/ratesUtils';
import { currentMonthKey } from '@/lib/ratesMonthlyAuto';
import type { RatesResponse } from '@/api/rates';

describe('ratesUtils', () => {
  it('detects version and date changes', () => {
    const before = buildRatesSnapshot({
      smic: {
        config_data: {},
        version: 1,
        last_checked_at: '2025-01-01T00:00:00Z',
        comment: null,
        source_links: null,
      },
    });
    const after: RatesResponse = {
      smic: {
        config_data: {},
        version: 2,
        last_checked_at: '2025-02-01T00:00:00Z',
        comment: null,
        source_links: null,
      },
    };
    expect(countChangedCategories(before, after)).toEqual(['smic']);
  });

  it('currentMonthKey returns YYYY-MM', () => {
    expect(currentMonthKey()).toMatch(/^\d{4}-\d{2}$/);
  });

  it('buildSmicDisplaySections supprime les doublons cas général / SMIC horaire brut', () => {
    const rows = buildSmicDisplaySections({
      annee: 2026,
      cas_general: 11.88,
      smic_horaire_brut: 11.88,
      jeune_17_ans: 11.65,
      jeune_moins_17_ans: 11.52,
      smic_mensuel_brut: 1449.93,
      effective_from: '2026-06-01',
      source: 'URSSAF',
    });
    expect(Object.keys(rows)).toEqual([
      'smic_horaire_brut',
      'date_application',
      'jeune_17_ans',
      'jeune_moins_17_ans',
      'smic_mensuel_brut',
    ]);
    expect(rows.cas_general).toBeUndefined();
    expect(rows.source).toBeUndefined();
    expect(rows.date_application).toMatch(/1 juin 2026|01\/06\/2026/);
  });

  it('buildIjPlafondsDisplaySections exclut unite et ne garde que les plafonds', () => {
    const rows = buildIjPlafondsDisplaySections({
      at_mp: 240.49,
      unite: 'EUR/jour',
      maladie: 41.47,
      at_mp_majoree: 320.66,
      maternite_paternite: 104.02,
    });
    expect(Object.keys(rows)).toEqual([
      'at_mp',
      'maladie',
      'at_mp_majoree',
      'maternite_paternite',
    ]);
    expect(rows.unite).toBeUndefined();
  });

  it('resolveSmicSections préfère le format plat et ignore le wrapper legacy', () => {
    const flat = {
      annee: 2026,
      cas_general: 11.88,
      smic_horaire_brut: 11.88,
      smic_mensuel_brut: 1801.8,
      jeune_17_ans: 10.69,
      jeune_moins_17_ans: 9.5,
      smic_horaire: { annee: 2022, cas_general: 12.02 },
    };
    const resolved = resolveSmicSections(flat);
    expect(resolved.annee).toBe(2026);
    expect(resolved.cas_general).toBe(11.88);
    expect(resolved.smic_horaire).toBeUndefined();
  });

  it('formatRateDisplayValue affiche l’année sans décimales ni €', () => {
    expect(formatRateDisplayValue(2026, 'annee')).toBe('2026');
  });

  it('formatRateKey applique accents et libellés métier', () => {
    expect(formatRateKey('annee')).toBe('Année');
    expect(formatRateKey('cas_general')).toBe('Cas général');
    expect(formatRateKey('at_mp_majoree')).toBe('AT/MP majorée');
    expect(formatRateKey('maternite_paternite')).toBe('Maternité / paternité');
    expect(formatRateKey('assiette_cet')).toBe('Assiette CET');
    expect(formatRateKey('brut_plafonne')).toBe('Brut plafonné');
    expect(formatRateKey('teletravail')).toBe('Télétravail');
    expect(formatRateKey('soumise_a_impot')).toBe('Soumise à l’impôt');
  });

  it('getCategoryTitle couvre les barèmes dynamiques', () => {
    expect(getCategoryTitle('heures_supp')).toBe('Heures supplémentaires');
    expect(getCategoryTitle('primes')).toBe('Primes');
    expect(getCategoryTitle('pas')).toBe('Prélèvement à la source (PAS)');
  });

  it('formatPayrollPercent convertit les taux décimaux paie', () => {
    expect(formatPayrollPercent(0.25)).toBe('25,00 %');
    expect(formatPayrollPercent(0.1131)).toBe('11,31 %');
  });

  it('formatHeuresSupPlage décrit les tranches d\'heures supplémentaires', () => {
    expect(formatHeuresSupPlage(1, 8)).toBe('Heures 1 à 8');
    expect(formatHeuresSupPlage(9, null)).toBe(
      'À partir de la 9e heure supplémentaire',
    );
  });

  it('formatEffectifRange décrit les tranches d\'effectif', () => {
    expect(formatEffectifRange(1, 19)).toBe('1 à 19 salariés');
    expect(formatEffectifRange(20, 249)).toBe('20 à 249 salariés');
  });

  it('formatIsoDateFr formate une date ISO', () => {
    expect(formatIsoDateFr('2025-09-05')).toMatch(/2025/);
  });

  it('formatAvantagesEnNatureAmount affiche repas et titre avec unité', () => {
    expect(formatAvantagesEnNatureAmount(5.45, '/ repas')).toMatch(/5,45\s*€.*repas/);
    expect(formatAvantagesEnNatureAmount(7.26, '/ titre')).toMatch(/7,26\s*€.*titre/);
  });

  it('pickAvantagesEnNatureValue lit les clés courtes URSSAF', () => {
    expect(
      pickAvantagesEnNatureValue({ repas: 5.5, titre: 7.32 }, ['repas', 'titre']),
    ).toBe(5.5);
    expect(
      pickAvantagesEnNatureValue(
        { titre_restaurant_exoneration_max_eur: 7.26 },
        ['titre', 'titre_restaurant_exoneration_max_eur'],
      ),
    ).toBe(7.26);
  });

  it('formatRateDisplayValue affiche les forfaits repas en euros', () => {
    expect(formatRateDisplayValue(7.4, 'sur_lieu_travail')).toMatch(/7,40\s*€.*repas/);
    expect(formatRateDisplayValue(21.1, 'hors_locaux_avec_restaurant')).toMatch(/21,10\s*€/);
  });

  it('formatRateDisplayValue applique les unités frais professionnels', () => {
    expect(formatRateDisplayValue(3.25, 'par_jour')).toMatch(/3,25\s*€.*jour/);
    expect(formatRateDisplayValue(71.5, 'limite_mensuelle')).toMatch(/71,50\s*€.*mois/);
    expect(formatRateDisplayValue(600, 'limite_base')).toMatch(/600,00\s*€.*an/);
    expect(formatRateDisplayValue(14, 'repas')).toMatch(/14,00\s*€.*jour/);
    expect(formatRateDisplayValue(84, 'hebergement')).toMatch(/84,00\s*€.*jour/);
    expect(formatRateDisplayValue(5, 'km_min')).toBe('5 km');
    expect(formatRateDisplayValue(12.5, 'montant')).toMatch(/12,50\s*€.*trajet/);
  });

  it('formatPasZone formate les zones PAS', () => {
    expect(formatPasZone('guadeloupe_reunion_martinique')).toBe(
      'Guadeloupe, La Réunion, Martinique',
    );
    expect(formatPasZone('metropole')).toBe('Métropole et hors de France');
  });

  it('getRateDateColor selon l’ancienneté du contrôle', () => {
    const recent = new Date();
    recent.setDate(recent.getDate() - 2);
    expect(getRateDateColor(recent.toISOString())).toContain('emerald');

    const mid = new Date();
    mid.setDate(mid.getDate() - 30);
    expect(getRateDateColor(mid.toISOString())).toContain('amber');

    const old = new Date();
    old.setDate(old.getDate() - 200);
    expect(getRateDateColor(old.toISOString())).toContain('red');

    expect(getRateDateColor(null)).toContain('red');
  });

  it('resolveCotisationLastCheckedAt ne lit que la ligne', () => {
    const coti: Cotisation = {
      id: 'cet',
      libelle: 'CET',
      base: 'assiette_cet',
      last_checked_at: '2026-05-29T12:00:00Z',
    };
    expect(resolveCotisationLastCheckedAt(coti)).toBe('2026-05-29T12:00:00Z');
    expect(resolveCotisationLastCheckedAt({ ...coti, last_checked_at: null })).toBeNull();
  });

  it('latestCotisationLastCheckedAt retient la date la plus récente', () => {
    const items: Cotisation[] = [
      { id: 'a', libelle: 'A', base: 'brut', last_checked_at: '2026-05-01T00:00:00Z' },
      { id: 'b', libelle: 'B', base: 'brut', last_checked_at: '2026-05-29T12:00:00Z' },
    ];
    expect(latestCotisationLastCheckedAt(items)).toBe('2026-05-29T12:00:00Z');
    expect(latestCotisationLastCheckedAt([{ id: 'x', libelle: 'X', base: 'brut' }])).toBeNull();
  });

  it('masque les cotisations gérées en fiche entreprise', () => {
    expect(
      shouldShowCotisationInRates({
        id: 'versement_mobilite',
        libelle: 'Versement mobilité',
        base: 'brut',
        patronal: 'specifique_entreprise',
      }),
    ).toBe(false);
    expect(
      shouldShowCotisationInRates({
        id: 'csg',
        libelle: 'CSG',
        base: 'brut',
        patronal: 0.092,
      }),
    ).toBe(true);
  });

  it('formatRateDisplayValue corrige les périodes de séjour', () => {
    expect(
      formatRateDisplayValue(
        'au-delà du 24emois et jusqu’au 72emois',
        'periode_sejour',
      ),
    ).toBe('Au-delà du 24e mois et jusqu’au 72e mois');
    expect(formatRateDisplayValue(true, 'soumise_a_impot')).toBe('Oui');
  });
});
