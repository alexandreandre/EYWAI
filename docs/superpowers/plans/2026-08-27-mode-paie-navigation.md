# Mode paie — navigation réduite : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Réduire la navigation RH à 19 entrées sur 48 — la paie et ce dont la paie a besoin — pour tous les comptes client, avec les routes retirées réellement inaccessibles et sans alerte pointant vers un écran retiré.

**Architecture:** Un module pur `lib/payrollFocus.ts` porte la liste blanche et deux prédicats, sur le modèle de `lib/routeAccess.ts` déjà en place. Trois consommateurs l'utilisent : la sidebar (filtrage par section), `App.tsx` (garde de route, à côté du garde `isEmployeeOnlyPath` existant) et `lib/rhPendingTasks.ts` (filtrage des alertes sur leur `href`). Aucun changement côté serveur, aucun changement de droits.

**Tech Stack:** React 18 + TypeScript, Vite, React Router, Vitest.

## Global Constraints

- Spec de référence : `docs/superpowers/specs/2026-08-27-mode-paie-navigation-design.md`.
- Vitest tourne en `environment: "node"` et n'inclut que `src/**/*.test.ts` — **pas de `.tsx`**. Toute logique à tester doit vivre dans un module `.ts` pur.
- `src/app/routes.snapshot.test.ts` compare les `<Route path=...>` de `App.tsx` à `scripts/.baseline/pages-routes.json`. **Ne créer ni supprimer aucun élément `<Route>`** — le garde est une clause de retour anticipé, pas une route.
- Le mode ne modifie aucun droit d'action, aucune permission, ni l'espace salarié, manager ou admin.
- Contournement : `isPlatformAdmin(user)` **ou** e-mail dans `PAYROLL_FOCUS_BYPASS_EMAILS`.
- Commandes : `npm test` et `npm run lint` depuis `frontend/`.

---

### Task 1 : Le module pur — liste blanche et prédicats de chemin

**Files:**
- Create: `frontend/src/lib/payrollFocus.ts`
- Test: `frontend/src/lib/payrollFocus.test.ts`

**Interfaces:**
- Consumes: `isPlatformAdmin`, `PlatformAdminUser` depuis `@/lib/platformAdmin`.
- Produces: `PAYROLL_FOCUS_NAV_URLS: readonly string[]` (19 entrées), `isPayrollFocusAllowed(pathname: string): boolean`, `isPayrollFocusActive(user): boolean`, `PayrollFocusUser`.

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `frontend/src/lib/payrollFocus.test.ts` :

