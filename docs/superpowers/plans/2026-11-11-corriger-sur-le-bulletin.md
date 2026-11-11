# Corriger sur le bulletin : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** remplacer le contenu de l'onglet « Corriger » du bulletin par le bulletin lui-même, corrigeable ligne par ligne (crayon, poubelle, « Ajouter une ligne » en 4 tuiles, motifs en un clic, bandeau d'étapes, un bouton « Appliquer », puis net avant/après et « Annuler »).

**Architecture:** tout est côté écran. La logique pure va dans un nouveau fichier `features/payroll/utils/bulletinACorriger.ts`, testé en unitaire (vitest). Les composants vont dans `components/payslip-edit/bulletin-a-corriger/`. L'état reste `EtatCorrections` et l'enregistrement reste `editPayslip` (variables du mois + recalcul complet) : aucun calcul ne change. « Annuler » restaure la dernière version archivée (`restorePayslipVersion`). Les composants sont vérifiés par Playwright sur un bulletin fictif intercepté (comme `06-edition-bulletin.spec.ts`), le projet n'ayant pas de test de composant.

**Tech Stack:** React 18, TypeScript, TanStack Query, composants `@/components/ui/*` (shadcn), lucide-react, vitest, Playwright.

## Global Constraints

- Design : `docs/superpowers/specs/2026-11-11-corriger-sur-le-bulletin-design.md`.
- **Aucun calcul ne change** : pas de modification du moteur, de `requeteDeCorrection`, ni des routes serveur.
- Écart volontaire au design, § 4 : l'origine d'une ligne (fiche, planning, prime, régularisation) se déduit de son `code` côté écran ; pas d'ajout à la route `lignes-corrigeables`. Le design est mis à jour à la tâche 1.
- Le motif s'imprime sur le bulletin du salarié (`aideDeLaCorrection`) : aucune puce ne parle de Quadra. Puces : « Correction d’une erreur de calcul », « Correction d’une erreur de saisie », « Rappel d’un mois précédent », « Ligne non due ce mois-ci », puis « Autre… ».
- Aucun mot de moteur à l'écran : pas de « variable », « base » seule, « mode ». Écrire « le bon montant », « le bon nombre », « le bon taux ».
- Apostrophes typographiques (’) dans les textes visibles, comme le reste de l'écran.
- Dépôt public : aucun nom de salarié réel dans le code, les tests ou les commits.
- Travailler dans le worktree `/Users/alex/dev/EYWAI/.claude/worktrees/corriger-bulletin`, branche `feat/corriger-sur-le-bulletin` (contient `feat/elsa-10-11`, version en ligne). Ne jamais changer de branche dans `~/dev/EYWAI`.
- Commandes depuis `frontend/` : `npx vitest run <fichier>`, `npm run typecheck`, `npm run lint`. Fin de chaque commit : `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Fichiers

| Fichier | Rôle |
|---|---|
| `frontend/src/features/payroll/utils/bulletinACorriger.ts` (créé) | Logique pure : origine d'une ligne, champ proposé, retrait, remise, correction en attente, nombre de changements, étape en cours, motifs |
| `frontend/src/features/payroll/utils/bulletinACorriger.test.ts` (créé) | Tests unitaires de la logique |
| `frontend/src/components/payslip-edit/bulletin-a-corriger/MotifEnPuces.tsx` (créé) | Puces de motif et « Autre… » |
| `.../bulletin-a-corriger/LigneDuBulletin.tsx` (créé) | Une ligne calculée : normale, en édition, corrigée, retirée, non corrigeable |
| `.../bulletin-a-corriger/LigneDePrime.tsx` (créé) | Une prime ou saisie du mois : montant, retrait, remise |
| `.../bulletin-a-corriger/LignesAjoutees.tsx` (créé) | Ce qui est ajouté et pas encore enregistré, en vert |
| `.../bulletin-a-corriger/HeuresDuMois.tsx` (créé, code déplacé) | Heures sup ou complémentaires du mois (extrait de `CorrectionsBulletinPanel.tsx`) |
| `.../bulletin-a-corriger/SurLeNetFormulaire.tsx` (créé) | Remboursement ou retenue sur le net |
| `.../bulletin-a-corriger/AjouterUneLigne.tsx` (créé) | Bouton et 4 tuiles |
| `.../bulletin-a-corriger/BandeauEtapes.tsx` (créé) | Les 3 étapes |
| `.../bulletin-a-corriger/BarreDeCorrection.tsx` (créé) | Barre fixe : changements, Appliquer ; après : net avant/après, Annuler |
| `.../bulletin-a-corriger/BulletinACorriger.tsx` (créé) | L'onglet : lit les lignes, place les blocs |
| `frontend/src/pages/rh/PayslipEdit.tsx` (modifié) | Monte `BulletinACorriger` et `BarreDeCorrection`, garde net avant/après, « Annuler » |
| `frontend/src/components/payslip-edit/CorrectionsBulletinPanel.tsx`, `CorrigerUneLigneCard.tsx` (supprimés, tâche 8) | Ancien onglet |
| `frontend/e2e/connecte/15-corriger-sur-le-bulletin.spec.ts` (créé) | Parcours de bout en bout sur bulletin fictif |
| `frontend/e2e/connecte/06-edition-bulletin.spec.ts` (modifié) | Adapté au nouvel onglet |

---

### Task 1: Logique pure de l'onglet

**Files:**
- Create: `frontend/src/features/payroll/utils/bulletinACorriger.ts`
- Test: `frontend/src/features/payroll/utils/bulletinACorriger.test.ts`
- Modify: `docs/superpowers/specs/2026-11-11-corriger-sur-le-bulletin-design.md` (§ 3.2 puces, § 4 origine côté écran)

**Interfaces:**
- Consumes: `LigneCorrigeable`, `CorrectionLigneAjoutee` (`@/api/payslips`) ; `champsDeLaLigne`, `correctionDeLigne`, `ChampDeLigne`, `ChampCorrigeable`, `EtatCorrections`, `PrimeDuBulletin` (`./correctionsBulletin`).
- Produces (exports exacts) :
  - `MOTIFS_PROPOSES: readonly string[]`
  - `type OrigineDeLigne = 'fiche' | 'planning' | 'prime' | 'regularisation_heures' | 'regularisation_cotisation' | 'calcul' | 'cotisation' | 'impot'`
  - `familleDuCode(code: string | null | undefined): string`
  - `origineDeLaLigne(ligne: Pick<LigneCorrigeable, 'code' | 'bloc'>): OrigineDeLigne`
  - `saisieDuCode(code: string | null | undefined): string | null`
  - `champPropose(ligne: LigneCorrigeable): ChampDeLigne | null`
  - `autresChamps(ligne: LigneCorrigeable): ChampDeLigne[]`
  - `libelleDuChamp(ligne: LigneCorrigeable, cle: ChampCorrigeable): string`
  - `uniteDuChamp(ligne: LigneCorrigeable, cle: ChampCorrigeable): string`
  - `type Retrait = { type: 'prime' | 'regularisation_heures' | 'regularisation_cotisation'; saisieId: string } | { type: 'montant_zero' }`
  - `retraitDeLaLigne(ligne: LigneCorrigeable): Retrait | null`
  - `estRetiree(etat: EtatCorrections, ligne: LigneCorrigeable): boolean`
  - `retirer(etat: EtatCorrections, ligne: LigneCorrigeable, motif: string): EtatCorrections`
  - `remettre(etat: EtatCorrections, ligne: LigneCorrigeable): EtatCorrections`
  - `correctionEnAttente(etat: EtatCorrections, code: string | null | undefined): CorrectionLigneAjoutee | undefined`
  - `corrigerLaLigne(etat: EtatCorrections, ligne: LigneCorrigeable, cle: ChampCorrigeable, valeur: number, motif: string): EtatCorrections`
  - `annulerLaCorrection(etat: EtatCorrections, code: string | null | undefined): EtatCorrections`
  - `primeDeLaLigne(etat: EtatCorrections, ligne: LigneCorrigeable): PrimeDuBulletin | undefined`
  - `estSurLeNet(prime: PrimeDuBulletin): boolean`
  - `nombreDeChangements(initial: EtatCorrections, courant: EtatCorrections): number`
  - `etapeEnCours(enEdition: boolean, changements: number): 1 | 2 | 3`

- [ ] **Step 1: Écrire les tests qui échouent**

```ts
// frontend/src/features/payroll/utils/bulletinACorriger.test.ts
import { describe, expect, it } from 'vitest';
import type { LigneCorrigeable } from '@/api/payslips';
import { etatInitial, type EtatCorrections } from './correctionsBulletin';
import {
  annulerLaCorrection,
  autresChamps,
  champPropose,
  correctionEnAttente,
  corrigerLaLigne,
  estRetiree,
  estSurLeNet,
  etapeEnCours,
  familleDuCode,
  libelleDuChamp,
  MOTIFS_PROPOSES,
  nombreDeChangements,
  origineDeLaLigne,
  primeDeLaLigne,
  remettre,
  retirer,
  retraitDeLaLigne,
  saisieDuCode,
  uniteDuChamp,
} from './bulletinACorriger';

const bulletin = {
  calcul_du_brut: [
    { libelle: 'Salaire de base', quantite: 151.67, taux: 14, gain: 2123.38 },
    { libelle: 'Prime de chantier', gain: 100, saisie_id: 's-1' },
  ],
  primes_non_soumises: [{ libelle: 'Panier', montant: 7.5, saisie_id: 's-2' }],
  net_a_payer: 1800,
};

function etat(): EtatCorrections {
  return etatInitial(bulletin, null);
}

const salaire: LigneCorrigeable = {
  code: 'brut:salaire_base', bloc: 'brut', libelle: 'Salaire de base', mode: 'base_ou_taux',
  base: 151.67, taux: 14, montant: 2123.38,
};
const maintien: LigneCorrigeable = {
  code: 'brut:maintien_employeur', bloc: 'brut', libelle: 'Maintien de salaire employeur', mode: 'montant', montant: 312.44,
};
const prime: LigneCorrigeable = {
  code: 'brut:saisie:s-1', bloc: 'brut', libelle: 'Prime de chantier', mode: null,
  raison: 'Une prime saisie se corrige dans « Primes du mois ».', montant: 100,
};
const absence: LigneCorrigeable = {
  code: 'brut:absence_non_remuneree:14-10-26', bloc: 'brut', libelle: 'Absence non rémunérée du 14/10/26', mode: 'montant', retenue: true, montant: 96.92,
};
const regulHeures: LigneCorrigeable = {
  code: 'brut:regularisation_heures:r-9', bloc: 'brut', libelle: 'Rappel d’heures de 09/2026', mode: null, montant: 55.38,
};
const regulCoti: LigneCorrigeable = {
  code: 'cotisation:regularisation:c-4', bloc: 'cotisations', libelle: 'Régularisation vieillesse', mode: null,
};
const vieillesse: LigneCorrigeable = {
  code: 'cotisation:vieillesse_plafonnee', bloc: 'cotisations', libelle: 'Vieillesse plafonnée', mode: 'base_ou_taux',
  base: 2123.38, taux_salarial: 0.069, taux_patronal: 0.0855, montant_salarial: 146.51, montant_patronal: 181.55,
};
const impot: LigneCorrigeable = { code: 'impot', bloc: 'impot', libelle: 'Impôt', mode: 'taux', base: 1700, taux: 2.5, montant: 42.5 };

describe('origine d’une ligne', () => {
  it('lit la famille du code', () => {
    expect(familleDuCode('brut:heures_sup:25#2')).toBe('heures_sup');
    expect(familleDuCode(null)).toBe('');
  });
  it('classe chaque ligne', () => {
    expect(origineDeLaLigne(salaire)).toBe('fiche');
    expect(origineDeLaLigne(absence)).toBe('planning');
    expect(origineDeLaLigne(prime)).toBe('prime');
    expect(origineDeLaLigne(maintien)).toBe('calcul');
    expect(origineDeLaLigne(regulHeures)).toBe('regularisation_heures');
    expect(origineDeLaLigne(regulCoti)).toBe('regularisation_cotisation');
    expect(origineDeLaLigne(vieillesse)).toBe('cotisation');
    expect(origineDeLaLigne(impot)).toBe('impot');
  });
  it('lit l’identifiant de saisie du code', () => {
    expect(saisieDuCode('brut:saisie:s-1')).toBe('s-1');
    expect(saisieDuCode('brut:regularisation_heures:r-9#2')).toBe('r-9');
    expect(saisieDuCode('cotisation:regularisation:c-4')).toBe('c-4');
    expect(saisieDuCode('brut:salaire_base')).toBeNull();
  });
});

