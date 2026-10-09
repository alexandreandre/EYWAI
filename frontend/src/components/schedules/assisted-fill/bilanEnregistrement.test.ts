import { describe, expect, it } from 'vitest';
import {
  joursEcritsDuLot,
  phraseAlertesMasquees,
  phraseEcartsOcr,
  phraseEnregistrement,
  phraseEnregistrementPartiel,
  phraseHorsReleve,
  phraseJoursEnConflit,
  phraseJoursPreserves,
} from './bilanEnregistrement';

describe('joursEcritsDuLot', () => {
  it('prend le nombre de jours écrits du résumé du lot', () => {
    expect(joursEcritsDuLot({ committed_days: 3 }, [{ days: [{ nature: 'reel' }, { nature: 'prevu' }] }])).toBe(3);
  });

  it('sans résumé, ne compte que les jours réels (pas le prévu)', () => {
    expect(
      joursEcritsDuLot(undefined, [
        { days: [{ nature: 'reel' }, { nature: 'prevu' }, { nature: 'reel' }, { nature: 'prevu' }] },
      ]),
    ).toBe(2);
  });
});

describe('phraseEnregistrement', () => {
  it('accorde salarié et jour, sans « (s) »', () => {
    expect(phraseEnregistrement(1, 3)).toBe('1 salarié · 3 jours mis à jour.');
    expect(phraseEnregistrement(2, 1)).toBe('2 salariés · 1 jour mis à jour.');
    expect(phraseEnregistrement(1, 0)).toBe('1 salarié · 0 jour mis à jour.');
  });
});

describe('phrases accordées de la revue', () => {
  it('jours portant des heures sur un arrêt ou une absence', () => {
    expect(phraseJoursEnConflit(3)).toBe(
      '3 jours portent des heures alors que le planning les marque en arrêt ou en absence : le bulletin sera refusé tant que ce n’est pas corrigé (voir détail).',
    );
    expect(phraseJoursEnConflit(1)).toBe(
      '1 jour porte des heures alors que le planning le marque en arrêt ou en absence : le bulletin sera refusé tant que ce n’est pas corrigé (voir détail).',
    );
  });

  it('jours laissés en l’état', () => {
    expect(phraseJoursPreserves(2)).toBe('2 jours laissés en l’état : absence validée (voir détail).');
    expect(phraseJoursPreserves(1)).toBe('1 jour laissé en l’état : absence validée (voir détail).');
  });

  it('enregistrement partiel', () => {
    expect(phraseEnregistrementPartiel(12, 2)).toBe('12 jours · 2 échecs.');
    expect(phraseEnregistrementPartiel(1, 1)).toBe('1 jour · 1 échec.');
  });

  it('écarts vision/OCR et alertes masquées', () => {
    expect(phraseEcartsOcr(2)).toBe('2 écarts vision/OCR — vérifiez les heures signalées.');
    expect(phraseEcartsOcr(1)).toBe('1 écart vision/OCR — vérifiez les heures signalées.');
    expect(phraseAlertesMasquees(3)).toBe('3 alertes masquées (salariés hors PDF)');
    expect(phraseAlertesMasquees(1)).toBe('1 alerte masquée (salarié hors PDF)');
    expect(phraseHorsReleve(2)).toBe('2 salariés du roster absents du relevé — normal, non affichés.');
    expect(phraseHorsReleve(1)).toBe('1 salarié du roster absent du relevé — normal, non affiché.');
  });
});
