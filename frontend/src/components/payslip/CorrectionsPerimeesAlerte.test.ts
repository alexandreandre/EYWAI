import { describe, expect, it } from 'vitest';
import { phraseCorrectionsPerimees } from './CorrectionsPerimeesAlerte';

describe('phraseCorrectionsPerimees', () => {
  it('ne dit rien sans correction périmée', () => {
    expect(phraseCorrectionsPerimees([{ libelle: 'Salaire de base', alerte: null }])).toBeNull();
  });
  it('nomme la ligne et demande de la garder ou la retirer', () => {
    const p = phraseCorrectionsPerimees([
      { libelle: 'Salaire de base', alerte: 'Martine calcule maintenant 2 500,00 €' },
      { libelle: 'Prime', alerte: null },
    ]);
    expect(p).toContain('1 ligne corrigée');
    expect(p).toContain('« Salaire de base »');
    expect(p).toContain('la garder ou la retirer');
  });
  it('accorde au pluriel', () => {
    const p = phraseCorrectionsPerimees([
      { libelle: 'A', alerte: 'x' },
      { libelle: 'B', alerte: 'y' },
    ]);
    expect(p).toContain('2 lignes corrigées');
    expect(p).toContain('Les corrections restent appliquées');
  });
});
