import { describe, expect, it } from 'vitest';
import {
  changementPcsDe,
  doitPreRemplir,
  prochainEtat,
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

describe('filtrerRubriques : intitulés de poste (B11, 10/11)', () => {
  const PEINTRES: RubriquePcs[] = [
    ...RUBRIQUES,
    {
      code: '624f',
      libelle: 'Ouvriers qualifiés des traitements thermiques et de surface sur métaux',
      metiers: ['Peintre carrossier (industrie), ouvrier qualifié', 'Peintre (industrie), ouvrier qualifié'],
      ecap: false,
      public: false,
    },
    { code: '681b', libelle: 'Ouvriers non qualifiés du second oeuvre du bâtiment', metiers: ['Peintre (btp), ouvrier non qualifié'], ecap: false, public: false },
  ];
  it('« peintre industriel » trouve « Peintre (industrie) » : chaque mot, même racine', () => {
    const r = filtrerRubriques(PEINTRES, 'peintre industriel');
    expect(r.map((x) => x.rubrique.code)).toEqual(['624f']);
    expect(r[0].metier).toBe('Peintre carrossier (industrie), ouvrier qualifié');
  });
  it('« préparateur peintre » sans métier qui ait les deux mots : les lignes au plus de mots', () => {
    expect(filtrerRubriques(PEINTRES, 'préparateur peintre').map((x) => x.rubrique.code)).toEqual(['624f', '681b']);
  });
  it('le code des collègues au même poste passe en tête quand on cherche un mot du poste', () => {
    const r = filtrerRubriques(PEINTRES, 'peintre', {
      poste: 'Préparateur peintre',
      proposes: [{ code: '674a', raison: '4 collègues sur 6 de Colorplast, au même poste, en 674a.' }],
    });
    expect(r.map((x) => x.rubrique.code)).toEqual(['674a', '624f', '681b']);
    expect(r[0].propose).toBe('4 collègues sur 6 de Colorplast, au même poste, en 674a.');
  });
  it('et aussi sans recherche ; pas pour un mot étranger au poste', () => {
    const options = { poste: 'Préparateur peintre', proposes: [{ code: '674a', raison: 'collègues' }] };
    expect(filtrerRubriques(PEINTRES, '', options)[0].rubrique.code).toBe('674a');
    expect(filtrerRubriques(PEINTRES, 'soudeur', options).map((x) => x.rubrique.code)).toEqual(['623e', '674a']);
    expect(filtrerRubriques(PEINTRES, 'soudeur', options)[1].propose).toBeNull();
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
  it('dit l’ancien code, la date et la DSN qui le déclare, si le code a bien changé', () => {
    expect(texteChangement({ ancien: '9999', date: '2026-11-06' }, '674a')).toBe(
      'Code changé le 06/11/2026 (avant : 9999) : Martine déclare l’ancien code dans la DSN de novembre 2026.',
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

const pasSure = (): PropositionPcs => ({
  code: null, sur: false, raison: 'Les collègues…', regle: 'a', nb_collegues: 2,
  candidats: [{ code: '674a', libelle: 'x', raison: 'y', ecap: false }], ecap: false,
});

describe('prochainEtat : le pré-remplissage suit la proposition sans écraser la RH', () => {
  it('remplit un code vide ou 9999 quand Martine est sûre', () => {
    expect(prochainEtat({ valeur: '9999', prerempli: null, rhAChoisi: false, proposition: sure('674a') })).toEqual({
      code: '674a',
      prerempli: { code: '674a', avant: '9999' },
    });
  });
  it('remplace son propre code quand la proposition change (statut passé à cadre)', () => {
    expect(
      prochainEtat({ valeur: '674a', prerempli: { code: '674a', avant: '' }, rhAChoisi: false, proposition: sure('387c') }),
    ).toEqual({ code: '387c', prerempli: { code: '387c', avant: '' } });
  });
  it('retire son propre code quand elle n’est plus sûre', () => {
    expect(
      prochainEtat({ valeur: '674a', prerempli: { code: '674a', avant: '9999' }, rhAChoisi: false, proposition: pasSure() }),
    ).toEqual({ code: '9999', prerempli: null });
  });
  it('remplit de nouveau après une remise à zéro du formulaire', () => {
    expect(
      prochainEtat({ valeur: '9999', prerempli: { code: '674a', avant: '9999' }, rhAChoisi: false, proposition: sure('674a') }),
    ).toEqual({ code: '674a', prerempli: { code: '674a', avant: '9999' } });
  });
  it('ne touche jamais au choix de la RH', () => {
    expect(prochainEtat({ valeur: '9999', prerempli: null, rhAChoisi: true, proposition: sure('674a') })).toBeNull();
    expect(
      prochainEtat({ valeur: '625h', prerempli: { code: '674a', avant: '' }, rhAChoisi: true, proposition: sure('387c') }),
    ).toBeNull();
  });
  it('ne fait rien pendant le chargement, ni sur un vrai code déjà là', () => {
    expect(prochainEtat({ valeur: '674a', prerempli: { code: '674a', avant: '' }, rhAChoisi: false, proposition: undefined })).toBeNull();
    expect(prochainEtat({ valeur: '625h', prerempli: null, rhAChoisi: false, proposition: sure('674a') })).toBeNull();
    expect(prochainEtat({ valeur: '674a', prerempli: { code: '674a', avant: '' }, rhAChoisi: false, proposition: sure('674a') })).toBeNull();
  });
});
