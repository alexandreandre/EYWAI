import { describe, expect, it } from 'vitest';

import {
  FORMATS_ACCEPTES_LIBELLE,
  FORMATS_ACCEPTES_ATTRIBUT,
  estFichierTabulaire,
  libelleAnalyseEnCours,
} from './importFormats';
import { filesMissingWeek } from './importWeekAssignments';

describe('importFormats', () => {
  it('annonce tous les formats réellement acceptés, tableurs compris', () => {
    for (const ext of ['PDF', 'JPG', 'PNG', 'CSV', 'Excel']) {
      expect(FORMATS_ACCEPTES_LIBELLE).toContain(ext);
    }
    expect(FORMATS_ACCEPTES_ATTRIBUT).toContain('.csv');
    expect(FORMATS_ACCEPTES_ATTRIBUT).toContain('.xlsx');
  });

  it('reconnaît un fichier tabulaire (CSV, Excel), pas un PDF ni une photo', () => {
    expect(estFichierTabulaire('Releve.CSV')).toBe(true);
    expect(estFichierTabulaire('a.xlsx')).toBe(true);
    expect(estFichierTabulaire('a.xls')).toBe(true);
    expect(estFichierTabulaire('a.pdf')).toBe(false);
    expect(estFichierTabulaire('a.jpg')).toBe(false);
  });

  it("n'annonce l'IA que s'il y a un PDF ou une photo", () => {
    expect(libelleAnalyseEnCours([{ name: 'a.csv' }])).toBe('Lecture du fichier…');
    expect(libelleAnalyseEnCours([{ name: 'a.csv' }, { name: 'b.xlsx' }])).toBe(
      'Lecture du fichier…',
    );
    expect(libelleAnalyseEnCours([{ name: 'a.pdf' }])).toBe('Analyse IA en cours…');
    expect(libelleAnalyseEnCours([{ name: 'a.csv' }, { name: 'b.pdf' }])).toBe(
      'Analyse IA en cours…',
    );
  });

  it("n'exige pas de semaine pour un fichier tabulaire", () => {
    expect(filesMissingWeek([{ name: 'a.csv' }, { name: 'b.pdf' }], {})).toEqual(['b.pdf']);
  });
});