```ts
import { describe, expect, it } from 'vitest';

import {
  PAYROLL_FOCUS_NAV_URLS,
  isPayrollFocusActive,
  isPayrollFocusAllowed,
} from './payrollFocus';

describe('PAYROLL_FOCUS_NAV_URLS', () => {
  it('contient exactement 19 entrées, sans doublon', () => {
    expect(PAYROLL_FOCUS_NAV_URLS).toHaveLength(19);
    expect(new Set(PAYROLL_FOCUS_NAV_URLS).size).toBe(19);
  });
});

describe('isPayrollFocusAllowed', () => {
  it('autorise chaque entrée de menu du périmètre', () => {
    for (const url of PAYROLL_FOCUS_NAV_URLS) {
      expect(isPayrollFocusAllowed(url)).toBe(true);
    }
  });

  it('autorise les sous-routes ouvertes depuis ces écrans', () => {
    expect(isPayrollFocusAllowed('/employees/abc-123')).toBe(true);
    expect(isPayrollFocusAllowed('/payroll/abc-123')).toBe(true);
    expect(isPayrollFocusAllowed('/payslips/abc-123/edit')).toBe(true);
  });

  it('refuse les écrans hors périmètre', () => {
    for (const url of [
      '/cse',
      '/formation',
      '/recruitment',
      '/onboarding',
      '/employee-exits',
      '/trial-periods',
      '/teams',
      '/documents',
      '/residence-permits',
      '/medical-follow-up',
      '/annual-reviews',
      '/analytics',
      '/analytics-paie',
      '/analytics-gestion',
      '/users',
      '/company',
      '/planning',
      '/badgeuse-rh',
      '/augmentations-et-promotions',
    ]) {
      expect(isPayrollFocusAllowed(url)).toBe(false);
    }
  });

  it('ignore la query string et le fragment', () => {
    expect(isPayrollFocusAllowed('/employees?alert=deadlines')).toBe(true);
    expect(isPayrollFocusAllowed('/annual-reviews?focus=upcoming')).toBe(false);
    expect(isPayrollFocusAllowed('/formation#entretiens')).toBe(false);
  });

  it('tolère la barre oblique finale', () => {
    expect(isPayrollFocusAllowed('/exports/')).toBe(true);
    expect(isPayrollFocusAllowed('/cse/')).toBe(false);
  });

  it('ne confond pas deux chemins de même préfixe textuel', () => {
    expect(isPayrollFocusAllowed('/employee-loans')).toBe(true);
    expect(isPayrollFocusAllowed('/employee-exits')).toBe(false);
  });
});

describe('isPayrollFocusActive', () => {
  it('est actif pour un compte client', () => {
    expect(isPayrollFocusActive({ role: 'rh', email: 'gaelle.bouali@maji-invest.fr' })).toBe(true);
    expect(isPayrollFocusActive({ role: 'admin', email: 'vanessa.amate@maji-invest.fr' })).toBe(true);
  });

  it('est inactif pour un administrateur plateforme', () => {
    expect(isPayrollFocusActive({ role: 'rh', is_platform_admin: true })).toBe(false);
    expect(isPayrollFocusActive({ role: 'rh', is_super_admin: true })).toBe(false);
  });

  it('est inactif pour un e-mail de la liste de contournement, quelle que soit la casse', () => {
    expect(isPayrollFocusActive({ role: 'rh', email: 'alexandreandre2004@gmail.com' })).toBe(false);
    expect(isPayrollFocusActive({ role: 'rh', email: 'Alexandreandre2004@GMAIL.com ' })).toBe(false);
  });

  it('est inactif sans utilisateur', () => {
    expect(isPayrollFocusActive(null)).toBe(false);
    expect(isPayrollFocusActive(undefined)).toBe(false);
  });
});
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

```bash
cd frontend && npm test -- src/lib/payrollFocus.test.ts
```

Attendu : FAIL — `Failed to resolve import "./payrollFocus"`.

- [ ] **Step 3 : Écrire l'implémentation**

Créer `frontend/src/lib/payrollFocus.ts` :

```ts
/**
 * Mode paie — navigation réduite pendant la reprise client.
 *
 * Ne laisse accessible que la paie et ce dont la paie a besoin. S'applique à
 * tous les comptes client ; les administrateurs plateforme EYWAI conservent la
 * navigation complète.
 *
 * Spec : docs/superpowers/specs/2026-08-27-mode-paie-navigation-design.md
 */

import { isPlatformAdmin, type PlatformAdminUser } from '@/lib/platformAdmin';

/** Les 19 entrées de menu conservées en mode paie. */
export const PAYROLL_FOCUS_NAV_URLS: readonly string[] = [
  '/',
  '/employees',
  '/schedules',
  '/leaves',
  '/suivi-ijss',
  '/suivi-temps-travail',
  '/suivi-contingent-hs',
  '/suivi-modulation',
  '/suivi-cet',
  '/expenses',
  '/saisies',
  '/salary-seizures',
  '/salary-advances',
  '/employee-loans',
  '/simulation',
  '/rates',
  '/taux-pas',
  '/exports',
  '/payroll',
];

/**
 * Sous-routes atteignables depuis les écrans du périmètre mais absentes de la
 * navigation. `/employees/:id` et `/payroll/:id` sont déjà couvertes par le
 * préfixe de leur entrée de menu ; l'édition de bulletin ne l'est pas.
 */
const PAYROLL_FOCUS_EXTRA_PREFIXES: readonly string[] = ['/payslips'];

/** Comptes conservant la navigation complète en plus des admins plateforme. */
export const PAYROLL_FOCUS_BYPASS_EMAILS: readonly string[] = [
  'alexandreandre2004@gmail.com',
];

