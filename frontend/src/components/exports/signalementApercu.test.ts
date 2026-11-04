import { describe, expect, it } from 'vitest';
import type { SignalementApercuBloc } from '@/api/exports';
import {
  detailErreurApercu,
  ERREUR_PAR_DEFAUT,
  grouperParPartie,
  masquerNir,
  masquerNirDansBrut,
} from './signalementApercu';

const bloc = (code: string, partie: SignalementApercuBloc['partie']): SignalementApercuBloc => ({
  code,
  libelle: code,
  partie,
  rubriques: [],
});

describe('masquerNir', () => {
  it('garde les 2 premiers et les 2 derniers chiffres, et la longueur', () => {
    expect(masquerNir('1850175123456')).toBe('18•••••••••56');
    expect(masquerNir('1850175123456')).toHaveLength(13);
  });

  it('laisse telle quelle une valeur déjà masquée ou trop courte', () => {
    expect(masquerNir('18•••••••••56')).toBe('18•••••••••56');
    expect(masquerNir('1234')).toBe('1234');
    expect(masquerNir('')).toBe('');
  });
});

describe('masquerNirDansBrut', () => {
  it('masque la seule ligne du NIR, le reste du texte ne bouge pas', () => {
    const brut = "S21.G00.30.001,'1850175123456'\r\nS21.G00.30.002,'DUPONT'\r\nS21.G00.40.001,'01012026'\r\n";
    expect(masquerNirDansBrut(brut)).toBe(
      "S21.G00.30.001,'18•••••••••56'\r\nS21.G00.30.002,'DUPONT'\r\nS21.G00.40.001,'01012026'\r\n",
    );
  });
});

describe('grouperParPartie', () => {
  it("regroupe les blocs voisins d'une même partie, dans l'ordre du fichier", () => {
    const parties = grouperParPartie([
      bloc('S10.G00.00', 'envoi'),
      bloc('S10.G00.01', 'envoi'),
      bloc('S21.G00.30', 'salarie'),
      bloc('S21.G00.40', 'contrat'),
      bloc('S21.G00.60', 'evenement'),
    ]);
    expect(parties.map((p) => [p.libelle, p.blocs.length])).toEqual([
      ['Envoi', 2],
      ['Salarié', 1],
      ['Contrat', 1],
      ['Événement', 1],
    ]);
  });
});

describe('detailErreurApercu', () => {
  it('dit le message du serveur, sinon la phrase par défaut', () => {
    const err = { response: { data: { detail: 'Signalement impossible : nom manquant sur la fiche du salarié.' } } };
    expect(detailErreurApercu(err)).toBe('Signalement impossible : nom manquant sur la fiche du salarié.');
    expect(detailErreurApercu(new Error('réseau'))).toBe(ERREUR_PAR_DEFAUT);
    expect(detailErreurApercu(null)).toBe(ERREUR_PAR_DEFAUT);
  });
});