describe('champ proposé', () => {
  it('propose la base d’une ligne à base et taux, puis le taux', () => {
    expect(champPropose(salaire)?.cle).toBe('base');
    expect(autresChamps(salaire).map((c) => c.cle)).toEqual(['taux']);
  });
  it('propose le montant d’une ligne au montant', () => {
    expect(champPropose(maintien)?.cle).toBe('montant');
    expect(autresChamps(maintien)).toEqual([]);
  });
  it('ne propose rien pour une ligne qui ne se corrige pas ici', () => {
    expect(champPropose(prime)).toBeNull();
  });
  it('parle comme la RH, avec l’unité', () => {
    expect(libelleDuChamp(salaire, 'base')).toBe('Le bon nombre');
    expect(libelleDuChamp(maintien, 'montant')).toBe('Le bon montant');
    expect(libelleDuChamp(vieillesse, 'taux_salarial')).toBe('Le bon taux salarial');
    expect(uniteDuChamp(maintien, 'montant')).toBe('€');
    expect(uniteDuChamp(salaire, 'base')).toBe('');
    expect(uniteDuChamp(salaire, 'taux')).toBe('€');
    expect(uniteDuChamp(impot, 'taux')).toBe('%');
    expect(uniteDuChamp(vieillesse, 'base')).toBe('€');
    expect(uniteDuChamp(vieillesse, 'taux_patronal')).toBe('%');
  });
});

describe('retirer et remettre', () => {
  it('dit comment chaque ligne se retire', () => {
    expect(retraitDeLaLigne(prime)).toEqual({ type: 'prime', saisieId: 's-1' });
    expect(retraitDeLaLigne(regulHeures)).toEqual({ type: 'regularisation_heures', saisieId: 'r-9' });
    expect(retraitDeLaLigne(regulCoti)).toEqual({ type: 'regularisation_cotisation', saisieId: 'c-4' });
    expect(retraitDeLaLigne(maintien)).toEqual({ type: 'montant_zero' });
    expect(retraitDeLaLigne(salaire)).toBeNull();
    expect(retraitDeLaLigne(absence)).toBeNull();
    expect(retraitDeLaLigne(vieillesse)).toBeNull();
  });
  it('retire une prime puis la remet', () => {
    const apres = retirer(etat(), prime, '');
    expect(apres.primesRetirees).toEqual(['s-1']);
    expect(estRetiree(apres, prime)).toBe(true);
    expect(remettre(apres, prime).primesRetirees).toEqual([]);
  });
  it('retire une ligne calculée par une correction à zéro, motif compris', () => {
    const apres = retirer(etat(), maintien, MOTIFS_PROPOSES[3]);
    expect(apres.correctionsAjoutees).toEqual([
      { ligne: 'brut:maintien_employeur', libelle: 'Maintien de salaire employeur', motif: 'Ligne non due ce mois-ci', montant: 0 },
    ]);
    expect(estRetiree(apres, maintien)).toBe(true);
    expect(remettre(apres, maintien).correctionsAjoutees).toEqual([]);
  });
  it('retire et remet les régularisations', () => {
    const a = retirer(etat(), regulHeures, '');
    expect(a.heuresRegulariseesRetirees).toEqual(['r-9']);
    const b = retirer(a, regulCoti, '');
    expect(b.regularisationsRetirees).toEqual(['c-4']);
    expect(remettre(remettre(b, regulHeures), regulCoti)).toMatchObject({
      heuresRegulariseesRetirees: [],
      regularisationsRetirees: [],
    });
  });
  it('ne fait rien sur une ligne qui ne se retire pas', () => {
    const depart = etat();
    expect(retirer(depart, salaire, 'x')).toBe(depart);
  });
});

describe('corriger une ligne', () => {
  it('remplace la correction en attente de la même ligne', () => {
    const a = corrigerLaLigne(etat(), salaire, 'base', 140, 'Correction d’une erreur de saisie');
    const b = corrigerLaLigne(a, salaire, 'base', 145, 'Correction d’une erreur de saisie');
    expect(b.correctionsAjoutees).toHaveLength(1);
    expect(correctionEnAttente(b, 'brut:salaire_base')?.base).toBe(145);
    expect(annulerLaCorrection(b, 'brut:salaire_base').correctionsAjoutees).toEqual([]);
  });
});

describe('primes', () => {
  it('trouve la prime d’une ligne saisie', () => {
    expect(primeDeLaLigne(etat(), prime)?.libelle).toBe('Prime de chantier');
    expect(primeDeLaLigne(etat(), salaire)).toBeUndefined();
  });
  it('range les primes non soumises et les saisies sur le net dans « Sur le net »', () => {
    const [chantier, panier] = etat().primes;
    expect(estSurLeNet(chantier)).toBe(false);
    expect(estSurLeNet(panier)).toBe(true);
    expect(estSurLeNet({ ...chantier, surLeNet: 'retenue' })).toBe(true);
  });
});

describe('changements et étapes', () => {
  it('compte chaque changement', () => {
    const depart = etat();
    expect(nombreDeChangements(depart, depart)).toBe(0);
    let courant = retirer(depart, prime, '');
    courant = corrigerLaLigne(courant, salaire, 'base', 140, 'Correction d’une erreur de saisie');
    courant = { ...courant, hs25: courant.hs25 + 2 };
    courant = { ...courant, primes: courant.primes.map((p) => (p.saisieId === 's-2' ? { ...p, montant: 9 } : p)) };
    expect(nombreDeChangements(depart, courant)).toBe(4);
  });
  it('dit l’étape en cours', () => {
    expect(etapeEnCours(false, 0)).toBe(1);
    expect(etapeEnCours(true, 0)).toBe(2);
    expect(etapeEnCours(true, 2)).toBe(2);
    expect(etapeEnCours(false, 2)).toBe(3);
  });
});
```

- [ ] **Step 2: Lancer les tests, ils échouent**

Run: `cd frontend && npx vitest run src/features/payroll/utils/bulletinACorriger.test.ts`
Expected: FAIL, « Failed to resolve import "./bulletinACorriger" ».

- [ ] **Step 3: Écrire la logique**

```ts
// frontend/src/features/payroll/utils/bulletinACorriger.ts
/**
 * L'onglet « Corriger » est le bulletin lui-même (design du 11/11/2026,
 * retours de Lyon). Ici, la logique pure : d'où vient une ligne, ce qu'on y
 * corrige, comment elle se retire. Rien n'est calculé ici : toute correction
 * reste une variable du mois, recalculée en entier par Martine.
 */
import type { CorrectionLigneAjoutee, LigneCorrigeable } from '@/api/payslips';
import {
  champsDeLaLigne,
  correctionDeLigne,
  type ChampCorrigeable,
  type ChampDeLigne,
  type EtatCorrections,
  type PrimeDuBulletin,
} from './correctionsBulletin';

/** Imprimés sur le bulletin du salarié : jamais un mot sur Quadra ou sur l'outil. */
export const MOTIFS_PROPOSES: readonly string[] = [
  'Correction d’une erreur de calcul',
  'Correction d’une erreur de saisie',
  'Rappel d’un mois précédent',
  'Ligne non due ce mois-ci',
];

export type OrigineDeLigne =
  | 'fiche'
  | 'planning'
  | 'prime'
  | 'regularisation_heures'
  | 'regularisation_cotisation'
  | 'calcul'
  | 'cotisation'
  | 'impot';

const FAMILLES_DE_LA_FICHE = new Set(['salaire_base', 'avantages_en_nature']);
const FAMILLES_DU_PLANNING = new Set([
  'heures_sup',
  'hs_structurelles',
  'heures_complementaires',
  'heures_nuit',
  'pause_remuneree',
  'absence_entree_sortie',
  'absence_injustifiee',
  'absence_non_remuneree',
  'absence_evenement_familial',
  'absence_ferie_non_paye',
  'absence_maladie',
  'absence_conges_payes',
  'indemnite_conges_payes',
  'reduction_hs_absence',
  'reduction_hs_evenement_familial',
]);

/** « brut:heures_sup:25#2 » → « heures_sup ». */
export function familleDuCode(code: string | null | undefined): string {
  if (!code) return '';
  return code.split('#')[0].split(':')[1] ?? '';
}

export function origineDeLaLigne(ligne: Pick<LigneCorrigeable, 'code' | 'bloc'>): OrigineDeLigne {
  if (ligne.bloc === 'impot') return 'impot';
  const code = ligne.code ?? '';
  if (ligne.bloc === 'cotisations') {
    return code.startsWith('cotisation:regularisation:') ? 'regularisation_cotisation' : 'cotisation';
  }
  const famille = familleDuCode(code);
  if (famille === 'saisie') return 'prime';
  if (famille === 'regularisation_heures') return 'regularisation_heures';
  if (FAMILLES_DE_LA_FICHE.has(famille)) return 'fiche';
  if (FAMILLES_DU_PLANNING.has(famille)) return 'planning';
  return 'calcul';
}

const PREFIXES_DE_SAISIE = ['brut:saisie:', 'brut:regularisation_heures:', 'cotisation:regularisation:'];

/** L'identifiant de la saisie porté par le code d'une prime ou d'une régularisation. */
export function saisieDuCode(code: string | null | undefined): string | null {
  const sansNumero = (code ?? '').split('#')[0];
  const prefixe = PREFIXES_DE_SAISIE.find((p) => sansNumero.startsWith(p));
  const id = prefixe ? sansNumero.slice(prefixe.length) : '';
  return id || null;
}

/** Le champ que l'écran propose d'abord : celui que la règle 3 permet, la base avant le taux. */
export function champPropose(ligne: LigneCorrigeable): ChampDeLigne | null {
  return champsDeLaLigne(ligne)[0] ?? null;
}

export function autresChamps(ligne: LigneCorrigeable): ChampDeLigne[] {
  return champsDeLaLigne(ligne).slice(1);
}

export function libelleDuChamp(ligne: LigneCorrigeable, cle: ChampCorrigeable): string {
  switch (cle) {
    case 'base':
      return ligne.bloc === 'cotisations' ? 'La bonne base' : 'Le bon nombre';
    case 'taux':
      return 'Le bon taux';
    case 'taux_salarial':
      return 'Le bon taux salarial';
    case 'taux_patronal':
      return 'Le bon taux patronal';
    case 'montant_salarial':
      return 'La bonne part salariale';
    case 'montant_patronal':
      return 'La bonne part patronale';
    default:
      return 'Le bon montant';
  }
}

export function uniteDuChamp(ligne: LigneCorrigeable, cle: ChampCorrigeable): string {
  if (cle === 'montant' || cle === 'montant_salarial' || cle === 'montant_patronal') return '€';
  if (cle === 'taux_salarial' || cle === 'taux_patronal') return '%';
  if (cle === 'taux') return ligne.bloc === 'impot' ? '%' : '€';
  return ligne.bloc === 'cotisations' ? '€' : '';
}

export type Retrait =
  | { type: 'prime' | 'regularisation_heures' | 'regularisation_cotisation'; saisieId: string }
  | { type: 'montant_zero' };

/** Comment la ligne se retire, ou null : elle se corrige au crayon ou à sa source. */
export function retraitDeLaLigne(ligne: LigneCorrigeable): Retrait | null {
  const origine = origineDeLaLigne(ligne);
  const saisieId = saisieDuCode(ligne.code);
  if (saisieId && (origine === 'prime' || origine === 'regularisation_heures' || origine === 'regularisation_cotisation')) {
    return { type: origine, saisieId };
  }
  if (origine === 'calcul' && ligne.bloc === 'brut' && ligne.mode === 'montant' && !ligne.retenue) {
    return { type: 'montant_zero' };
  }
  return null;
}

export function correctionEnAttente(
  etat: EtatCorrections,
  code: string | null | undefined
): CorrectionLigneAjoutee | undefined {
  return code ? etat.correctionsAjoutees.find((c) => c.ligne === code) : undefined;
}

export function annulerLaCorrection(etat: EtatCorrections, code: string | null | undefined): EtatCorrections {
  if (!code || !correctionEnAttente(etat, code)) return etat;
  return { ...etat, correctionsAjoutees: etat.correctionsAjoutees.filter((c) => c.ligne !== code) };
}

export function corrigerLaLigne(
  etat: EtatCorrections,
  ligne: LigneCorrigeable,
  cle: ChampCorrigeable,
  valeur: number,
  motif: string
): EtatCorrections {
  const sans = annulerLaCorrection(etat, ligne.code);
  return { ...sans, correctionsAjoutees: [...sans.correctionsAjoutees, correctionDeLigne(ligne, cle, valeur, motif)] };
}

const ajouter = (liste: string[], id: string) => (liste.includes(id) ? liste : [...liste, id]);
const enlever = (liste: string[], id: string) => liste.filter((x) => x !== id);

export function estRetiree(etat: EtatCorrections, ligne: LigneCorrigeable): boolean {
  const retrait = retraitDeLaLigne(ligne);
  if (!retrait) return false;
  switch (retrait.type) {
    case 'prime':
      return etat.primesRetirees.includes(retrait.saisieId);
    case 'regularisation_heures':
      return etat.heuresRegulariseesRetirees.includes(retrait.saisieId);
    case 'regularisation_cotisation':
      return etat.regularisationsRetirees.includes(retrait.saisieId);
    default:
      return correctionEnAttente(etat, ligne.code)?.montant === 0;
  }
}

