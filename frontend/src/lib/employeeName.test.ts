import { describe, expect, it } from 'vitest';

import {
  displayLastName,
  displayNameNomPrenom,
  searchableName,
} from './employeeName';

describe('employeeName', () => {
  it("préfère le nom d'usage quand il existe", () => {
    const gaelle = { first_name: 'Gaëlle', last_name: 'KEWITZ', nom_usage: 'BOUALI' };
    expect(displayLastName(gaelle)).toBe('BOUALI');
    expect(displayNameNomPrenom(gaelle)).toBe('BOUALI Gaëlle');
  });

  it('replie sur le nom de naissance sinon', () => {
    expect(displayLastName({ last_name: 'AMATE', nom_usage: null })).toBe('AMATE');
    expect(displayLastName({ last_name: 'AMATE', nom_usage: '  ' })).toBe('AMATE');
  });

  it('la recherche couvre les deux noms', () => {
    const s = searchableName({ first_name: 'Gaëlle', last_name: 'KEWITZ', nom_usage: 'BOUALI' });
    expect(s).toContain('KEWITZ');
    expect(s).toContain('BOUALI');
  });
});
