import { describe, expect, it } from 'vitest';
import {
  filterCollectiveAgreements,
  matchesCollectiveAgreementSearch,
} from './collectiveAgreementSearch';

const sampleAgreements = [
  {
    name: 'Convention collective nationale de la plasturgie',
    idcc: '1297',
    sector: 'Plasturgie',
    description: 'Industrie des plastiques',
  },
  {
    name: 'Convention collective Syntec',
    idcc: '1486',
    sector: 'Informatique',
    description: "Bureaux d'études",
  },
];

describe('collectiveAgreementSearch', () => {
  it('matches sector keywords without accents', () => {
    expect(matchesCollectiveAgreementSearch(sampleAgreements[0], 'plasturgie')).toBe(true);
    expect(matchesCollectiveAgreementSearch(sampleAgreements[1], 'informatique')).toBe(true);
  });

  it('matches multiple natural language tokens', () => {
    expect(matchesCollectiveAgreementSearch(sampleAgreements[0], 'industrie plastiques')).toBe(true);
    expect(matchesCollectiveAgreementSearch(sampleAgreements[0], 'industrie syntec')).toBe(false);
  });

  it('ranks exact idcc first', () => {
    const ranked = filterCollectiveAgreements(sampleAgreements, '1486');
    expect(ranked[0]?.idcc).toBe('1486');
  });
});