export type PayrollFocusUser = PlatformAdminUser & { email?: string };

function normalizePath(pathname: string): string {
  const path = pathname.split('?')[0].split('#')[0];
  return path.length > 1 && path.endsWith('/') ? path.slice(0, -1) : path;
}

/** Le chemin est-il atteignable quand le mode paie est actif ? */
export function isPayrollFocusAllowed(pathname: string): boolean {
  const path = normalizePath(pathname);
  if (path === '/') return true;
  return [...PAYROLL_FOCUS_NAV_URLS, ...PAYROLL_FOCUS_EXTRA_PREFIXES].some(
    (prefix) =>
      prefix !== '/' && (path === prefix || path.startsWith(`${prefix}/`)),
  );
}

/** Le mode paie s'applique-t-il à cet utilisateur ? */
export function isPayrollFocusActive(
  user: PayrollFocusUser | null | undefined,
): boolean {
  if (!user) return false;
  if (isPlatformAdmin(user)) return false;
  const email = user.email?.trim().toLowerCase();
  if (email && PAYROLL_FOCUS_BYPASS_EMAILS.includes(email)) return false;
  return true;
}
```

- [ ] **Step 4 : Lancer le test pour vérifier qu'il passe**

```bash
cd frontend && npm test -- src/lib/payrollFocus.test.ts
```

Attendu : PASS, 11 tests.

- [ ] **Step 5 : Commit**

```bash
git add frontend/src/lib/payrollFocus.ts frontend/src/lib/payrollFocus.test.ts
git commit -m "feat(paie): liste blanche et prédicats du mode paie"
```

---

### Task 2 : Le filtrage par section

**Files:**
- Modify: `frontend/src/lib/payrollFocus.ts`
- Test: `frontend/src/lib/payrollFocus.test.ts`

**Interfaces:**
- Consumes: `isPayrollFocusAllowed`, `PAYROLL_FOCUS_NAV_URLS` (Task 1).
- Produces: `PayrollFocusSection = 'team' | 'gestion' | 'paie'` et `restrictToPayrollFocus<TItem extends { url: string }, TGroup extends { items: TItem[] }>(section, groups): TGroup[]`.

**Pourquoi par section et non par URL seule :** `/schedules` figure deux fois dans la sidebar — « Calendriers » dans la section Gestion et « Calendrier » dans le parcours paie. Un filtre par URL garderait les deux et laisserait la section Gestion vivante avec une entrée orpheline.

- [ ] **Step 1 : Écrire le test qui échoue**

Étendre l'import existant en tête de `frontend/src/lib/payrollFocus.test.ts` — ne pas ajouter
un second `import` depuis le même module, ESLint le refuse :

```ts
import {
  PAYROLL_FOCUS_NAV_URLS,
  isPayrollFocusActive,
  isPayrollFocusAllowed,
  restrictToPayrollFocus,
} from './payrollFocus';
```

Puis ajouter à la fin du fichier :

```ts
const teamGroups = [
  { items: [{ url: '/analytics' }] },
  {
    label: 'Effectifs',
    items: [
      { url: '/employees' },
      { url: '/recruitment' },
      { url: '/onboarding' },
      { url: '/employee-exits' },
      { url: '/trial-periods' },
      { url: '/teams' },
    ],
  },
  { label: 'Suivi documents', items: [{ url: '/documents' }, { url: '/residence-permits' }] },
];

const gestionGroups = [
  {
    items: [
      { url: '/analytics-gestion' },
      { url: '/badgeuse-rh' },
      { url: '/schedules' },
      { url: '/planning' },
      { url: '/users' },
    ],
  },
];

