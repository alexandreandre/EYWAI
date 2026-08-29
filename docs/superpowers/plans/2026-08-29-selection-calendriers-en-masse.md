# Sélection en masse des calendriers — plan d'implémentation

Spec : `docs/superpowers/specs/2026-08-29-selection-calendriers-en-masse-design.md`.
Exécution inline (recâblage UI couplé sur une page) ; validation par
eslint + `npx vite build` + `npx vitest run` + vérification visuelle HMR.

## Tâche 1 — Chip filtre « À saisir (n) » (CalendarFiltersBar)
- Retirer `<ASaisirActionsMenu>` et ses props (`aSaisirRows`,
  `allASaisirSelected`, `onSelectSubset`, `onFillASaisirWithAi`).
- Ajouter prop `aSaisirCount: number` ; rendre un `Button` toggle à sa place :
  actif quand `saisieFilter === 'a_saisir'` (variant default), sinon outline ;
  clic → `onSaisieFilterChange(actif ? 'all' : 'a_saisir')`.

## Tâche 2 — Sélection dans la vue Planning (TeamPlanningView)
- Props : `selectedIds: Set<string>`, `onToggleSelect(id)`,
  `onToggleSelectAll(ids: string[])` (signatures identiques à
  CalendarEmployeeTable).
- En-tête « Collaborateur » : Checkbox tout-cocher (état checked si toutes les
  lignes affichées sont sélectionnées) + libellé.
- Cellule collaborateur : Checkbox avant le nom ; `onClick` avec
  `stopPropagation` pour ne pas ouvrir le drawer ; le bouton nom inchangé.

## Tâche 3 — IA dans la barre d'actions (CalendarBulkActionsBar)
- Prop `onFillWithAi: (ids: string[]) => void` ; bouton « Remplir par l'IA
  (n) » avec icône Sparkles, placé avant Export CSV.

## Tâche 4 — Recâblage Schedules.tsx
- `CalendarFiltersBar` : nouvelle interface (`aSaisirCount={aSaisirRows.length}`).
- `TeamPlanningView` : passer `selectedIds`/`onToggleSelect`/`onToggleSelectAll`.
- `CalendarBulkActionsBar` : `onFillWithAi={(ids) => openAssistedFillForSelection(ids)}`.
- Bouton d'en-tête IA : si `selectedIds.size > 0` → cible la sélection, sinon
  roster complet (renommer les callbacks pour la clarté).
- Supprimer l'import + `git rm` de `ASaisirActionsMenu.tsx` ; retirer
  `selectSubsetToFill`/`allASaisirSelected` devenus morts.

## Tâche 5 — Vérification
- eslint sur fichiers touchés, `npx vitest run`, `npx vite build`.
- Vérif visuelle locale (HMR) : chip filtre, cocher en Planning, barre
  d'actions avec IA, bouton haut avec/sans sélection.
- Commit unique, push, déploiement env de test.
