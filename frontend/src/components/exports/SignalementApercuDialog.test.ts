// La fenêtre d'aperçu, rendue sans navigateur (vitest en environnement node,
// sans bibliothèque DOM) : rendu statique du corps, et le bouton « Valider le
// format » lu dans l'arbre React. Données fictives.
import { createElement, isValidElement, type ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { SignalementApercu } from '@/api/exports';

vi.mock('@/api/exports', () => ({
  apercuSignalement: vi.fn(),
  genererSignalement: vi.fn(),
}));
vi.mock('@/contexts/CompanyContext', () => ({
  useCompany: () => ({ activeCompany: { company_id: 'societe-exemple' } }),
}));

import * as api from '@/api/exports';
import { ApercuCorps } from './SignalementApercuDialog';
import { PHRASE_BRUT, PHRASE_TETE } from './signalementApercu';

/** NIR fictif laissé en clair, comme si le serveur avait oublié de le masquer. */
const NIR_FICTIF = '1850175123456';

const APERCU: SignalementApercu = {
  nature: '04',
  libelle_nature: "Signalement d'arrêt de travail",
  essai: false,
  nir_masque: true,
  blocs: [
    {
      code: 'S10.G00.00',
      libelle: 'Envoi',
      partie: 'envoi',
      rubriques: [{ code: 'S10.G00.00.008', libelle: "Type de l'envoi", valeur: '01', traduction: 'déclaration réelle' }],
    },
    {
      code: 'S21.G00.06',
      libelle: 'Entreprise',
      partie: 'entreprise',
      rubriques: [{ code: 'S21.G00.06.001', libelle: 'SIREN', valeur: '000000000', traduction: null }],
    },
    {
      code: 'S21.G00.30',
      libelle: 'Individu',
      partie: 'salarie',
      rubriques: [
        { code: 'S21.G00.30.001', libelle: "Numéro d'inscription au répertoire", valeur: NIR_FICTIF, traduction: null },
        { code: 'S21.G00.30.002', libelle: 'Nom de famille', valeur: 'DUPONT', traduction: null },
      ],
    },
    {
      code: 'S21.G00.60',
      libelle: 'Arrêt de travail',
      partie: 'evenement',
      rubriques: [
        { code: 'S21.G00.60.001', libelle: "Motif de l'arrêt", valeur: '01', traduction: 'maladie' },
        { code: 'S21.G00.60.004', libelle: 'Subrogation', valeur: '02', traduction: 'non' },
      ],
    },
  ],
  brut: [
    "S10.G00.00.008,'01'",
    "S21.G00.06.001,'000000000'",
    `S21.G00.30.001,'${NIR_FICTIF}'`,
    "S21.G00.30.002,'DUPONT'",
    "S21.G00.60.001,'01'",
    '',
  ].join('\r\n'),
};

type Props = Parameters<typeof ApercuCorps>[0];

function props(sur: Partial<Props> = {}): Props {
  return {
    apercu: APERCU,
    chargement: false,
    erreur: null,
    onReessayer: vi.fn(),
    onValider: vi.fn(),
    ...sur,
  };
}

/** Le texte visible du rendu, entités décodées. */
function texte(p: Props): string {
  return renderToStaticMarkup(createElement(ApercuCorps, p))
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ');
}

/** Le bouton dont le texte est donné, cherché dans l'arbre rendu par le corps. */
function bouton(noeud: ReactNode, libelle: string): { onClick: () => void } | null {
  if (Array.isArray(noeud)) {
    for (const n of noeud) {
      const trouve = bouton(n, libelle);
      if (trouve) return trouve;
    }
    return null;
  }
  if (!isValidElement(noeud)) return null;
  const p = noeud.props as { children?: ReactNode; onClick?: () => void };
  if (p.children === libelle && p.onClick) return { onClick: p.onClick };
  return bouton(p.children, libelle);
}

describe("fenêtre d'aperçu d'un signalement", () => {
  beforeEach(() => vi.clearAllMocks());

  it('dit en tête que rien n’est envoyé, puis montre les blocs en clair', () => {
    const t = texte(props());
    expect(t).toContain(PHRASE_TETE);
    expect(t).toContain('Salarié');
    expect(t).toContain('Entreprise et établissement');
    expect(t).toContain('Événement');
    expect(t).toContain('S21.G00.60.001');
    expect(t).toContain("Motif de l'arrêt");
    expect(t).toContain('maladie');
    expect(t).toContain('En clair');
    expect(t).toContain('Fichier brut');
  });

  it('ne montre jamais le NIR en entier, ni en clair ni dans le fichier brut', () => {
    const clair = texte(props());
    expect(clair).toContain('18•••••••••56');
    expect(clair).not.toContain(NIR_FICTIF);
    const brut = texte(props({ onglet: 'brut' }));
    expect(brut).toContain("S21.G00.30.001,'18•••••••••56'");
    expect(brut).not.toContain(NIR_FICTIF);
  });

  it("l'onglet « Fichier brut » montre le texte du fichier et dit ce qui est masqué", () => {
    const t = texte(props({ onglet: 'brut' }));
    expect(t).toContain(PHRASE_BRUT);
    expect(t).toContain("S21.G00.60.001,'01'");
    expect(t).toContain("S21.G00.30.002,'DUPONT'");
  });

  it('dit quand il prépare, et dit le message du serveur en cas d’échec', () => {
    expect(texte(props({ apercu: undefined, chargement: true }))).toContain("Préparation de l'aperçu…");
    const echec = texte(props({
      apercu: undefined,
      erreur: { response: { data: { detail: 'Signalement impossible : nom manquant sur la fiche du salarié.' } } },
    }));
    expect(echec).toContain('Signalement impossible : nom manquant sur la fiche du salarié.');
    expect(echec).toContain('Réessayer');
    expect(texte(props({ apercu: undefined, erreur: new Error('réseau') }))).toContain(
      "L'aperçu n'a pas pu être construit : réessayez.",
    );
  });

  it('« Valider le format » ferme seulement : aucun appel, ni génération ni aperçu', () => {
    const p = props();
    const valider = bouton(ApercuCorps(p), 'Valider le format');
    expect(valider).not.toBeNull();
    valider!.onClick();
    expect(p.onValider).toHaveBeenCalledTimes(1);
    expect(api.genererSignalement).not.toHaveBeenCalled();
    expect(api.apercuSignalement).not.toHaveBeenCalled();
  });
});