export function retirer(etat: EtatCorrections, ligne: LigneCorrigeable, motif: string): EtatCorrections {
  const retrait = retraitDeLaLigne(ligne);
  if (!retrait) return etat;
  switch (retrait.type) {
    case 'prime':
      return { ...etat, primesRetirees: ajouter(etat.primesRetirees, retrait.saisieId) };
    case 'regularisation_heures':
      return { ...etat, heuresRegulariseesRetirees: ajouter(etat.heuresRegulariseesRetirees, retrait.saisieId) };
    case 'regularisation_cotisation':
      return { ...etat, regularisationsRetirees: ajouter(etat.regularisationsRetirees, retrait.saisieId) };
    default:
      return corrigerLaLigne(etat, ligne, 'montant', 0, motif);
  }
}

export function remettre(etat: EtatCorrections, ligne: LigneCorrigeable): EtatCorrections {
  const retrait = retraitDeLaLigne(ligne);
  if (!retrait) return etat;
  switch (retrait.type) {
    case 'prime':
      return { ...etat, primesRetirees: enlever(etat.primesRetirees, retrait.saisieId) };
    case 'regularisation_heures':
      return { ...etat, heuresRegulariseesRetirees: enlever(etat.heuresRegulariseesRetirees, retrait.saisieId) };
    case 'regularisation_cotisation':
      return { ...etat, regularisationsRetirees: enlever(etat.regularisationsRetirees, retrait.saisieId) };
    default:
      return annulerLaCorrection(etat, ligne.code);
  }
}

export function primeDeLaLigne(etat: EtatCorrections, ligne: LigneCorrigeable): PrimeDuBulletin | undefined {
  if (origineDeLaLigne(ligne) !== 'prime') return undefined;
  const saisieId = saisieDuCode(ligne.code);
  return etat.primes.find((p) => p.saisieId === saisieId);
}

/** Non soumise, ou retenue ou versement sur le net : rangée dans le bloc « Sur le net ». */
export function estSurLeNet(prime: PrimeDuBulletin): boolean {
  return !prime.soumise || Boolean(prime.surLeNet);
}

export function nombreDeChangements(initial: EtatCorrections, courant: EtatCorrections): number {
  const montants = new Map(initial.primes.map((p) => [p.saisieId, p.montant]));
  const primesChangees = courant.primes.filter((p) => montants.has(p.saisieId) && montants.get(p.saisieId) !== p.montant).length;
  const heures =
    courant.hs25 !== initial.hs25 || courant.hs50 !== initial.hs50 || courant.revenirAuPlanning !== initial.revenirAuPlanning ? 1 : 0;
  const complementaires =
    courant.hc1 !== initial.hc1 || courant.hc2 !== initial.hc2 || courant.hcAuPlanning !== initial.hcAuPlanning ? 1 : 0;
  return (
    primesChangees +
    heures +
    complementaires +
    courant.primesRetirees.length +
    courant.primesAjoutees.length +
    courant.correctionsAjoutees.length +
    courant.correctionsRetirees.length +
    courant.regularisationsAjoutees.length +
    courant.regularisationsRetirees.length +
    courant.heuresRegulariseesAjoutees.length +
    courant.heuresRegulariseesRetirees.length
  );
}

export function etapeEnCours(enEdition: boolean, changements: number): 1 | 2 | 3 {
  if (enEdition) return 2;
  return changements > 0 ? 3 : 1;
}
```

- [ ] **Step 4: Lancer les tests, ils passent**

Run: `cd frontend && npx vitest run src/features/payroll/utils/bulletinACorriger.test.ts`
Expected: PASS. Si `etatInitial(bulletin, null)` ne range pas « Panier » avec `soumise: false`, lire `primesDuBulletin` dans `correctionsBulletin.ts` (ligne 269) et ajuster la donnée du test, pas la fonction.

- [ ] **Step 5: Mettre le design à jour**

Dans `docs/superpowers/specs/2026-11-11-corriger-sur-le-bulletin-design.md` :
- § 3.2, remplacer la liste des puces par : « Correction d’une erreur de calcul », « Correction d’une erreur de saisie », « Rappel d’un mois précédent », « Ligne non due ce mois-ci », « Autre… ». Ajouter : « Le motif est imprimé sur le bulletin du salarié : aucune puce ne parle de Quadra. »
- § 4, remplacer le paragraphe « Serveur, ajout minimal… » par : « Aucun changement serveur. L'origine d'une ligne (fiche, planning, prime, régularisation, calcul) et son retrait se déduisent de son `code` (`codes_des_lignes.py`), dans `bulletinACorriger.ts`. »

- [ ] **Step 6: Typecheck et commit**

Run: `cd frontend && npm run typecheck`
Expected: aucune erreur.

```bash
git add frontend/src/features/payroll/utils/bulletinACorriger.ts frontend/src/features/payroll/utils/bulletinACorriger.test.ts docs/superpowers/specs/2026-11-11-corriger-sur-le-bulletin-design.md
git commit -m "feat(corriger): logique de l'onglet corriger sur le bulletin

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Les lignes du bulletin (motif, ligne calculée, prime)

**Files:**
- Create: `frontend/src/components/payslip-edit/bulletin-a-corriger/MotifEnPuces.tsx`
- Create: `frontend/src/components/payslip-edit/bulletin-a-corriger/LigneDuBulletin.tsx`
- Create: `frontend/src/components/payslip-edit/bulletin-a-corriger/LigneDePrime.tsx`

**Interfaces:**
- Consumes: tout l'export de la tâche 1 ; `aideDeLaCorrection`, `apercuDuMontant`, `eurosFr`, `montantCorrigeDeLaPrime`, `resumeDeLaCorrection`, `DemandeDeCorrection` (`correctionsBulletin.ts`) ; `lireNombre` (`@/lib/nombreSaisi`) ; `pastilleSoumise` (`@/components/saisies/libellesSaisie`).
- Produces :
  - `MotifEnPuces({ valeur, onValeur, disabled, testId }: { valeur: string; onValeur: (motif: string) => void; disabled?: boolean; testId?: string })`
  - `LigneDuBulletin(props: { ligne: LigneCorrigeable; etat: EtatCorrections; onChange: (e: EtatCorrections) => void; disabled?: boolean; lienSource: { texte: string; onOuvrir: () => void } | null; demande?: DemandeDeCorrection | null; onEdition: (code: string, ouverte: boolean) => void })`
  - `LigneDePrime(props: { prime: PrimeDuBulletin; etat: EtatCorrections; onChange: (e: EtatCorrections) => void; disabled?: boolean })`
  - testids : `ligne-<code>`, `corriger-<code>`, `retirer-<code>`, `remettre-<code>`, `valeur-<code>`, `apercu-<code>`, `motif-<code>` (sur `MotifEnPuces`), `prime-<saisieId>`, `montant-prime-<saisieId>`, `retirer-prime-<saisieId>`, `remettre-prime-<saisieId>`.

- [ ] **Step 1: `MotifEnPuces.tsx`**

```tsx
import { useState } from 'react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { MOTIFS_PROPOSES } from '@/features/payroll/utils/bulletinACorriger';

interface Props {
  valeur: string;
  onValeur: (motif: string) => void;
  disabled?: boolean;
  testId?: string;
}

/** Le motif en un clic. Il est imprimé sur le bulletin : « Autre… » ouvre un champ libre. */
export default function MotifEnPuces({ valeur, onValeur, disabled, testId }: Props) {
  const [autre, setAutre] = useState(() => valeur !== '' && !MOTIFS_PROPOSES.includes(valeur));
  return (
    <div className="space-y-2" data-testid={testId}>
      <p className="text-xs text-muted-foreground">Pourquoi ? (imprimé sur le bulletin)</p>
      <div className="flex flex-wrap gap-1.5">
        {MOTIFS_PROPOSES.map((motif) => (
          <button
            key={motif}
            type="button"
            disabled={disabled}
            onClick={() => {
              setAutre(false);
              onValeur(motif);
            }}
            className={cn(
              'rounded-full border px-3 py-1 text-xs',
              !autre && valeur === motif ? 'border-primary bg-primary text-primary-foreground' : 'bg-background'
            )}
          >
            {motif}
          </button>
        ))}
        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            setAutre(true);
            onValeur('');
          }}
          className={cn(
            'rounded-full border px-3 py-1 text-xs',
            autre ? 'border-primary bg-primary text-primary-foreground' : 'bg-background'
          )}
        >
          Autre…
        </button>
      </div>
      {autre ? (
        <Input
          autoFocus
          maxLength={300}
          placeholder="Écrivez le motif"
          value={valeur}
          disabled={disabled}
          onChange={(e) => onValeur(e.target.value)}
        />
      ) : null}
    </div>
  );
}
```

Vérifier que `cn` existe dans `@/lib/utils` (`grep -n "export function cn" frontend/src/lib/utils.ts`) ; sinon l'importer d'où les autres composants l'importent (`grep -rn "import { cn }" frontend/src/components | head -1`).

- [ ] **Step 2: `LigneDuBulletin.tsx`**