const paieGroups = [
  { items: [{ url: '/analytics-paie' }] },
  {
    workflow: true,
    items: [
      { url: '/schedules' },
      { url: '/leaves' },
      { url: '/suivi-ijss' },
      { url: '/suivi-temps-travail' },
      { url: '/suivi-contingent-hs' },
      { url: '/suivi-modulation' },
      { url: '/suivi-cet' },
      { url: '/expenses' },
      { url: '/saisies' },
      { url: '/salary-seizures' },
      { url: '/salary-advances' },
      { url: '/employee-loans' },
    ],
  },
  {
    label: 'Outils paie',
    items: [
      { url: '/simulation' },
      { url: '/rates' },
      { url: '/taux-pas' },
      { url: '/exports' },
      { url: '/payroll' },
    ],
  },
];

const urlsOf = (groups: { items: { url: string }[] }[]) =>
  groups.flatMap((g) => g.items.map((i) => i.url));

describe('restrictToPayrollFocus', () => {
  it('ne garde que Collaborateurs dans la section Effectifs', () => {
    const out = restrictToPayrollFocus('team', teamGroups);
    expect(urlsOf(out)).toEqual(['/employees']);
  });

  it('supprime entièrement la section Gestion', () => {
    expect(restrictToPayrollFocus('gestion', gestionGroups)).toEqual([]);
  });

  it('garde tout le parcours paie sauf Analytics Paie', () => {
    const out = restrictToPayrollFocus('paie', paieGroups);
    expect(urlsOf(out)).not.toContain('/analytics-paie');
    expect(urlsOf(out)).toHaveLength(17);
  });

  it('conserve les métadonnées de groupe', () => {
    const out = restrictToPayrollFocus('paie', paieGroups);
    expect(out.find((g) => g.label === 'Outils paie')).toBeDefined();
    expect(out.find((g) => (g as { workflow?: boolean }).workflow)).toBeDefined();
  });

  it('supprime les groupes devenus vides', () => {
    const out = restrictToPayrollFocus('paie', paieGroups);
    expect(out).toHaveLength(2);
  });

  it('ne mute pas les groupes reçus', () => {
    const before = urlsOf(paieGroups).length;
    restrictToPayrollFocus('paie', paieGroups);
    expect(urlsOf(paieGroups)).toHaveLength(before);
  });

  it('produit exactement les 19 URL du périmètre, toutes sections confondues', () => {
    const all = [
      '/',
      ...urlsOf(restrictToPayrollFocus('team', teamGroups)),
      ...urlsOf(restrictToPayrollFocus('gestion', gestionGroups)),
      ...urlsOf(restrictToPayrollFocus('paie', paieGroups)),
    ];
    expect(new Set(all)).toEqual(new Set(PAYROLL_FOCUS_NAV_URLS));
  });
});
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

```bash
cd frontend && npm test -- src/lib/payrollFocus.test.ts
```

Attendu : FAIL — `restrictToPayrollFocus is not a function`.

- [ ] **Step 3 : Écrire l'implémentation**

Ajouter à la fin de `frontend/src/lib/payrollFocus.ts` :

```ts
export type PayrollFocusSection = 'team' | 'gestion' | 'paie';

/**
 * Filtre une section de navigation. Le filtrage est par section et non par URL
 * seule : `/schedules` apparaît dans Gestion (« Calendriers ») et dans le
 * parcours paie (« Calendrier »), et seule la seconde doit survivre.
 */
export function restrictToPayrollFocus<
  TItem extends { url: string },
  TGroup extends { items: TItem[] },
>(section: PayrollFocusSection, groups: TGroup[]): TGroup[] {
  if (section === 'gestion') return [];
  const keep = (item: TItem) =>
    section === 'team' ? item.url === '/employees' : isPayrollFocusAllowed(item.url);
  return groups
    .map((group) => ({ ...group, items: group.items.filter(keep) }))
    .filter((group) => group.items.length > 0);
}
```

- [ ] **Step 4 : Lancer le test pour vérifier qu'il passe**

```bash
cd frontend && npm test -- src/lib/payrollFocus.test.ts
```

Attendu : PASS, 18 tests.

- [ ] **Step 5 : Commit**

```bash
git add frontend/src/lib/payrollFocus.ts frontend/src/lib/payrollFocus.test.ts
git commit -m "feat(paie): filtrage de la navigation par section"
```

---

### Task 3 : Retirer les alertes qui pointent vers un écran retiré

