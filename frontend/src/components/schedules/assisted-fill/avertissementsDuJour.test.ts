import { describe, expect, it } from 'vitest';
import { avertissementsDuJour, avertissementsHorsJour, phraseResume, resumeAvertissements } from './avertissementsDuJour';

const LIGNE = [
  "Jour 1 : Écart journalier 0.03 h au-delà du seuil (pointé 7.53 h vs théorique 7.00 h).",
  "Jour 3 : Entrée 07:28 : 32 min d'avance (> 30 min) — HS à valider.",
  "Jour 3 : Sortie à 04:10 rattachée au poste de nuit de la veille.",
  'Jour 9 : Pointage incomplet : entrée 04:38 sans sortie. Journée à compléter.',
  'Matricule absent du relevé.',
];

describe('avertissements de pointage rangés par jour', () => {
  it("donne les messages d'un jour, sans le préfixe « Jour N : »", () => {
    expect(avertissementsDuJour(LIGNE, 3)).toEqual([
      "Entrée 07:28 : 32 min d'avance (> 30 min) — HS à valider.",
      'Sortie à 04:10 rattachée au poste de nuit de la veille.',
    ]);
    expect(avertissementsDuJour(LIGNE, 4)).toEqual([]);
  });

  it("ne confond pas le jour 1 avec le jour 10 ou 11", () => {
    expect(avertissementsDuJour(['Jour 11 : Pointage incomplet : sortie sans entrée.'], 1)).toEqual([]);
  });

  it('garde à part ce qui ne porte sur aucun jour', () => {
    expect(avertissementsHorsJour(LIGNE)).toEqual(['Matricule absent du relevé.']);
  });

  it('résume les jours à heures en plus et les pointages incomplets, sans compter deux fois un jour', () => {
    expect(resumeAvertissements(LIGNE)).toEqual({ heuresEnPlus: 2, incomplets: 1 });
  });

  it('dit le résumé en clair, et rien quand il n’y a rien', () => {
    expect(phraseResume({ heuresEnPlus: 2, incomplets: 1 })).toBe(
      'Heures en plus à valider : 2 jours · Pointage incomplet : 1 jour',
    );
    expect(phraseResume({ heuresEnPlus: 1, incomplets: 0 })).toBe('Heures en plus à valider : 1 jour');
    expect(phraseResume({ heuresEnPlus: 0, incomplets: 0 })).toBeNull();
  });
});
