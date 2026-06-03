import { describe, expect, it } from 'vitest';

import {
  classifyRateSourceLinks,
  getComplementarySourceLabel,
  getOfficialSourceLabel,
  isLegisocialSourceUrl,
  isOfficialSourceUrl,
} from '@/lib/rateSourceLinks';

describe('rateSourceLinks', () => {
  it('identifie les domaines officiels et LegiSocial', () => {
    expect(isOfficialSourceUrl('https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/montant-smic.html')).toBe(true);
    expect(isOfficialSourceUrl('https://www.ameli.fr/entreprise/vos-salaries/montants-reference/indemnites-journalieres-montants-maximum')).toBe(true);
    expect(isOfficialSourceUrl('https://entreprendre.service-public.gouv.fr/vosdroits/F78')).toBe(true);
    expect(isOfficialSourceUrl('https://boss.gouv.fr/accueil/frais-professionnels.html')).toBe(true);
    expect(isOfficialSourceUrl('https://www.legisocial.fr/reperes-sociaux/montant-smic-2026.html')).toBe(false);
    expect(isLegisocialSourceUrl('https://www.legisocial.fr/reperes-sociaux/montant-smic-2026.html')).toBe(true);
  });

  it('libellés officiels par institution', () => {
    expect(getOfficialSourceLabel('https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/montant-smic.html')).toBe('URSSAF — SMIC');
    expect(getOfficialSourceLabel('https://www.ameli.fr/entreprise/vos-salaries/montants-reference/indemnites-journalieres-montants-maximum')).toBe('Ameli.fr — Plafonds IJSS');
    expect(getOfficialSourceLabel('https://www.agirc-arrco.fr/')).toBe('AGIRC ARRCO');
    expect(
      getOfficialSourceLabel('https://entreprendre.service-public.gouv.fr/vosdroits/F78'),
    ).toBe('Service-Public Entreprises — Prévoyance');
    expect(getOfficialSourceLabel('https://travail-emploi.gouv.fr/droit-du-travail/temps-de-travail/article/les-heures-supplementaires')).toBe('Ministère du Travail — Heures sup.');
  });

  it('libellés LegiSocial pour recoupement', () => {
    expect(getComplementarySourceLabel('https://www.legisocial.fr/reperes-sociaux/plafond-securite-sociale-2026.html')).toBe('LegiSocial — PSS');
    expect(getComplementarySourceLabel('https://www.legisocial.fr/reperes-sociaux/taux-cotisations-sociales-urssaf-2026.html')).toBe('LegiSocial — Cotisations');
  });

  it('sépare officiel et recoupement', () => {
    const { official, complementary } = classifyRateSourceLinks([
      'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/montant-smic.html',
      'https://www.legisocial.fr/reperes-sociaux/montant-smic-2026.html',
      'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/montant-smic.html',
    ]);
    expect(official).toHaveLength(1);
    expect(official[0].label).toBe('URSSAF — SMIC');
    expect(complementary).toHaveLength(1);
    expect(complementary[0].label).toBe('LegiSocial — SMIC');
  });
});