**Files:**
- Modify: `frontend/src/lib/rhPendingTasks.ts`
- Test: `frontend/src/lib/rhPendingTasks.test.ts`

**Interfaces:**
- Consumes: `isPayrollFocusAllowed` (Task 1).
- Produces: `filterTasksToPayrollFocus(items: RhPendingTaskItem[]): RhPendingTaskItem[]`.

Le filtrage porte sur `href` — la destination du clic — et non sur `sidebarPath`. C'est ce qui répond au défaut visé : une alerte ne doit jamais mener vers une page absente du menu.

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `frontend/src/lib/rhPendingTasks.test.ts` :

```ts
import { filterTasksToPayrollFocus } from './rhPendingTasks';
import type { RhPendingTaskItem } from './rhPendingTasks';
import { CalendarCheck } from 'lucide-react';

const task = (id: string, href: string): RhPendingTaskItem =>
  ({ id, label: id, count: 1, href, icon: CalendarCheck, hint: '' }) as RhPendingTaskItem;

describe('filterTasksToPayrollFocus', () => {
  it('garde les tâches dont la destination est dans le périmètre', () => {
    const kept = filterTasksToPayrollFocus([
      task('leaves', '/leaves'),
      task('expenses', '/expenses'),
      task('contracts', '/employees?alert=deadlines'),
      task('rates', '/rates'),
    ]);
    expect(kept.map((t) => t.id)).toEqual(['leaves', 'expenses', 'contracts', 'rates']);
  });

  it('retire les tâches menant vers un écran retiré', () => {
    const kept = filterTasksToPayrollFocus([
      task('medical', '/medical-follow-up'),
      task('residence', '/residence-permits'),
      task('reviews', '/annual-reviews?focus=upcoming'),
      task('recruitment', '/recruitment'),
      task('onboarding', '/onboarding'),
      task('company', '/company'),
    ]);
    expect(kept).toEqual([]);
  });

  it('ne modifie pas la liste reçue', () => {
    const input = [task('leaves', '/leaves'), task('medical', '/medical-follow-up')];
    filterTasksToPayrollFocus(input);
    expect(input).toHaveLength(2);
  });
});
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

```bash
cd frontend && npm test -- src/lib/rhPendingTasks.test.ts
```

Attendu : FAIL — `filterTasksToPayrollFocus is not a function`.

- [ ] **Step 3 : Écrire l'implémentation**

Dans `frontend/src/lib/rhPendingTasks.ts`, ajouter l'import en tête :

```ts
import { isPayrollFocusAllowed } from '@/lib/payrollFocus';
```

et la fonction après `sumRhPendingActions` :

```ts
/**
 * Mode paie : ne conserve que les alertes dont la destination reste
 * atteignable. Une alerte qui mène vers un écran retiré est incohérente, et une
 * alerte sur laquelle on ne peut pas agir est pire qu'une absence d'alerte.
 */
export function filterTasksToPayrollFocus(
  items: RhPendingTaskItem[],
): RhPendingTaskItem[] {
  return items.filter((item) => isPayrollFocusAllowed(item.href));
}
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

```bash
cd frontend && npm test -- src/lib/rhPendingTasks.test.ts
```

Attendu : PASS, y compris les tests préexistants du fichier.

- [ ] **Step 5 : Commit**

```bash
git add frontend/src/lib/rhPendingTasks.ts frontend/src/lib/rhPendingTasks.test.ts
git commit -m "feat(paie): retirer les alertes hors périmètre du mode paie"
```

---

### Task 4 : Câbler la navigation

**Files:**
- Modify: `frontend/src/components/ui/app-sidebar.tsx`
- Modify: `frontend/src/hooks/useRhPendingTasks.ts`

**Interfaces:**
- Consumes: `restrictToPayrollFocus`, `isPayrollFocusActive` (Tasks 1–2), `filterTasksToPayrollFocus` (Task 3).
- Produces: rien pour les tâches suivantes.

Aucun test unitaire possible : Vitest est en `environment: "node"` et n'inclut pas les `.tsx`. La logique filtrée est déjà couverte par les Tasks 1–3 ; cette tâche est du câblage, vérifié à l'écran.

