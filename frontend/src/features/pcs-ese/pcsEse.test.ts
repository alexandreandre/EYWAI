import { describe, expect, it } from 'vitest';
import {
  changementPcsDe,
  doitPreRemplir,
  filtrerRubriques,
  libelleCode,
  texteChangement,
  type PropositionPcs,
  type RubriquePcs,
} from './pcsEse';

const RUBRIQUES: RubriquePcs[] = [
  { code: '623e', libelle: 'Ouvriers qualifiés de la soudure', metiers: ["Soudeur à l'arc, ouvrier qualifié"], ecap: false, public: false },
  { code: '674a', libelle: 'Ouvriers de production non qualifiés : chimie, pharmacie, plasturgie', metiers: ['Soudeur (chimie), ouvrier non qualifié'], ecap: false, public: false },
  { code: '674b', libelle: 'Ouvriers de production non qualifiés de la transformation des viandes', metiers: [], ecap: false, public: false },
  { code: '9999', libelle: 'Profession et catégorie professionnelle non connue ou non communiquée', metiers: [], ecap: false, public: false },
];

const sure = (code = '674a'): PropositionPcs => ({
  code, sur: true, raison: 'Même poste…', regle: 'a', nb_collegues: 2, candidats: [], ecap: false,
});

describe('filtrerRubriques', () => {
  it('sans recherche, tout dans l’ordre de la table', () => {
    expect(filtrerRubriques(RUBRIQUES, '').map((x) => x.rubrique.code)).toEqual(['623e', '674a', '674b', '9999']);
  });
  it('un début de code passe en tête', () => {
    expect(filtrerRubriques(RUBRIQUES, '674').map((x) => x.rubrique.code)).toEqual(['674a', '674b']);
  });
  it('un mot du libellé, sans accent ni majuscule', () => {
    expect(filtrerRubriques(RUBRIQUES, 'PLASTURGIE').map((x) => x.rubrique.code)).toEqual(['674a']);
    expect(filtrerRubriques(RUBRIQUES, 'qualifies de la soudure').map((x) => x.rubrique.code)).toEqual(['623e']);
  });
  it('un métier Insee, avec le métier trouvé', () => {
    const r = filtrerRubriques(RUBRIQUES, 'soud');
    expect(r.map((x) => x.rubrique.code)).toEqual(['623e', '674a']);
    expect(r[1].metier).toBe('Soudeur (chimie), ouvrier non qualifié');
  });
});

describe('doitPreRemplir', () => {
  it('seulement un code vide ou 9999, et seulement si Martine est sûre', () => {
    expect(doitPreRemplir('', sure())).toBe(true);
    expect(doitPreRemplir('9999', sure())).toBe(true);
    expect(doitPreRemplir('674a', sure('625h'))).toBe(false);
    expect(doitPreRemplir('', { ...sure(), sur: false, code: null })).toBe(false);
    expect(doitPreRemplir('', undefined)).toBe(false);
    expect(doitPreRemplir('674a', sure('674a'))).toBe(false);
  });
});

describe('texteChangement', () => {
  it('dit l’ancien code et la date, si le code a bien changé', () => {
    expect(texteChangement({ ancien: '9999', date: '2026-11-06' }, '674a')).toBe(
      'Code changé le 06/11/2026 (avant : 9999). Martine déclare ce changement dans la DSN.',
    );
    expect(texteChangement({ ancien: '9999', date: '2026-11-06' }, '9999')).toBeNull();
    expect(texteChangement(undefined, '674a')).toBeNull();
  });
});

describe('libelleCode', () => {
  it('code et libellé, ou le code seul s’il est inconnu', () => {
    expect(libelleCode(RUBRIQUES, '674a')).toBe('674a — Ouvriers de production non qualifiés : chimie, pharmacie, plasturgie');
    expect(libelleCode(RUBRIQUES, '999a')).toBe('999a');
    expect(libelleCode(RUBRIQUES, '')).toBe('');
  });
});

describe('changementPcsDe', () => {
  it('lit le changement rangé dans la classification', () => {
    expect(changementPcsDe({ pcs: '674a', pcs_changement: { ancien: '9999', date: '2026-11-06' } })).toEqual({
      ancien: '9999',
      date: '2026-11-06',
    });
    expect(changementPcsDe({ pcs: '674a' })).toBeNull();
    expect(changementPcsDe(null)).toBeNull();
    expect(changementPcsDe({ pcs_changement: 'n’importe quoi' })).toBeNull();
  });
});