```tsx
/**
 * Une ligne calculée du bulletin, corrigeable en place (design du 11/11/2026).
 * La correction s'écrit dans l'état dès que la valeur et le motif sont bons :
 * rien d'autre à valider que « Appliquer », en bas de l'écran.
 */
import { useEffect, useRef, useState } from 'react';
import { ExternalLink, PencilLine, Trash2, Undo2, X } from 'lucide-react';

import type { LigneCorrigeable } from '@/api/payslips';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  aideDeLaCorrection,
  apercuDuMontant,
  type ChampCorrigeable,
  type DemandeDeCorrection,
  type EtatCorrections,
  eurosFr,
  resumeDeLaCorrection,
} from '@/features/payroll/utils/correctionsBulletin';
import {
  annulerLaCorrection,
  autresChamps,
  champPropose,
  correctionEnAttente,
  corrigerLaLigne,
  estRetiree,
  libelleDuChamp,
  remettre,
  retirer,
  retraitDeLaLigne,
  uniteDuChamp,
} from '@/features/payroll/utils/bulletinACorriger';
import { lireNombre } from '@/lib/nombreSaisi';
import { cn } from '@/lib/utils';
import MotifEnPuces from './MotifEnPuces';

interface Props {
  ligne: LigneCorrigeable;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
  lienSource: { texte: string; onOuvrir: () => void } | null;
  demande?: DemandeDeCorrection | null;
  onEdition: (code: string, ouverte: boolean) => void;
}

function montantAffiche(ligne: LigneCorrigeable): string {
  if (ligne.bloc === 'cotisations') {
    const parts = [
      ligne.montant_salarial ? `salarié ${eurosFr(ligne.montant_salarial)}` : null,
      ligne.montant_patronal ? `employeur ${eurosFr(ligne.montant_patronal)}` : null,
    ].filter(Boolean);
    return parts.join(' · ');
  }
  if (ligne.montant == null) return '';
  return `${ligne.retenue ? '−' : ''}${eurosFr(ligne.montant)}`;
}

export default function LigneDuBulletin({ ligne, etat, onChange, disabled, lienSource, demande, onEdition }: Props) {
  const code = String(ligne.code ?? '');
  const enAttente = correctionEnAttente(etat, code);
  const retiree = estRetiree(etat, ligne);
  const retrait = retraitDeLaLigne(ligne);
  const propose = champPropose(ligne);
  const [ouverte, setOuverte] = useState(false);
  const [cle, setCle] = useState<ChampCorrigeable | ''>('');
  const [texte, setTexte] = useState('');
  const [motif, setMotif] = useState('');
  const [motifRetrait, setMotifRetrait] = useState<string | null>(null);
  const racine = useRef<HTMLDivElement>(null);
  const champ = (cle && [propose, ...autresChamps(ligne)].find((c) => c?.cle === cle)) || propose;

  const ouvrir = () => {
    setOuverte(true);
    setCle(enAttente ? (Object.keys(enAttente).find((k) => !['ligne', 'libelle', 'motif'].includes(k)) as ChampCorrigeable) : '');
    setTexte(enAttente && champ ? String(enAttente[champ.cle] ?? '').replace('.', ',') : '');
    setMotif(enAttente?.motif ?? '');
    onEdition(code, true);
  };
  const fermer = () => {
    setOuverte(false);
    onEdition(code, false);
  };

  useEffect(() => {
    if (demande?.carte === 'ligne' && demande.code === code && propose && !disabled) {
      ouvrir();
      racine.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    // Le jeton change à chaque clic venu de l'onglet « Bulletin ».
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demande?.jeton]);

  /** Chaque frappe met l'état à jour : une valeur et un motif valides font une correction en attente. */
  const ecrire = (nouveauTexte: string, nouveauMotif: string, nouvelleCle: ChampCorrigeable | '' = cle) => {
    setTexte(nouveauTexte);
    setMotif(nouveauMotif);
    const cible = (nouvelleCle && [propose, ...autresChamps(ligne)].find((c) => c?.cle === nouvelleCle)) || propose;
    const nombre = lireNombre(nouveauTexte);
    if (cible && nombre !== null && aideDeLaCorrection(nouveauTexte, nouveauMotif) === null) {
      onChange(corrigerLaLigne(etat, ligne, cible.cle, nombre, nouveauMotif));
    } else {
      onChange(annulerLaCorrection(etat, code));
    }
  };

  const nombre = lireNombre(texte);
  const apercu = champ && nombre !== null ? apercuDuMontant(ligne, champ.cle, nombre) : null;
  const aide = ouverte ? aideDeLaCorrection(texte, motif) : null;
  const dejaCorrigee = Boolean(ligne.correction?.saisie_id);
  const correctionRetiree = dejaCorrigee && etat.correctionsRetirees.includes(String(ligne.correction?.saisie_id));

  return (
    <div
      ref={racine}
      data-testid={`ligne-${code}`}
      className={cn(
        'flex flex-col gap-2 border-b px-3 py-2 text-sm sm:flex-row sm:items-start sm:justify-between',
        ouverte && 'bg-blue-50 outline outline-2 -outline-offset-2 outline-blue-500 dark:bg-blue-950/30',
        retiree && 'bg-red-50 dark:bg-red-950/20',
        !retiree && enAttente && !ouverte && 'bg-amber-50 dark:bg-amber-950/20'
      )}
    >
      <div className="min-w-0 flex-1 space-y-1">
        <div className={cn('font-medium', retiree && 'text-muted-foreground line-through')}>
          {ligne.libelle}
          {retiree ? <span className="ml-2 rounded bg-red-100 px-1.5 text-xs font-semibold text-red-700">Retirée</span> : null}
          {!retiree && enAttente ? (
            <span className="ml-2 rounded bg-amber-100 px-1.5 text-xs font-semibold text-amber-800">À appliquer</span>
          ) : null}
        </div>
        {lienSource ? (
          <button type="button" className="text-xs text-muted-foreground underline-offset-2 hover:underline" onClick={lienSource.onOuvrir}>
            {lienSource.texte} <ExternalLink className="inline h-3 w-3" />
          </button>
        ) : null}
        {!ligne.mode && !retrait && ligne.raison ? <p className="text-xs text-muted-foreground">{ligne.raison}</p> : null}
        {dejaCorrigee ? (
          <p className={cn('text-xs text-muted-foreground', correctionRetiree && 'line-through')}>
            Corrigée : {resumeDeLaCorrection(ligne)} — {ligne.correction?.motif}
          </p>
        ) : null}
        {ligne.alerte ? <p className="text-xs text-destructive">{ligne.alerte}</p> : null}
        {retiree && enAttente ? <p className="text-xs text-muted-foreground">Motif : {enAttente.motif}</p> : null}

        {ouverte && champ ? (
          <div className="mt-2 space-y-3 rounded-md border bg-background p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">
                Martine : {champ.valeur != null ? String(champ.valeur).replace('.', ',') : '—'} {uniteDuChamp(ligne, champ.cle)}
              </span>
              <span>· {libelleDuChamp(ligne, champ.cle)} :</span>
              <Input
                autoFocus
                data-testid={`valeur-${code}`}
                inputMode="decimal"
                className="w-28 border-2 border-blue-500 text-right font-semibold"
                value={texte}
                aria-invalid={aide?.champ === 'valeur'}
                onChange={(e) => ecrire(e.target.value, motif)}
              />
              <span className="text-sm">{uniteDuChamp(ligne, champ.cle)}</span>
            </div>
            {autresChamps(ligne).length > 0 ? (
              <div className="flex flex-wrap gap-2 text-xs">
                {[propose, ...autresChamps(ligne)]
                  .filter((c) => c && c.cle !== champ.cle)
                  .map((c) => (
                    <button
                      key={c!.cle}
                      type="button"
                      className="text-blue-700 underline-offset-2 hover:underline"
                      onClick={() => {
                        setCle(c!.cle);
                        ecrire('', motif, c!.cle);
                      }}
                    >
                      Corriger plutôt : {libelleDuChamp(ligne, c!.cle).toLowerCase()}
                    </button>
                  ))}
              </div>
            ) : null}
            {aide?.champ === 'valeur' ? <p className="text-xs text-destructive">{aide.message}</p> : null}
            <MotifEnPuces testId={`motif-${code}`} valeur={motif} onValeur={(m) => ecrire(texte, m)} />
            {aide?.champ === 'motif' ? <p className="text-xs text-destructive">{aide.message}</p> : null}
          </div>
        ) : null}

        {motifRetrait !== null ? (
          <div className="mt-2 space-y-2 rounded-md border bg-background p-3">
            <MotifEnPuces
              testId={`motif-retrait-${code}`}
              valeur={motifRetrait}
              onValeur={(m) => {
                if (m.trim().length >= 3) {
                  onChange(retirer(etat, ligne, m));
                  setMotifRetrait(null);
                  onEdition(code, false);
                } else setMotifRetrait(m);
              }}
            />
          </div>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:pl-3">
        <span className={cn('tabular-nums', retiree && 'text-muted-foreground line-through')}>
          {montantAffiche(ligne)}
          {apercu !== null ? (
            <span data-testid={`apercu-${code}`} className="ml-1 font-semibold">
              → {eurosFr(apercu)}
            </span>
          ) : null}
        </span>
        {disabled ? null : retiree ? (
          <Button variant="outline" size="sm" data-testid={`remettre-${code}`} onClick={() => onChange(remettre(etat, ligne))}>
            <Undo2 className="mr-1 h-4 w-4" /> Remettre
          </Button>
        ) : ouverte ? (
          <Button
            variant="ghost"
            size="sm"
            aria-label="Annuler cette correction"
            onClick={() => {
              onChange(annulerLaCorrection(etat, code));
              fermer();
            }}
          >
            <X className="h-4 w-4" />
          </Button>
        ) : (
          <>
            {propose ? (
              <Button variant="outline" size="sm" data-testid={`corriger-${code}`} aria-label={`Corriger ${ligne.libelle}`} onClick={ouvrir}>
                <PencilLine className="h-4 w-4" />
              </Button>
            ) : null}
            {retrait ? (
              <Button
                variant="outline"
                size="sm"
                className="text-red-700"
                data-testid={`retirer-${code}`}
                aria-label={`Retirer ${ligne.libelle}`}
                onClick={() => {
                  if (retrait.type === 'montant_zero') {
                    setMotifRetrait('');
                    onEdition(code, true);
                  } else onChange(retirer(etat, ligne, ''));
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            ) : null}
            {dejaCorrigee ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  const id = String(ligne.correction?.saisie_id);
                  onChange({
                    ...etat,
                    correctionsRetirees: correctionRetiree
                      ? etat.correctionsRetirees.filter((x) => x !== id)
                      : [...etat.correctionsRetirees, id],
                  });
                }}
              >
                {correctionRetiree ? 'Garder la correction' : 'Remettre la valeur de Martine'}
              </Button>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: `LigneDePrime.tsx`**

```tsx
/** Une prime ou une saisie du mois : son montant se change, elle se retire et se remet. */
import { useState } from 'react';
import { PencilLine, Trash2, Undo2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { pastilleSoumise } from '@/components/saisies/libellesSaisie';
import {
  type EtatCorrections,
  eurosFr,
  montantCorrigeDeLaPrime,
  type PrimeDuBulletin,
} from '@/features/payroll/utils/correctionsBulletin';
import { lireNombre } from '@/lib/nombreSaisi';
import { cn } from '@/lib/utils';

interface Props {
  prime: PrimeDuBulletin;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
}

function pastille(prime: PrimeDuBulletin): string {
  if (prime.surLeNet === 'retenue') return 'Retenue sur le net';
  if (prime.surLeNet === 'versement') return 'Versement sur le net';
  return pastilleSoumise(prime.soumise);
}

export default function LigneDePrime({ prime, etat, onChange, disabled }: Props) {
  const id = prime.saisieId;
  const retiree = etat.primesRetirees.includes(id);
  const initiale = prime.surLeNet === 'retenue' ? Math.abs(prime.montant) : prime.montant;
  const [ouverte, setOuverte] = useState(false);
  const [texte, setTexte] = useState(String(initiale).replace('.', ','));

  return (
    <div
      data-testid={`prime-${id}`}
      className={cn(
        'flex flex-col gap-2 border-b px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between',
        retiree && 'bg-red-50 dark:bg-red-950/20'
      )}
    >
      <div className="min-w-0 flex-1">
        <span className={cn('font-medium', retiree && 'text-muted-foreground line-through')}>{prime.libelle}</span>
        <span className="ml-2 text-xs text-muted-foreground">{pastille(prime)}</span>
        {retiree ? <span className="ml-2 rounded bg-red-100 px-1.5 text-xs font-semibold text-red-700">Retirée</span> : null}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {ouverte && !retiree ? (
          <>
            <Input
              autoFocus
              data-testid={`montant-prime-${id}`}
              inputMode="decimal"
              className="w-28 border-2 border-blue-500 text-right font-semibold"
              value={texte}
              onChange={(e) => {
                setTexte(e.target.value);
                const lu = lireNombre(e.target.value);
                if (lu === null) return;
                const montant = montantCorrigeDeLaPrime(prime, lu);
                onChange({ ...etat, primes: etat.primes.map((p) => (p.saisieId === id ? { ...p, montant } : p)) });
              }}
            />
            <span>€</span>
          </>
        ) : (
          <span className={cn('tabular-nums', retiree && 'text-muted-foreground line-through')}>{eurosFr(prime.montant)}</span>
        )}
        {disabled ? null : retiree ? (
          <Button
            variant="outline"
            size="sm"
            data-testid={`remettre-prime-${id}`}
            onClick={() => onChange({ ...etat, primesRetirees: etat.primesRetirees.filter((x) => x !== id) })}
          >
            <Undo2 className="mr-1 h-4 w-4" /> Remettre
          </Button>
        ) : (
          <>
            {!ouverte ? (
              <Button variant="outline" size="sm" aria-label={`Corriger ${prime.libelle}`} onClick={() => setOuverte(true)}>
                <PencilLine className="h-4 w-4" />
              </Button>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              className="text-red-700"
              data-testid={`retirer-prime-${id}`}
              aria-label={`Retirer ${prime.libelle}`}
              onClick={() => onChange({ ...etat, primesRetirees: [...etat.primesRetirees, id] })}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
```

`montantCorrigeDeLaPrime(prime, saisi)` remet le signe d'une retenue (lire sa définition ligne 286 de `correctionsBulletin.ts` avant d'utiliser) : le montant affiché d'une retenue reste positif.

- [ ] **Step 4: Typecheck, lint, commit**

Run: `cd frontend && npm run typecheck && npx eslint src/components/payslip-edit/bulletin-a-corriger`
Expected: aucune erreur.

```bash
git add frontend/src/components/payslip-edit/bulletin-a-corriger
git commit -m "feat(corriger): lignes du bulletin corrigeables en place

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Ajouter une ligne (4 tuiles) et lignes ajoutées

**Files:**
- Create: `frontend/src/components/payslip-edit/bulletin-a-corriger/HeuresDuMois.tsx`
- Create: `frontend/src/components/payslip-edit/bulletin-a-corriger/SurLeNetFormulaire.tsx`
- Create: `frontend/src/components/payslip-edit/bulletin-a-corriger/AjouterUneLigne.tsx`
- Create: `frontend/src/components/payslip-edit/bulletin-a-corriger/LignesAjoutees.tsx`

**Interfaces:**
- Consumes : `RegularisationsHeuresCard`, `RegularisationsCotisationCard`, `AjouterPrimeBouton` (inchangés) ; `PrimeAjoutee` (`@/api/payslips`) ; tâche 1.
- Produces :
  - `HeuresDuMois(props: { payslipData: unknown; etat: EtatCorrections; onChange: (e: EtatCorrections) => void; disabled?: boolean; tempsPartiel?: boolean })` (garde les testids `heures-sup-25`, `heures-sup-50`, `revenir-au-planning`, `heures-declarees`, `retour-planning`, `heures-complementaires-1`, `heures-complementaires-2`, `heures-complementaires-du-mois`, `heures-complementaires-declarees`)
  - `SurLeNetFormulaire(props: { onAjout: (prime: PrimeAjoutee) => void })`
  - `type Tuile = 'heures' | 'prime' | 'net' | 'cotisation'`
  - `AjouterUneLigne(props: { payslipData: unknown; etat: EtatCorrections; onChange: (e: EtatCorrections) => void; disabled?: boolean; forfaitJours?: boolean; tempsPartiel?: boolean; employeeId: string; year: number; month: number; demande?: DemandeDeCorrection | null })` ; testids `ajouter-une-ligne`, `tuile-heures`, `tuile-prime`, `tuile-net`, `tuile-cotisation`, `heures-ce-mois`, `heures-mois-passe`.
  - `LignesAjoutees(props: { initial: EtatCorrections; etat: EtatCorrections; onChange: (e: EtatCorrections) => void; disabled?: boolean })` ; testid `lignes-ajoutees`.

- [ ] **Step 1: `HeuresDuMois.tsx` : déplacer le code**

Créer le fichier avec `ChampNombre`, `heures()` et les deux blocs « Heures complémentaires du mois » et « Heures supplémentaires du mois » copiés **tels quels** depuis `frontend/src/components/payslip-edit/CorrectionsBulletinPanel.tsx` (lignes 39-99 pour `texteDe`, `lire`, `lireSigne`, `ChampNombre` ; lignes 101-103 pour `heures` ; lignes 167-304 pour les deux blocs, sans l'`Alert` forfait jours). Retirer les `Card`/`CardHeader` qui les entourent : le composant rend un `div className="space-y-4"` avec le texte d'aide (`descriptionHeuresSupDuMois(payslipData)` ou le texte des complémentaires) en `<p className="text-xs text-muted-foreground">`, puis les champs.

```tsx
interface Props {
  payslipData: unknown;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
  tempsPartiel?: boolean;
}

export default function HeuresDuMois({ payslipData, etat, onChange, disabled, tempsPartiel = false }: Props) {
  const declarees = heuresDeclarees(payslipData);
  const hcDeclarees = heuresComplementairesDeclarees(payslipData);
  const [palier1, palier2] = paliersHeuresComplementaires(payslipData);
  const maj = (changement: Partial<EtatCorrections>) => onChange({ ...etat, ...changement });
  return tempsPartiel ? (
    <div className="space-y-4" data-testid="heures-complementaires-du-mois">
      {/* bloc « Heures complémentaires du mois » copié de CorrectionsBulletinPanel, CardContent seul */}
    </div>
  ) : (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">{descriptionHeuresSupDuMois(payslipData)}</p>
      {/* bloc « Heures supplémentaires du mois » copié de CorrectionsBulletinPanel, CardContent seul */}
    </div>
  );
}
```

Les deux commentaires ci-dessus marquent l'endroit où coller le contenu exact des `CardContent` d'origine (`CorrectionsBulletinPanel.tsx` lignes 180-231 et 242-302). Rien d'autre ne change dans ce code.

- [ ] **Step 2: `SurLeNetFormulaire.tsx`**

```tsx
/** Un remboursement ou une retenue sur le net à payer : ne touche ni le brut ni les cotisations. */
import { useState } from 'react';
import type { PrimeAjoutee } from '@/api/payslips';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { lireNombre } from '@/lib/nombreSaisi';
import { cn } from '@/lib/utils';

export default function SurLeNetFormulaire({ onAjout }: { onAjout: (prime: PrimeAjoutee) => void }) {
  const [sens, setSens] = useState<'versement' | 'retenue'>('versement');
  const [libelle, setLibelle] = useState('');
  const [texte, setTexte] = useState('');
  const montant = lireNombre(texte);
  const pret = libelle.trim().length >= 3 && montant !== null && montant > 0;
  return (
    <div className="space-y-3" data-testid="formulaire-sur-le-net">
      <div className="inline-flex overflow-hidden rounded-md border">
        {(['versement', 'retenue'] as const).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSens(s)}
            className={cn('px-3 py-1 text-sm', sens === s ? 'bg-primary text-primary-foreground' : 'bg-background')}
          >
            {s === 'versement' ? 'On lui verse' : 'On lui retient'}
          </button>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="net-libelle">Libellé sur le bulletin</Label>
          <Input id="net-libelle" placeholder="Remboursement de frais" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="net-montant">Montant (€)</Label>
          <Input id="net-montant" inputMode="decimal" value={texte} onChange={(e) => setTexte(e.target.value)} />
        </div>
      </div>
      <Button
        disabled={!pret}
        data-testid="ajouter-sur-le-net"
        onClick={() => {
          if (!pret || montant === null) return;
          onAjout({
            name: libelle.trim(),
            amount: sens === 'retenue' ? -montant : montant,
            is_socially_taxed: false,
            is_taxable: false,
            sur_le_net: true,
            catalog_prime_id: null,
          });
          setLibelle('');
          setTexte('');
        }}
      >
        Ajouter au bulletin
      </Button>
    </div>
  );
}
```

Avant d'écrire, vérifier le signe attendu par le serveur pour une retenue sur le net : `grep -rn "sur_le_net" backend/app/modules/payslips/application/corrections.py | head` et lire comment `primes_ajoutees` avec `sur_le_net` est enregistré. Si le serveur attend un montant positif avec un autre champ pour le sens, adapter `amount` et noter le choix dans le commit.

- [ ] **Step 3: `AjouterUneLigne.tsx`**

```tsx
/** « Ajouter une ligne » : quatre tuiles dans les mots de la RH, deux champs au plus. */
import { useEffect, useRef, useState } from 'react';
import { ArrowLeftRight, Clock, Coins, Percent, Plus } from 'lucide-react';

import AjouterPrimeBouton from '@/components/payslip-edit/AjouterPrimeBouton';
import RegularisationsCotisationCard from '@/components/payslip-edit/RegularisationsCotisationCard';
import RegularisationsHeuresCard from '@/components/payslip-edit/RegularisationsHeuresCard';
import { type DemandeDeCorrection, type EtatCorrections } from '@/features/payroll/utils/correctionsBulletin';
import { PHRASE_FORFAIT_JOURS_SANS_HEURES_SUP } from '@/lib/forfaitJoursAffichage';
import { cn } from '@/lib/utils';
import HeuresDuMois from './HeuresDuMois';
import SurLeNetFormulaire from './SurLeNetFormulaire';

export type Tuile = 'heures' | 'prime' | 'net' | 'cotisation';

interface Props {
  payslipData: unknown;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
  forfaitJours?: boolean;
  tempsPartiel?: boolean;
  employeeId: string;
  year: number;
  month: number;
  demande?: DemandeDeCorrection | null;
}

export default function AjouterUneLigne(props: Props) {
  const { etat, onChange, disabled, forfaitJours, tempsPartiel, employeeId, year, month, demande, payslipData } = props;
  const [ouvert, setOuvert] = useState(false);
  const [tuile, setTuile] = useState<Tuile | null>(null);
  const [moisDesHeures, setMoisDesHeures] = useState<'ce_mois' | 'passe'>('ce_mois');
  const racine = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // L'onglet « Bulletin » demande une régularisation : la bonne tuile s'ouvre.
    if (demande?.carte === 'heures') {
      setOuvert(true);
      setTuile('heures');
      setMoisDesHeures('passe');
    } else if (demande?.carte === 'cotisation') {
      setOuvert(true);
      setTuile('cotisation');
    } else return;
    racine.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demande?.jeton]);

  if (disabled) return null;
  const heures = tempsPartiel ? 'heures complémentaires' : 'heures sup';
  const tuiles: Array<{ cle: Tuile; titre: string; aide: string; Icone: typeof Clock }> = [
    { cle: 'heures', titre: 'Des heures', aide: `en plus ou en moins, ce mois-ci (${heures}) ou un mois passé`, Icone: Clock },
    { cle: 'prime', titre: 'Une prime', aide: '13e mois, panier, rappel de maintien… ou une prime libre', Icone: Coins },
    { cle: 'net', titre: 'Sur le net', aide: 'remboursement de frais, retenue', Icone: ArrowLeftRight },
    { cle: 'cotisation', titre: 'Une cotisation', aide: 'd’un mois passé, oubliée ou fausse', Icone: Percent },
  ];

  return (
    <div ref={racine} className="space-y-3 p-3">
      <button
        type="button"
        data-testid="ajouter-une-ligne"
        onClick={() => setOuvert(!ouvert)}
        className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-blue-500 bg-blue-50 py-2.5 font-semibold text-blue-700 dark:bg-blue-950/30 dark:text-blue-300"
      >
        <Plus className="h-4 w-4" /> Ajouter une ligne
      </button>
      {ouvert ? (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {tuiles.map(({ cle, titre, aide, Icone }) => (
            <button
              key={cle}
              type="button"
              data-testid={`tuile-${cle}`}
              onClick={() => setTuile(tuile === cle ? null : cle)}
              className={cn(
                'rounded-lg border p-3 text-left',
                tuile === cle ? 'border-2 border-blue-600 bg-blue-50 dark:bg-blue-950/30' : 'bg-background'
              )}
            >
              <span className="flex items-center gap-2 font-semibold">
                <Icone className="h-4 w-4" /> {titre}
              </span>
              <span className="mt-1 block text-xs text-muted-foreground">{aide}</span>
            </button>
          ))}
        </div>
      ) : null}

      {ouvert && tuile === 'heures' ? (
        <div className="space-y-3 rounded-lg border bg-background p-3">
          {forfaitJours ? (
            <p className="text-sm" data-testid="forfait-jours-sans-heures-sup">{PHRASE_FORFAIT_JOURS_SANS_HEURES_SUP}</p>
          ) : (
            <>
              <div className="inline-flex overflow-hidden rounded-md border text-sm">
                <button
                  type="button"
                  data-testid="heures-ce-mois"
                  onClick={() => setMoisDesHeures('ce_mois')}
                  className={cn('px-3 py-1', moisDesHeures === 'ce_mois' ? 'bg-primary text-primary-foreground' : 'bg-background')}
                >
                  Ce mois-ci
                </button>
                <button
                  type="button"
                  data-testid="heures-mois-passe"
                  onClick={() => setMoisDesHeures('passe')}
                  className={cn('px-3 py-1', moisDesHeures === 'passe' ? 'bg-primary text-primary-foreground' : 'bg-background')}
                >
                  Un mois passé
                </button>
              </div>
              {moisDesHeures === 'ce_mois' ? (
                <HeuresDuMois payslipData={payslipData} etat={etat} onChange={onChange} tempsPartiel={tempsPartiel} />
              ) : (
                <RegularisationsHeuresCard
                  etat={etat}
                  onChange={onChange}
                  year={year}
                  month={month}
                  demande={demande}
                  tempsPartiel={tempsPartiel}
                />
              )}
            </>
          )}
        </div>
      ) : null}
      {ouvert && tuile === 'prime' ? (
        <div className="rounded-lg border bg-background p-3">
          <AjouterPrimeBouton
            employeeId={employeeId}
            year={year}
            month={month}
            onAjout={(primes) => onChange({ ...etat, primesAjoutees: [...etat.primesAjoutees, ...primes] })}
          />
        </div>
      ) : null}
      {ouvert && tuile === 'net' ? (
        <div className="rounded-lg border bg-background p-3">
          <SurLeNetFormulaire onAjout={(prime) => onChange({ ...etat, primesAjoutees: [...etat.primesAjoutees, prime] })} />
        </div>
      ) : null}
      {ouvert && tuile === 'cotisation' ? (
        <RegularisationsCotisationCard
          payslipData={payslipData}
          etat={etat}
          onChange={onChange}
          year={year}
          month={month}
          demande={demande}
        />
      ) : null}
    </div>
  );
}
```

Avant d'écrire, lire les `Props` exactes de `RegularisationsHeuresCard` (ligne 35) et `RegularisationsCotisationCard` et passer exactement ce qu'elles demandent (même liste que dans `CorrectionsBulletinPanel.tsx` lignes 441-461).

- [ ] **Step 4: `LignesAjoutees.tsx`**

```tsx
/** Ce qui est ajouté et pas encore appliqué : en vert, avec la poubelle pour l'enlever. */
import { Trash2, Undo2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { type EtatCorrections, eurosFr, moisAffiche } from '@/features/payroll/utils/correctionsBulletin';

interface Props {
  initial: EtatCorrections;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
}

function Ligne({ texte, detail, onRetirer, disabled }: { texte: string; detail: string; onRetirer: () => void; disabled?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b bg-green-50 px-3 py-2 text-sm dark:bg-green-950/20">
      <div>
        <span className="font-medium">{texte}</span>
        <span className="ml-2 rounded bg-green-100 px-1.5 text-xs font-semibold text-green-800">Nouvelle</span>
        <div className="text-xs text-muted-foreground">{detail}</div>
      </div>
      {disabled ? null : (
        <Button variant="ghost" size="sm" aria-label={`Ne pas ajouter ${texte}`} onClick={onRetirer}>
          <Trash2 className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}

export default function LignesAjoutees({ initial, etat, onChange, disabled }: Props) {
  const heuresChangees = etat.hs25 !== initial.hs25 || etat.hs50 !== initial.hs50;
  const complementairesChangees = etat.hc1 !== initial.hc1 || etat.hc2 !== initial.hc2;
  const rien =
    !heuresChangees &&
    !complementairesChangees &&
    etat.primesAjoutees.length === 0 &&
    etat.heuresRegulariseesAjoutees.length === 0 &&
    etat.regularisationsAjoutees.length === 0;
  if (rien) return null;
  return (
    <div data-testid="lignes-ajoutees">
      {heuresChangees ? (
        <div className="flex items-center justify-between gap-2 border-b bg-green-50 px-3 py-2 text-sm dark:bg-green-950/20">
          <span className="font-medium">
            Heures sup du mois : {String(etat.hs25).replace('.', ',')} h à 25 %, {String(etat.hs50).replace('.', ',')} h à 50 %
          </span>
          {disabled ? null : (
            <Button variant="ghost" size="sm" onClick={() => onChange({ ...etat, hs25: initial.hs25, hs50: initial.hs50 })}>
              <Undo2 className="mr-1 h-4 w-4" /> Remettre
            </Button>
          )}
        </div>
      ) : null}
      {complementairesChangees ? (
        <div className="flex items-center justify-between gap-2 border-b bg-green-50 px-3 py-2 text-sm dark:bg-green-950/20">
          <span className="font-medium">
            Heures complémentaires du mois : {String(etat.hc1).replace('.', ',')} h et {String(etat.hc2).replace('.', ',')} h
          </span>
          {disabled ? null : (
            <Button variant="ghost" size="sm" onClick={() => onChange({ ...etat, hc1: initial.hc1, hc2: initial.hc2 })}>
              <Undo2 className="mr-1 h-4 w-4" /> Remettre
            </Button>
          )}
        </div>
      ) : null}
      {etat.primesAjoutees.map((p, i) => (
        <Ligne
          key={`prime-${i}`}
          texte={p.name}
          detail={eurosFr(p.amount)}
          disabled={disabled}
          onRetirer={() => onChange({ ...etat, primesAjoutees: etat.primesAjoutees.filter((_, j) => j !== i) })}
        />
      ))}
      {etat.heuresRegulariseesAjoutees.map((h, i) => (
        <Ligne
          key={`heures-${i}`}
          texte={`Heures de ${moisAffiche(h.mois_origine)}`}
          detail={`${String(h.quantite).replace('.', ',')} h — ${h.motif}`}
          disabled={disabled}
          onRetirer={() =>
            onChange({ ...etat, heuresRegulariseesAjoutees: etat.heuresRegulariseesAjoutees.filter((_, j) => j !== i) })
          }
        />
      ))}
      {etat.regularisationsAjoutees.map((r, i) => (
        <Ligne
          key={`coti-${i}`}
          texte={r.libelle}
          detail={r.motif}
          disabled={disabled}
          onRetirer={() => onChange({ ...etat, regularisationsAjoutees: etat.regularisationsAjoutees.filter((_, j) => j !== i) })}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Typecheck, lint, commit**

Run: `cd frontend && npm run typecheck && npx eslint src/components/payslip-edit/bulletin-a-corriger`
Expected: aucune erreur.

```bash
git add frontend/src/components/payslip-edit/bulletin-a-corriger
git commit -m "feat(corriger): ajouter une ligne en quatre tuiles

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Bandeau d'étapes et barre de correction

**Files:**
- Create: `frontend/src/components/payslip-edit/bulletin-a-corriger/BandeauEtapes.tsx`
- Create: `frontend/src/components/payslip-edit/bulletin-a-corriger/BarreDeCorrection.tsx`

**Interfaces:**
- Produces :
  - `BandeauEtapes({ etape }: { etape: 1 | 2 | 3 })` ; testid `bandeau-etapes`, chaque étape `etape-1`…`etape-3` avec `data-etat="faite" | "en-cours" | "a-venir"`.
  - `BarreDeCorrection(props: { changements: number; recalculPrevu: boolean; enCours: boolean; resultat: { netAvant: number | null; netApres: number | null } | null; onAppliquer: () => void; onToutAnnuler: () => void; onAnnulerLApplication: () => void; onFermerResultat: () => void })` ; testids `barre-enregistrement`, `enregistrer-barre`, `resultat-application`, `annuler-application`.

- [ ] **Step 1: `BandeauEtapes.tsx`**

```tsx
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

const ETAPES = ['Cliquez la ligne fausse, ou « Ajouter une ligne »', 'Remplissez', 'Appliquez'];

export default function BandeauEtapes({ etape }: { etape: 1 | 2 | 3 }) {
  return (
    <ol className="grid gap-1.5 sm:grid-cols-3" data-testid="bandeau-etapes">
      {ETAPES.map((texte, i) => {
        const numero = i + 1;
        const etat = numero < etape ? 'faite' : numero === etape ? 'en-cours' : 'a-venir';
        return (
          <li
            key={texte}
            data-testid={`etape-${numero}`}
            data-etat={etat}
            className={cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-sm',
              etat === 'faite' && 'bg-green-100 text-green-800 dark:bg-green-950/40 dark:text-green-300',
              etat === 'en-cours' && 'bg-blue-700 font-semibold text-white',
              etat === 'a-venir' && 'bg-muted text-muted-foreground'
            )}
          >
            {etat === 'faite' ? <Check className="h-4 w-4" /> : <span>{numero}.</span>}
            {texte}
          </li>
        );
      })}
    </ol>
  );
}
```

- [ ] **Step 2: `BarreDeCorrection.tsx`**

```tsx
/**
 * Barre fixe en bas : où qu'elle soit dans la page, la RH voit ce qui reste à
 * appliquer (le 12/09, des heures corrigées n'avaient jamais été enregistrées).
 * Après « Appliquer » : le net avant et après, et « Annuler ».
 */
import { Loader2, Undo2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { eurosFr } from '@/features/payroll/utils/correctionsBulletin';

interface Props {
  changements: number;
  recalculPrevu: boolean;
  enCours: boolean;
  resultat: { netAvant: number | null; netApres: number | null } | null;
  onAppliquer: () => void;
  onToutAnnuler: () => void;
  onAnnulerLApplication: () => void;
  onFermerResultat: () => void;
}

const net = (valeur: number | null) => (valeur == null ? '—' : eurosFr(valeur));

export default function BarreDeCorrection(props: Props) {
  const { changements, recalculPrevu, enCours, resultat } = props;
  if (changements === 0 && !resultat && !enCours) return null;
  return (
    <>
      <div className="h-24" aria-hidden="true" />
      <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-gray-900 text-white shadow-[0_-4px_16px_rgba(0,0,0,0.15)]">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          {enCours ? (
            <p className="flex items-center gap-2 text-sm">
              <Loader2 className="h-4 w-4 animate-spin" /> Martine recalcule le bulletin…
            </p>
          ) : changements > 0 ? (
            <>
              <div className="text-sm" data-testid="barre-enregistrement">
                <p className="font-semibold">
                  {changements} changement{changements > 1 ? 's' : ''} à appliquer
                </p>
                <p className="text-gray-300">
                  {recalculPrevu
                    ? 'Le bulletin sera recalculé en entier : brut, cotisations, net et cumuls.'
                    : 'Seules les notes changent : le bulletin n’est pas recalculé.'}
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" className="text-gray-900" onClick={props.onToutAnnuler}>
                  <Undo2 className="mr-2 h-4 w-4" /> Tout annuler
                </Button>
                <Button className="bg-green-600 hover:bg-green-700" data-testid="enregistrer-barre" onClick={props.onAppliquer}>
                  Appliquer
                </Button>
              </div>
            </>
          ) : resultat ? (
            <>
              <p className="text-sm" data-testid="resultat-application">
                Bulletin recalculé · Net : {net(resultat.netAvant)} →{' '}
                <span className="font-bold text-green-300">{net(resultat.netApres)}</span>
              </p>
              <div className="flex gap-2">
                <Button variant="outline" className="text-gray-900" data-testid="annuler-application" onClick={props.onAnnulerLApplication}>
                  <Undo2 className="mr-2 h-4 w-4" /> Annuler
                </Button>
                <Button variant="ghost" size="sm" aria-label="Fermer" onClick={props.onFermerResultat}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 3: Typecheck, lint, commit**

Run: `cd frontend && npm run typecheck && npx eslint src/components/payslip-edit/bulletin-a-corriger`
Expected: aucune erreur.

```bash
git add frontend/src/components/payslip-edit/bulletin-a-corriger
git commit -m "feat(corriger): bandeau d'étapes et barre appliquer, puis annuler

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: L'onglet `BulletinACorriger`

**Files:**
- Create: `frontend/src/components/payslip-edit/bulletin-a-corriger/BulletinACorriger.tsx`

**Interfaces:**
- Consumes : tâches 1 à 4 ; `getLignesCorrigeables` (`@/api/payslips`) ; `queryKeys.lignesCorrigeables` ; `useActiveCompanyId` ; `eurosFr`, `SaisieApresCalcul`.
- Produces : `BulletinACorriger(props: { payslipId: string; version: string | null; payslipData: unknown; initial: EtatCorrections; etat: EtatCorrections; onChange: (e: EtatCorrections) => void; disabled?: boolean; employeeId: string; year: number; month: number; lienPlanning: string; lienFiche: string; lienSaisies: string; forfaitJours?: boolean; tempsPartiel?: boolean; demande?: DemandeDeCorrection | null; saisiesApresCalcul?: SaisieApresCalcul[]; onAller: (lien: string) => void })` ; testids `bulletin-a-corriger`, `bloc-remuneration`, `bloc-sur-le-net`, `bloc-cotisations`, `net-a-payer`, `corrections-en-attente`, `saisies-apres-calcul`, `corriger-les-variables`, `verrou-corriger`.

- [ ] **Step 1: Écrire le composant**

```tsx
/**
 * L'onglet « Corriger » : le bulletin lui-même, corrigeable ligne par ligne
 * (design du 11/11/2026, retours de Lyon). Chaque correction reste une
 * variable du mois ; « Appliquer » (barre du bas) recalcule tout.
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ExternalLink, Lock, TriangleAlert } from 'lucide-react';

import { getLignesCorrigeables, type LigneCorrigeable } from '@/api/payslips';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  type DemandeDeCorrection,
  type EtatCorrections,
  eurosFr,
  type SaisieApresCalcul,
} from '@/features/payroll/utils/correctionsBulletin';
import {
  estSurLeNet,
  etapeEnCours,
  nombreDeChangements,
  origineDeLaLigne,
  primeDeLaLigne,
} from '@/features/payroll/utils/bulletinACorriger';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';
import AjouterUneLigne from './AjouterUneLigne';
import BandeauEtapes from './BandeauEtapes';
import LigneDePrime from './LigneDePrime';
import LigneDuBulletin from './LigneDuBulletin';
import LignesAjoutees from './LignesAjoutees';

interface Props {
  payslipId: string;
  version: string | null;
  payslipData: unknown;
  initial: EtatCorrections;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
  employeeId: string;
  year: number;
  month: number;
  lienPlanning: string;
  lienFiche: string;
  lienSaisies: string;
  forfaitJours?: boolean;
  tempsPartiel?: boolean;
  demande?: DemandeDeCorrection | null;
  saisiesApresCalcul?: SaisieApresCalcul[];
  onAller: (lien: string) => void;
}

const SOURCE_DES_PRIMES = '« Primes du mois »';

function netAPayer(payslipData: unknown): number | null {
  const valeur = (payslipData as { net_a_payer?: unknown } | null)?.net_a_payer;
  return typeof valeur === 'number' ? valeur : null;
}

function Titre({ children }: { children: React.ReactNode }) {
  return <div className="bg-muted px-3 py-1.5 text-xs font-semibold text-muted-foreground">{children}</div>;
}

export default function BulletinACorriger(props: Props) {
  const { payslipId, version, payslipData, initial, etat, onChange, disabled, demande, onAller } = props;
  const companyId = useActiveCompanyId();
  const query = useQuery({
    queryKey: queryKeys.lignesCorrigeables(companyId, payslipId, version),
    queryFn: () => getLignesCorrigeables(payslipId, companyId),
    enabled: Boolean(companyId && payslipId),
    staleTime: 30_000,
  });
  const [enEdition, setEnEdition] = useState<Set<string>>(new Set());
  const surEdition = (code: string, ouverte: boolean) =>
    setEnEdition((avant) => {
      const apres = new Set(avant);
      if (ouverte) apres.add(code);
      else apres.delete(code);
      return apres;
    });

  const lignes = (query.data?.lignes ?? []).filter((l) => l.code);
  const enAttente = query.data?.en_attente ?? [];
  const autresMontantsDuNet = (query.data?.a_la_source ?? []).filter((b) => !b.source.startsWith(SOURCE_DES_PRIMES));
  const changements = nombreDeChangements(initial, etat);
  const lienDe = (ligne: LigneCorrigeable) => {
    const origine = origineDeLaLigne(ligne);
    if (origine === 'planning') return { texte: 'Vient du planning · ouvrir le planning du mois', onOuvrir: () => onAller(props.lienPlanning) };
    if (origine === 'fiche') return { texte: 'Vient de la fiche · ouvrir la fiche', onOuvrir: () => onAller(props.lienFiche) };
    return null;
  };
  const ligneDe = (ligne: LigneCorrigeable) => {
    const prime = primeDeLaLigne(etat, ligne);
    return prime ? (
      <LigneDePrime key={ligne.code} prime={prime} etat={etat} onChange={onChange} disabled={disabled} />
    ) : (
      <LigneDuBulletin
        key={ligne.code}
        ligne={ligne}
        etat={etat}
        onChange={onChange}
        disabled={disabled}
        lienSource={lienDe(ligne)}
        demande={demande}
        onEdition={surEdition}
      />
    );
  };
  const remuneration = lignes.filter((l) => l.bloc === 'brut');
  const cotisations = lignes.filter((l) => l.bloc === 'cotisations');
  const impot = lignes.filter((l) => l.bloc === 'impot');
  const primesDuNet = etat.primes.filter(estSurLeNet);

  return (
    <div className="space-y-4" data-testid="bulletin-a-corriger">
      {disabled ? (
        <Alert data-testid="verrou-corriger">
          <Lock className="h-4 w-4" />
          <AlertDescription>Ce bulletin ne se corrige pas pour l’instant : la raison est affichée en haut de la page.</AlertDescription>
        </Alert>
      ) : (
        <BandeauEtapes etape={etapeEnCours(enEdition.size > 0, changements)} />
      )}

      {enAttente.length > 0 ? (
        <Alert variant="destructive" data-testid="corrections-en-attente">
          <TriangleAlert className="h-4 w-4" />
          <AlertDescription className="space-y-2">
            <p>Ces corrections ne sont plus sur le bulletin. Il ne peut pas être validé tant qu’elles ne sont pas retirées.</p>
            {enAttente.map((attente) => {
              const id = String(attente.saisie_id ?? '');
              const retiree = etat.correctionsRetirees.includes(id);
              return (
                <div key={id || attente.ligne} className="flex flex-wrap items-center justify-between gap-2">
                  <span className={retiree ? 'line-through' : ''}>
                    {attente.libelle} — {attente.motif} ({attente.raison})
                  </span>
                  {id && !disabled ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        onChange({
                          ...etat,
                          correctionsRetirees: retiree
                            ? etat.correctionsRetirees.filter((x) => x !== id)
                            : [...etat.correctionsRetirees, id],
                        })
                      }
                    >
                      {retiree ? 'Garder' : 'Retirer'}
                    </Button>
                  ) : null}
                </div>
              );
            })}
          </AlertDescription>
        </Alert>
      ) : null}

      {props.saisiesApresCalcul && props.saisiesApresCalcul.length > 0 ? (
        <Alert data-testid="saisies-apres-calcul">
          <AlertDescription>
            Saisies du mois enregistrées après le calcul, pas encore sur le bulletin :{' '}
            {props.saisiesApresCalcul.map((s) => `${s.libelle} (${eurosFr(s.montant)})`).join(', ')}. « Appliquer » ou « Régénérer » les y prend.
          </AlertDescription>
        </Alert>
      ) : null}

      {query.isLoading ? <p className="text-sm text-muted-foreground">Lecture des lignes du bulletin…</p> : null}
      {query.isError ? <p className="text-sm text-destructive">Les lignes du bulletin n’ont pas pu être lues. Rechargez la page.</p> : null}

      <div className="overflow-hidden rounded-lg border bg-background">
        <div data-testid="bloc-remuneration">
          <Titre>Rémunération</Titre>
          {remuneration.map(ligneDe)}
        </div>
        <LignesAjoutees initial={initial} etat={etat} onChange={onChange} disabled={disabled} />
        {primesDuNet.length > 0 || autresMontantsDuNet.length > 0 ? (
          <div data-testid="bloc-sur-le-net">
            <Titre>Sur le net</Titre>
            {primesDuNet.map((p) => (
              <LigneDePrime key={p.saisieId} prime={p} etat={etat} onChange={onChange} disabled={disabled} />
            ))}
            {autresMontantsDuNet.map((b) => (
              <div key={`${b.libelle}-${b.source}`} className="flex items-center justify-between border-b px-3 py-2 text-sm">
                <div>
                  <div className="font-medium">{b.libelle}</div>
                  <div className="text-xs text-muted-foreground">Se corrige dans {b.source}</div>
                </div>
                <span className="tabular-nums">{b.montant != null ? eurosFr(b.montant) : ''}</span>
              </div>
            ))}
          </div>
        ) : null}
        {cotisations.length > 0 ? (
          <details data-testid="bloc-cotisations">
            <summary className="cursor-pointer bg-muted px-3 py-1.5 text-xs font-semibold text-muted-foreground">
              Cotisations ({cotisations.length} lignes) · elles se recalculent seules : ouvrez seulement si une cotisation précise est fausse
            </summary>
            {cotisations.map(ligneDe)}
          </details>
        ) : null}
        {impot.length > 0 ? (
          <div>
            <Titre>Impôt</Titre>
            {impot.map(ligneDe)}
          </div>
        ) : null}
        <div className="flex items-center justify-between bg-muted/60 px-3 py-2 font-bold" data-testid="net-a-payer">
          <span>Net à payer</span>
          <span className="tabular-nums">{netAPayer(payslipData) != null ? eurosFr(netAPayer(payslipData)!) : '—'}</span>
        </div>
        <AjouterUneLigne
          payslipData={payslipData}
          etat={etat}
          onChange={onChange}
          disabled={disabled}
          forfaitJours={props.forfaitJours}
          tempsPartiel={props.tempsPartiel}
          employeeId={props.employeeId}
          year={props.year}
          month={props.month}
          demande={demande}
        />
      </div>

      <Button
        variant="link"
        className="px-0"
        data-testid="corriger-les-variables"
        onClick={() => onAller(props.lienSaisies)}
      >
        Acomptes, frais et autres saisies du mois <ExternalLink className="ml-1 h-3 w-3" />
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck, lint, commit**

Run: `cd frontend && npm run typecheck && npx eslint src/components/payslip-edit/bulletin-a-corriger`
Expected: aucune erreur.

```bash
git add frontend/src/components/payslip-edit/bulletin-a-corriger/BulletinACorriger.tsx
git commit -m "feat(corriger): l'onglet corriger devient le bulletin

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Brancher l'onglet dans `PayslipEdit.tsx`, net avant/après et « Annuler »

**Files:**
- Modify: `frontend/src/pages/rh/PayslipEdit.tsx` (imports ; `enregistrer` lignes 315-368 ; onglet « corriger » lignes 626-660 ; barre fixe lignes 803-840)

**Interfaces:**
- Consumes : `BulletinACorriger`, `BarreDeCorrection`, `nombreDeChangements` ; `getPayslipHistory`, `restorePayslipVersion` (`@/api/payslips`) ; `choixApresCorrection`, `phrasesApresCorrection` (déjà importés par la page ou par `HistoryPanel.tsx` : reprendre le même import).

- [ ] **Step 1: Imports et état**

Ajouter aux imports :

```tsx
import BulletinACorriger from '@/components/payslip-edit/bulletin-a-corriger/BulletinACorriger';
import BarreDeCorrection from '@/components/payslip-edit/bulletin-a-corriger/BarreDeCorrection';
import { nombreDeChangements } from '@/features/payroll/utils/bulletinACorriger';
```

Ajouter `getPayslipHistory` et `restorePayslipVersion` à l'import existant de `@/api/payslips`. Retirer l'import de `CorrectionsBulletinPanel`.

Près des autres `useState` de la page :

```tsx
const [resultat, setResultat] = useState<{ netAvant: number | null; netApres: number | null } | null>(null);
```

Et une fonction locale, sous `messageDErreur` :

```tsx
function netDuBulletin(data: unknown): number | null {
  const valeur = (data as { net_a_payer?: unknown } | null)?.net_a_payer;
  return typeof valeur === 'number' ? valeur : null;
}
```

- [ ] **Step 2: Retenir le net avant/après dans `enregistrer`**

Dans `enregistrer`, avant l'appel `editPayslip`, ajouter `const netAvant = netDuBulletin(payslip.payslip_data);`. Dans la branche `else if (reponse.recalcule)`, après le `toast`, ajouter :

```tsx
setResultat({ netAvant, netApres: netDuBulletin(reponse.payslip?.payslip_data) });
```

Au début de `enregistrer`, ajouter `setResultat(null);`.

- [ ] **Step 3: « Annuler » après application**

Sous `enregistrer` :

```tsx
const annulerLApplication = async () => {
  if (!payslipId || !payslip) return;
  setIsSaving(true);
  try {
    const versions = await getPayslipHistory(payslipId);
    const derniere = versions.reduce((max, v) => Math.max(max, v.version), 0);
    if (!derniere) throw new Error('Aucune version précédente à remettre.');
    const reponse = await restorePayslipVersion(payslipId, derniere, payslip.company_id);
    const suite = choixApresCorrection(reponse);
    if (suite.kind === 'choix') {
      setRefusApresCorrection(suite.refus);
      toast({ title: 'Bulletin remis, non recalculé', description: suite.refus.message, variant: 'destructive' });
    } else if (suite.kind === 'regenerer') {
      toast({ title: 'Bulletin remis, non recalculé', description: `${suite.message} — utilisez « Régénérer ».`, variant: 'destructive' });
    } else {
      toast({ title: 'Correction annulée', description: 'Le bulletin est revenu à sa version d’avant.' });
    }
    setResultat(null);
    await apresChangement();
  } catch (error) {
    toast({
      title: 'Annulation impossible',
      description: messageDErreur(error, 'Le bulletin n’a pas pu revenir à sa version d’avant'),
      variant: 'destructive',
    });
  } finally {
    setIsSaving(false);
  }
};
```

Si `choixApresCorrection` refuse le type `PayslipRestoreResponse`, regarder comment `HistoryPanel.tsx` (lignes 90-110) l'appelle avec ce même type et reprendre exactement son import.

- [ ] **Step 4: Monter l'onglet**

Remplacer `<CorrectionsBulletinPanel … />` (dans `TabsContent value="corriger"`) par :

```tsx
<BulletinACorriger
  payslipId={payslip.id}
  version={payslip.updated_at ?? null}
  payslipData={payslip.payslip_data}
  initial={initial}
  etat={etat}
  onChange={setEtat}
  disabled={isEditLocked}
  employeeId={payslip.employee_id}
  year={payslip.year}
  month={payslip.month}
  lienPlanning={lienCalendrierDuSalarie(payslip.employee_id, { year: payslip.year, month: payslip.month })}
  lienFiche={`/employees/${encodeURIComponent(payslip.employee_id)}`}
  lienSaisies={lienSaisies}
  forfaitJours={salarieBulletin?.is_forfait_jour === true}
  tempsPartiel={estTempsPartiel(salarieBulletin)}
  demande={demande}
  saisiesApresCalcul={saisiesApresLeCalcul(saisiesDuMois, payslip.generated_at, etat)}
  onAller={aller}
/>
```

`NotesSection` reste en dessous, inchangée. Si `initial` peut être `null` à cet endroit, garder la même garde que le reste du rendu (la page ne rend l'onglet qu'une fois `initial` et `etat` chargés ; sinon entourer de `initial ? … : null`).

- [ ] **Step 5: Remplacer la barre fixe**

Remplacer tout le bloc `{modifie && !isEditLocked ? ( <> … </> ) : null}` (barre orange, lignes 803-840) par :

```tsx
{!isEditLocked && initial && etat ? (
  <BarreDeCorrection
    changements={modifie ? Math.max(1, nombreDeChangements(initial, etat)) : 0}
    recalculPrevu={recalculPrevu}
    enCours={isSaving}
    resultat={resultat}
    onAppliquer={demanderEnregistrement}
    onToutAnnuler={() => setEtat(initial)}
    onAnnulerLApplication={() => void annulerLApplication()}
    onFermerResultat={() => setResultat(null)}
  />
) : null}
```

`Math.max(1, …)` : une note seule change `modifie` sans compter de ligne ; la barre doit quand même apparaître.

- [ ] **Step 6: Typecheck, lint, tests unitaires**

Run: `cd frontend && npm run typecheck && npm run lint && npx vitest run src/features/payroll`
Expected: aucune erreur, tests verts.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/rh/PayslipEdit.tsx
git commit -m "feat(corriger): onglet corriger branché, net avant/après et annuler

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Parcours de bout en bout (Playwright, bulletin fictif)

**Files:**
- Create: `frontend/e2e/connecte/15-corriger-sur-le-bulletin.spec.ts`
- Modify: `frontend/e2e/connecte/06-edition-bulletin.spec.ts`

- [ ] **Step 1: Écrire le nouveau parcours**

Copier dans le nouveau fichier, sans les changer, depuis `06-edition-bulletin.spec.ts` : les imports, `BULLETIN_ID` (remplacer le dernier chiffre par `15`), `SALARIE_ID` (finir par `16`), `chemin`, le type `Corps`, `bulletinFictif` et `preparerBulletin`, avec ces différences :
- `LIGNES_CORRIGEABLES` est remplacé par :

```ts
const LIGNES = {
  lignes: [
    { code: 'brut:salaire_base', bloc: 'brut', libelle: 'Salaire de base QA', mode: 'base_ou_taux', base: 100, taux: 10, montant: 1000 },
    { code: 'brut:prime_anciennete', bloc: 'brut', libelle: 'Prime d’ancienneté QA', mode: 'montant', montant: 58.2 },
    { code: 'brut:maintien_employeur', bloc: 'brut', libelle: 'Maintien de salaire employeur', mode: 'montant', montant: 312.44 },
    { code: 'brut:saisie:saisie-qa-1', bloc: 'brut', libelle: 'Prime de chantier QA', mode: null, montant: 100 },
    {
      code: 'cotisation:vieillesse_qa', bloc: 'cotisations', libelle: 'Vieillesse QA', mode: 'base_ou_taux',
      base: 1177.5, taux_salarial: 0.069, taux_patronal: 0.0855, montant_salarial: 81.25, montant_patronal: 100.68,
    },
  ],
  en_attente: [],
  a_la_source: [],
};
```

- la route `/history` répond `[{ version: 3, edited_at: '2026-11-11T08:00:00+00:00', edited_by: null, edited_by_name: null, changes_summary: '', previous_payslip_data: {} }]` ;
- une route `POST …/restore` répond `{ status: 'success', message: 'Version rétablie.', payslip: bulletin, recalcule: true }` et pousse le corps dans un tableau `restaurations` renvoyé par `preparerBulletin` avec `envois` (`return { envois, restaurations }`) ;
- la réponse d'`edit` met `payslip_data.net_a_payer` à `912.34` dans le bulletin renvoyé (`{ ...bulletin, payslip_data: { ...bulletin.payslip_data, net_a_payer: 912.34 } }`) ;
- après `page.goto`, cliquer l'onglet « Corriger » et attendre `page.getByTestId('bandeau-etapes')`.

Puis les tests :

```ts
test.describe('Corriger sur le bulletin (données fictives)', () => {
  test('corriger un montant : crayon, valeur, motif, appliquer, net avant/après', async ({ page }) => {
    const { envois } = await preparerBulletin(page);
    await expect(page.getByTestId('etape-1')).toHaveAttribute('data-etat', 'en-cours');
    await page.getByTestId('corriger-brut:prime_anciennete').click();
    await expect(page.getByTestId('etape-2')).toHaveAttribute('data-etat', 'en-cours');
    await page.getByTestId('valeur-brut:prime_anciennete').fill('63');
    await expect(page.getByTestId('apercu-brut:prime_anciennete')).toContainText('63,00');
    await page.getByTestId('motif-brut:prime_anciennete').getByRole('button', { name: 'Correction d’une erreur de calcul' }).click();
    await expect(page.getByTestId('barre-enregistrement')).toContainText('1 changement à appliquer');
    await page.getByTestId('enregistrer-barre').click();
    await expect(page.getByTestId('resultat-application')).toContainText('900,00');
    await expect(page.getByTestId('resultat-application')).toContainText('912,34');
    expect(envois[0].corrections).toMatchObject({
      corrections_ajoutees: [{ ligne: 'brut:prime_anciennete', montant: 63, motif: 'Correction d’une erreur de calcul' }],
    });
  });

  test('retirer une ligne calculée demande un motif, la ligne reste barrée et se remet', async ({ page }) => {
    await preparerBulletin(page);
    await page.getByTestId('retirer-brut:maintien_employeur').click();
    await page.getByTestId('motif-retrait-brut:maintien_employeur').getByRole('button', { name: 'Ligne non due ce mois-ci' }).click();
    await expect(page.getByTestId('ligne-brut:maintien_employeur')).toContainText('Retirée');
    await page.getByTestId('remettre-brut:maintien_employeur').click();
    await expect(page.getByTestId('ligne-brut:maintien_employeur')).not.toContainText('Retirée');
  });

  test('retirer une prime saisie', async ({ page }) => {
    const { envois } = await preparerBulletin(page);
    await page.getByTestId('retirer-prime-saisie-qa-1').click();
    await expect(page.getByTestId('prime-saisie-qa-1')).toContainText('Retirée');
    await page.getByTestId('enregistrer-barre').click();
    await expect(page.getByTestId('resultat-application')).toBeVisible();
    expect(envois[0].corrections).toMatchObject({ primes_retirees: ['saisie-qa-1'] });
  });

  test('ajouter des heures sup du mois par la tuile « Des heures »', async ({ page }) => {
    const { envois } = await preparerBulletin(page);
    await page.getByTestId('ajouter-une-ligne').click();
    await page.getByTestId('tuile-heures').click();
    await page.getByTestId('heures-sup-25').fill('4');
    await expect(page.getByTestId('lignes-ajoutees')).toContainText('4 h à 25 %');
    await page.getByTestId('enregistrer-barre').click();
    await expect(page.getByTestId('resultat-application')).toBeVisible();
    expect(envois[0].corrections).toHaveProperty('heures_sup');
  });

  test('ajouter un remboursement sur le net', async ({ page }) => {
    const { envois } = await preparerBulletin(page);
    await page.getByTestId('ajouter-une-ligne').click();
    await page.getByTestId('tuile-net').click();
    await page.getByLabel('Libellé sur le bulletin').fill('Remboursement QA');
    await page.getByLabel('Montant (€)').fill('25');
    await page.getByTestId('ajouter-sur-le-net').click();
    await expect(page.getByTestId('lignes-ajoutees')).toContainText('Remboursement QA');
    await page.getByTestId('enregistrer-barre').click();
    await expect(page.getByTestId('resultat-application')).toBeVisible();
    expect(envois[0].corrections).toMatchObject({ primes_ajoutees: [{ name: 'Remboursement QA', sur_le_net: true }] });
  });

  test('annuler après application remet la dernière version', async ({ page }) => {
    const { restaurations } = await preparerBulletin(page);
    await page.getByTestId('retirer-prime-saisie-qa-1').click();
    await page.getByTestId('enregistrer-barre').click();
    await page.getByTestId('annuler-application').click();
    await expect(page.getByText('Correction annulée', { exact: true })).toBeVisible();
    expect(restaurations[0]).toEqual({ version: 3 });
  });
});
```

Avant de figer les assertions sur `envois[0].corrections`, lire `requeteDeCorrection` (`correctionsBulletin.ts` ligne 542) pour les noms exacts des clés envoyées (`corrections_ajoutees`, `heures_sup`, `primes_retirees`, `primes_ajoutees`) et les reprendre tels quels.

- [ ] **Step 2: Adapter `06-edition-bulletin.spec.ts`**

1. Dans `preparerBulletin`, remplacer l'attente après le clic sur « Corriger » par : `await expect(page.getByTestId('bandeau-etapes').or(page.getByTestId('verrou-corriger'))).toBeVisible();`.
2. Ajouter une aide et l'appeler avant chaque usage de `heures-sup-25`, `heures-sup-50` ou `revenir-au-planning` dans l'onglet Corriger :

```ts
async function ouvrirHeuresDuMois(page: Page) {
  await page.getByTestId('ajouter-une-ligne').click();
  await page.getByTestId('tuile-heures').click();
}
```

3. Supprimer les tests qui décrivent l'ancienne carte « Corriger une ligne » et sont remplacés par le fichier 15 : « la carte liste les lignes du serveur et grise une ligne qui ne se corrige pas ici », « corriger la base d’une ligne : le motif est exigé, la correction part au recalcul », « un taux de cotisation se tape en pourcentage et part en fraction ». Les noter dans le message de commit.
4. « corriger, retirer et ajouter une prime » : remplacer `page.locator('#montant-saisie-qa-1').fill('150')` par un clic sur le crayon de la prime (`page.getByTestId('prime-saisie-qa-1').getByRole('button', { name: 'Corriger Prime de chantier QA' })`) puis `page.getByTestId('montant-prime-saisie-qa-1').fill('150')` ; « Retirer Panier QA » garde son nom ; le bouton « Ajouter une prime » est derrière `ajouter-une-ligne` puis `tuile-prime`.
5. « une correction déjà enregistrée se retire… » : remplacer la recherche par `carte` par `page.getByTestId('corrections-en-attente')` pour le bandeau ; la correction enregistrée se retire par le bouton « Remettre la valeur de Martine » de sa ligne.
6. « le bulletin s’ouvre sur l’onglet Bulletin… » : remplacer `corriger-une-ligne` par `bandeau-etapes`, et `heures-sup-25` (visible) par `ajouter-une-ligne`.
7. « un bulletin verrouillé ne se corrige pas » : attendre `verrou-corriger` au lieu de `heures-sup-25` désactivé.
8. Les tests qui cliquent `enregistrer-barre` : le bouton s'appelle maintenant « Appliquer » ; garder le testid.

- [ ] **Step 3: Typecheck des e2e**

Run: `cd frontend && npm run e2e:typecheck`
Expected: aucune erreur.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/connecte/15-corriger-sur-le-bulletin.spec.ts frontend/e2e/connecte/06-edition-bulletin.spec.ts
git commit -m "test(e2e): corriger sur le bulletin ; 06 adapté (3 tests de l'ancienne carte remplacés par 15)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Retirer l'ancien onglet, preuves, déploiement sur le site de test

**Files:**
- Delete: `frontend/src/components/payslip-edit/CorrectionsBulletinPanel.tsx`, `frontend/src/components/payslip-edit/CorrigerUneLigneCard.tsx`

- [ ] **Step 1: Vérifier que plus rien ne les importe, puis les supprimer**

Run: `cd frontend && grep -rn "CorrectionsBulletinPanel\|CorrigerUneLigneCard" src e2e | grep -v "^src/components/payslip-edit/Correct\|^src/components/payslip-edit/CorrigerUne"`
Expected: aucune ligne. Puis `git rm` des deux fichiers.

- [ ] **Step 2: Suite complète locale**

Run: `cd frontend && npm run typecheck && npm run lint && npm test`
Expected: tout vert (2 287 tests au 10/11, plus ceux de la tâche 1).

- [ ] **Step 3: Commit et poussée**

```bash
git commit -m "refactor(corriger): ancien onglet retiré

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push -u origin feat/corriger-sur-le-bulletin
```

- [ ] **Step 4: Déployer sur le site de test et jouer les e2e**

Run: `gh workflow run deploy-test-env.yml --ref feat/corriger-sur-le-bulletin` puis suivre le run (`gh run watch`). Une fois en ligne, depuis `frontend/` avec `frontend/.env.e2e` (copié du dossier principal s'il manque) : `npx playwright test e2e/connecte/15-corriger-sur-le-bulletin.spec.ts e2e/connecte/06-edition-bulletin.spec.ts e2e/connecte/08-mode-paie.spec.ts`.
Expected: tous verts. Un test par fichier à la fois si la base est chargée (règle : jamais de visites en série).

Aucun calcul ne change : pas de filet avant/après à lancer. Le noter dans le journal de suivi (`data/_rapports/2026-11-09-etat-des-lieux-complet.md`, § 14) avec la version déployée.

---

### Task 9: Le PDF pour Elsa

**Files:**
- Create (hors dépôt) : `~/dev/eywai-filet/corriger-sur-le-bulletin/` (captures, source HTML, PDF)

- [ ] **Step 1: Captures**

Sur le site de test, avec le bulletin fictif intercepté du test 15 (aucun vrai salarié), capturer : l'onglet au repos (bandeau étape 1) ; une ligne en édition (valeur, aperçu, puces) ; une ligne retirée (barrée, « Remettre ») ; les 4 tuiles ouvertes ; la barre « 1 changement à appliquer » ; la barre après application (net avant → après, « Annuler »). Les prendre avec Playwright (`page.screenshot`) dans un script du dossier ci-dessus, en réutilisant `preparerBulletin`.

- [ ] **Step 2: Le document**

Une page HTML de 2 à 4 pages A4, en français simple, convertie en PDF (Chrome sans tête : `--print-to-pdf`) :
1. « On corrige sur le bulletin » : une phrase, une capture de l'onglet.
2. Schéma des 3 étapes (le bandeau) : cliquer la ligne, remplir, appliquer.
3. Corriger, retirer, ajouter : une capture chacun, une phrase chacun.
4. « Appliquer » puis « Annuler » : la barre avant et après.
Aucun nom réel, aucun mot de code.

- [ ] **Step 3: Remettre à Alexandre**

Ouvrir le PDF pour le relire, le noter au journal de suivi, et le remettre à Alexandre, qui l'enverra.