- [ ] **Step 1 : Filtrer les alertes à la source du hook**

Dans `frontend/src/hooks/useRhPendingTasks.ts`, importer `filterTasksToPayrollFocus` et `isPayrollFocusActive`, récupérer l'utilisateur via `useAuth()`, et envelopper le retour de `buildRhPendingTasks` :

```ts
const items = buildRhPendingTasks(input);
const tasks = isPayrollFocusActive(user) ? filterTasksToPayrollFocus(items) : items;
```

Le reste du hook (`sumRhPendingActions`, `rhPendingTasksToSidebarCounts`) consomme `tasks`. Les pastilles de la sidebar et le panneau du tableau de bord se filtrent donc ensemble, sans autre modification.

- [ ] **Step 2 : Ajouter le filtre dans la sidebar**

Dans `frontend/src/components/ui/app-sidebar.tsx`, importer en tête :

```ts
import { isPayrollFocusActive, restrictToPayrollFocus } from "@/lib/payrollFocus";
```

Dans le corps de `AppSidebar()`, après `const { user } = useAuth();` (ligne ~739) :

```ts
const payrollFocus = isPayrollFocusActive(user);
```

Puis remplacer le `useMemo` existant de `rhGestionGroups` (ligne ~837) et ajouter ses deux voisins :

```ts
const rhTeamGroups = useMemo(
  () => (payrollFocus ? restrictToPayrollFocus('team', RH_TEAM_GROUPS) : RH_TEAM_GROUPS),
  [payrollFocus],
);

const rhGestionGroups = useMemo(() => {
  if (payrollFocus) return restrictToPayrollFocus('gestion', RH_GESTION_GROUPS);
  const base = RH_GESTION_GROUPS.map((g) => ({ ...g, items: [...g.items] }));
  if (!hasConsolidatedViews && base[0]) {
    const usersIdx = base[0].items.findIndex((i) => i.url === "/users");
    const idx = usersIdx >= 0 ? usersIdx : base[0].items.length;
    base[0].items.splice(idx, 0, monEntrepriseNav);
  }
  return base;
}, [payrollFocus, hasConsolidatedViews, monEntrepriseNav]);

const rhPaieGroups = useMemo(
  () => (payrollFocus ? restrictToPayrollFocus('paie', RH_PAIE_GROUPS) : RH_PAIE_GROUPS),
  [payrollFocus],
);
```

Le court-circuit de `rhGestionGroups` est volontaire : quand le mode est actif, la section disparaît et l'insertion de « Mon entreprise » n'a plus lieu d'être.

- [ ] **Step 3 : Remplacer les références aux constantes**

Dans le même fichier, remplacer chaque usage de `RH_TEAM_GROUPS` par `rhTeamGroups` et de `RH_PAIE_GROUPS` par `rhPaieGroups` **à l'intérieur du composant** (lignes ~853-878, ~1034, ~1092). Laisser intactes les définitions des constantes et les deux dérivations de module `rhTeamNavItems` / `rhPaieNavItems` (lignes 277-278), qui servent au préchargement et ne pilotent pas l'affichage.

Sites concernés dans le composant :
- `rhCollapsedNavItems` (~853-855)
- `teamSectionHasTasks`, `paieSectionHasTasks` (~860-863)
- `useState` initial de `teamOpen`, `paieOpen` (~866-878)
- `useEffect` d'ouverture automatique (~876-878) — ajouter `rhTeamGroups` et `rhPaieGroups` au tableau de dépendances
- Les props `groups={...}` des deux sections (~1034, ~1092)

- [ ] **Step 4 : Vérifier que rien n'est cassé**

```bash
cd frontend && npm run lint && npm test && npx tsc -p tsconfig.app.json --noEmit
```

Attendu : aucune erreur, tous les tests passent, `routes.snapshot.test.ts` inclus.

- [ ] **Step 5 : Vérifier à l'écran**

```bash
cd frontend && npm run dev
```

