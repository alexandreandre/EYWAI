import { describe, expect, it } from 'vitest';

import { formatCatalogConventionName } from './collectiveAgreementDisplay';

describe('formatCatalogConventionName', () => {
  it('tronque les extensions légales après le titre principal', () => {
    const full =
      "Convention collective nationale des ouvriers employés par les entreprises du bâtiment non visées par le décret du 1er mars 1962 (c'est-à-dire occupant plus de 10 salariés) du 8 octobre 1990. Etendue par arrêté du 8 février 1991 JORF 12 février 1991.";
    expect(formatCatalogConventionName(full)).toBe(
      'Convention collective nationale des ouvriers employés par les entreprises du bâtiment non visées par le décret du 1er mars 1962'
    );
  });

  it('conserve un titre déjà court', () => {
    expect(formatCatalogConventionName('Convention collective IDCC 1486')).toBe(
      'Convention collective IDCC 1486'
    );
  });
});
