import { describe, expect, it } from 'vitest';

import { listeDeMoisEnClair, periodeEnClair } from './payrollMonth';

/**
 * Tournage du 20/10/2026 : « Mois manquants : 2026-06… » dans la carte
 * « Reprise de la paie » des paramètres paie, et la période « 2026-10 » de
 * l'aperçu de la DSN. L'application écrit le mois en toutes lettres, comme
 * l'historique des exports (« Octobre 2026 »).
 */
describe('mois en clair', () => {
  it('« 2026-10 » se lit « Octobre 2026 »', () => {
    expect(periodeEnClair('2026-10')).toBe('Octobre 2026');
  });

  it('une valeur illisible reste telle quelle', () => {
    expect(periodeEnClair('')).toBe('');
    expect(periodeEnClair('T3 2026')).toBe('T3 2026');
  });

  it('une liste de mois, dans une phrase : « juin 2026, juillet 2026 »', () => {
    expect(listeDeMoisEnClair(['2026-06', '2026-07'])).toBe('juin 2026, juillet 2026');
  });
});

describe('écrans qui montraient des mois au format machine', () => {
  it.each([
    'features/dsn-import/components/DsnSyncModeCard.tsx',
    'features/company/components/CompanyDsnCoverageBand.tsx',
    'pages/admin/super/CompanyDetails.tsx',
  ])('%s : mois manquants en clair', async (fichier) => {
    const { readFileSync } = await import('node:fs');
    const path = await import('node:path');
    const texte = readFileSync(path.resolve(__dirname, '../../..', fichier), 'utf8');
    expect(texte).not.toMatch(/gaps\.join\(/);
    expect(texte).toMatch(/Mois manquants : \{listeDeMoisEnClair\(/);
  });

  it('l’aperçu et le résultat d’un export disent la période en clair', async () => {
    const { readFileSync } = await import('node:fs');
    const path = await import('node:path');
    const texte = readFileSync(path.resolve(__dirname, '../../../components/exports/ExportCommonModel.tsx'), 'utf8');
    expect(texte).toContain('{periodeEnClair(selectedPeriod)}');
    expect(texte).toContain('{periodeEnClair(generateResponse.period)}');
  });
});
