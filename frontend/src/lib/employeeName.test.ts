import { describe, expect, it } from 'vitest';

import {
  displayLastName,
  displayNameNomPrenom,
  searchableName,
} from './employeeName';

describe('employeeName', () => {
  it("préfère le nom d'usage quand il existe", () => {
    const gaelle = { first_name: 'Gaëlle', last_name: 'ROSINET', nom_usage: 'CAVOTIN' };
    expect(displayLastName(gaelle)).toBe('CAVOTIN');
    expect(displayNameNomPrenom(gaelle)).toBe('CAVOTIN Gaëlle');
  });

  it('replie sur le nom de naissance sinon', () => {
    expect(displayLastName({ last_name: 'BARAGUE', nom_usage: null })).toBe('BARAGUE');
    expect(displayLastName({ last_name: 'BARAGUE', nom_usage: '  ' })).toBe('BARAGUE');
  });

  it('la recherche couvre les deux noms', () => {
    const s = searchableName({ first_name: 'Gaëlle', last_name: 'ROSINET', nom_usage: 'CAVOTIN' });
    expect(s).toContain('ROSINET');
    expect(s).toContain('CAVOTIN');
  });
});