Avec un compte client : 19 entrées, sections Effectifs et Gestion absentes, aucune pastille sur un écran retiré. Avec un compte admin plateforme : 48 entrées. Replier la sidebar : mêmes entrées.

- [ ] **Step 6 : Commit**

```bash
git add frontend/src/components/ui/app-sidebar.tsx frontend/src/hooks/useRhPendingTasks.ts
git commit -m "feat(paie): appliquer le mode paie à la navigation et aux pastilles"
```

---

### Task 5 : Rendre les routes retirées réellement inaccessibles

**Files:**
- Modify: `frontend/src/App.tsx:110-116`

**Interfaces:**
- Consumes: `isPayrollFocusActive`, `isPayrollFocusAllowed` (Task 1).

Le garde se place à côté de celui de `isEmployeeOnlyPath`, déjà présent dans `ProtectedRoutes`, et suit exactement la même forme : une clause de retour anticipé avant le bloc `<Routes>`. **Aucun élément `<Route>` n'est ajouté ni retiré** — c'est ce qui garantit que `routes.snapshot.test.ts` reste vert.

- [ ] **Step 1 : Ajouter l'import**

Dans `frontend/src/App.tsx`, après la ligne 28 :

```ts
import { isPayrollFocusActive, isPayrollFocusAllowed } from '@/lib/payrollFocus';
```

- [ ] **Step 2 : Ajouter la clause de garde**

Juste après le bloc `isEmployeeOnlyPath` existant (ligne 116), avant `if (user.role === 'collaborateur')` :

```tsx
if (
  user.role !== 'collaborateur' &&
  !isCollaborateurRhView &&
  isPayrollFocusActive(user) &&
  !isPayrollFocusAllowed(location.pathname)
) {
  return <Navigate to="/" replace />;
}
```

L'ordre des conditions compte : les deux premières reprennent celles du garde voisin, pour ne toucher ni l'espace salarié ni la vue collaborateur d'un `collaborateur_rh`.

- [ ] **Step 3 : Vérifier que rien n'est cassé**

```bash
cd frontend && npm run lint && npm test && npx tsc -p tsconfig.app.json --noEmit
```

Attendu : aucune erreur. `src/app/routes.snapshot.test.ts` doit passer — s'il échoue, c'est qu'un `<Route>` a été touché : annuler et revoir l'étape 2.

- [ ] **Step 4 : Vérifier à l'écran**

Avec un compte client, saisir directement dans la barre d'adresse :

| Chemin | Attendu |
|---|---|
| `/cse` | redirection vers `/` |
| `/formation` | redirection vers `/` |
| `/residence-permits` | redirection vers `/` |
| `/employees/<id>` | la fiche salarié s'ouvre |
| `/payroll/<id>` | le détail de paie s'ouvre |
| `/payslips/<id>/edit` | l'édition de bulletin s'ouvre |
| `/exports` | la page Exports s'ouvre |

Avec un compte admin plateforme : `/cse` s'ouvre normalement.
Avec un compte salarié : espace collaborateur inchangé, aucune redirection parasite.

- [ ] **Step 5 : Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(paie): bloquer l'accès direct aux routes hors mode paie"
```

---

## Recette finale avant le 28/08

Sur l'environnement de test, après déploiement :

- [ ] Compte `gaelle.bouali` : 19 entrées, parcours complet jusqu'à la validation d'un bulletin Colorplast **et** la sortie de l'OD comptable depuis Exports.
- [ ] Compte `vanessa.amate` : 19 entrées, aucune alerte pointant vers un écran retiré.
- [ ] Compte `alexandreandre2004@gmail.com` : 48 entrées, navigation inchangée.
- [ ] `useCanLaunchPayroll` : le lancement reste bloqué tant que Calendrier, Congés ou Notes de frais ont des éléments en attente, et se débloque une fois les trois à zéro.
- [ ] Espace salarié et espace manager : inchangés.

**Prérequis non technique, bloquant :** Gaëlle Bouali est RH sur MAJI et Zone 404 uniquement. Sans Colorplast ajoutée à son compte de test, la séquence de vendredi ne peut pas se jouer, quel que soit le menu.
