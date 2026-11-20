import { describe, expect, it } from 'vitest';

import {
  MESSAGE_AUCUN_BULLETIN_VALIDE,
  messageSansBulletinDeReference,
  TEXTE_PAS_DE_BULLETIN,
  messageComparaisonMoisDernier,
  sousTitreComparaisonValidee,
  titreComparaisonMoisDernier,
} from './comparaisonMoisDernier';

describe('messageComparaisonMoisDernier', () => {
  it('sans bulletin le mois dernier : la phrase, aucun chiffre inventé', () => {
    expect(messageComparaisonMoisDernier(null)).toBe(TEXTE_PAS_DE_BULLETIN);
    expect(messageComparaisonMoisDernier(undefined)).toBe(TEXTE_PAS_DE_BULLETIN);
    expect(messageComparaisonMoisDernier({ present: false, texte: TEXTE_PAS_DE_BULLETIN })).toBe(
      TEXTE_PAS_DE_BULLETIN
    );
    expect(messageComparaisonMoisDernier({ present: false, texte: TEXTE_PAS_DE_BULLETIN })).not.toMatch(
      /€|→|\d/
    );
  });

  it('affiche le texte déjà calculé, sans recalculer la paie', () => {
    const texte =
      'Brut : 2 000,00 € → 2 100,00 € · Net : 1 500,00 € → 1 600,00 € · Heures sup : 8 h → 12 h · Absences : 0 h → 14 h';
    expect(
      messageComparaisonMoisDernier({
        present: true,
        texte,
        brut: { avant: 2000, apres: 2100 },
      })
    ).toBe(texte);
  });

  it('un texte vide n’invente pas de montants', () => {
    expect(messageComparaisonMoisDernier({ present: true, texte: '  ' })).toBe(
      TEXTE_PAS_DE_BULLETIN
    );
  });
});

describe('la référence de chaque comparaison est nommée', () => {
  it('l’encadré « Ce qui a changé » compare au mois civil précédent, validé ou non', () => {
    expect(titreComparaisonMoisDernier(2026, 9)).toBe(
      'Ce qui a changé par rapport à août 2026 (bulletin validé ou non)'
    );
    expect(titreComparaisonMoisDernier(2026, 1)).toBe(
      'Ce qui a changé par rapport à décembre 2025 (bulletin validé ou non)'
    );
    expect(titreComparaisonMoisDernier(2026, 3)).toContain('février 2026');
  });

  it('sans mois connu, il dit quand même quelle référence il prend', () => {
    expect(titreComparaisonMoisDernier(undefined, undefined)).toBe(
      'Ce qui a changé par rapport au mois civil précédent (bulletin validé ou non)'
    );
  });

  it('l’onglet « Comparaison N-1 » compare au dernier bulletin validé et dit lequel', () => {
    expect(sousTitreComparaisonValidee(6, 2026)).toBe(
      'Analyse automatique par rapport au dernier bulletin validé : juin 2026.'
    );
    expect(sousTitreComparaisonValidee(null, null)).toBe(
      'Analyse automatique par rapport au dernier bulletin validé, qui n’existe pas encore.'
    );
  });

  it('sans bulletin validé, l’onglet renvoie à l’autre comparaison', () => {
    expect(MESSAGE_AUCUN_BULLETIN_VALIDE).toContain('Aucun bulletin validé avant ce mois');
    expect(MESSAGE_AUCUN_BULLETIN_VALIDE).toContain('mois civil précédent, validé ou non');
  });
});

describe('mois précédent repris de l’ancien logiciel (Zone 404, 20/11)', () => {
  const r12Repris = {
    rule_id: 'R12',
    message: "Septembre vient de l'ancien logiciel : pas de comparaison du net.",
  };

  it('l’encadré dit la vraie raison au lieu de « aucun bulletin validé »', () => {
    const msg = messageSansBulletinDeReference([r12Repris]);
    expect(msg.startsWith("Septembre vient de l'ancien logiciel : pas de comparaison du net.")).toBe(
      true
    );
    expect(msg).not.toContain('Aucun bulletin validé');
  });

  it('sans mois repris, le message habituel', () => {
    expect(
      messageSansBulletinDeReference([
        { rule_id: 'R12', message: 'Aucun bulletin N-1 validé trouvé pour la comparaison.' },
      ])
    ).toBe(MESSAGE_AUCUN_BULLETIN_VALIDE);
    expect(messageSansBulletinDeReference([])).toBe(MESSAGE_AUCUN_BULLETIN_VALIDE);
  });

  it('le sous-titre ne parle plus d’un bulletin validé qui « n’existe pas »', () => {
    expect(sousTitreComparaisonValidee(null, null, true)).toBe(
      'Analyse automatique par rapport au dernier bulletin calculé par Martine, qui n’existe pas encore.'
    );
  });
});
