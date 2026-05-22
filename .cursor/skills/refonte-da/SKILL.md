---
name: refonte-da
description: >-
  Refonte complète de la direction artistique (couleurs, typo, rayons, ombres,
  dégradés, motion) du frontend sans modifier l’UX, la structure des composants
  ni les parcours. S’appuie sur un brief DA fourni par l’utilisateur, couvre
  tokens, primitives UI et couleurs en dur, puis exécute une phase de
  vérification de cohérence. À utiliser lorsque l’utilisateur tape /refonte-da,
  demande de refaire toute la DA du site, une rebrand visuelle globale, ou
  attache explicitement ce skill.
---

# Refonte DA — direction artistique globale

## Objectif

Appliquer une **nouvelle direction artistique** sur **tout** le frontend : uniquement l’**apparence** (tokens, styles, classes visuelles). Le produit garde la **même UX** (disposition, flux, hiérarchie d’information, libellés, interactions).

## Quand utiliser ce skill

- `/refonte-da` ou demande de **refaire toute la DA** du site.
- Rebrand visuel **global** avec brief DA (voir [da-prompt-template.md](da-prompt-template.md)).

**Ne pas confondre** avec `frontend-design` : ce skill ne polît pas une page au feeling ; il **remplace systématiquement** l’identité visuelle partout.

---

## Périmètre strict

### Autorisé (DA uniquement)

| Zone | Fichiers typiques (EYWAI) |
|------|---------------------------|
| Tokens CSS | `frontend/src/index.css` (`:root`, `.dark`) |
| Mapping Tailwind | `frontend/tailwind.config.ts` (couleurs, radius, animations liées au thème) |
| Primitives shadcn | `frontend/src/components/ui/*.tsx` (classes Tailwind visuelles, variants `cva`) |
| Classes utilitaires globales | `frontend/src/index.css` (`.hr-card`, `.kpi-card`, badges…) |
| Couleurs en dur | Tous `frontend/src/**/*.{tsx,css}` : `bg-blue-500`, `#hex`, `hsl(…)` hors tokens |
| Graphiques | `chart.tsx`, couleurs de séries dans pages/composants analytics |
| Assets visuels | favicon, logos statiques si le brief le demande |

### Interdit (ne pas toucher)

- **Structure DOM** : pas de réorganisation de sections, grilles, ordre des blocs.
- **Composants métier** : pas de fusion/split de composants, pas de nouveaux props fonctionnels.
- **UX / parcours** : pas de nouvelles étapes, suppression d’écrans, déplacement de navigation.
- **Copie & i18n** : pas de changement de textes (sauf si l’utilisateur le demande à part).
- **Logique** : hooks, appels API, états, validations, permissions.
- **Accessibilité structurelle** : ne pas retirer labels, rôles ARIA, focus trap ; **ajuster** contrastes et `:focus-visible` dans le cadre DA.

Si un fichier mélange DA et UX, **ne modifier que les lignes visuelles** (classes, `style`, variables CSS).

---

## Entrée obligatoire : brief DA

Avant toute modification, l’utilisateur doit fournir un brief (message ou fichier rempli). **Modèle** : [da-prompt-template.md](da-prompt-template.md).

Sans brief exploitable (palette, typo, radius, ton clair/sombre), **demander** de compléter le template — ne pas inventer une charte complète sauf demande explicite.

---

## Workflow (ordre obligatoire)

> Phases : 0 cadrage → 1 tokens → 2 primitives ui → 3 sweep couleurs → 4 graphiques → **5 cohérence inter-composants** → 6 vérif finale → 7 livrable.

### Phase 0 — Cadrage

1. Lire le brief DA et le résumer en 5–10 lignes (palette, typo, radius, ombres, motion).
2. Lire `frontend/src/index.css` et `frontend/tailwind.config.ts`.
3. Noter les écarts actuels vs brief (ex. vert accent → terracotta).

### Phase 1 — Tokens (source de vérité)

1. Mettre à jour **toutes** les variables dans `:root` et `.dark` (`index.css`) :
   - sémantiques shadcn : `background`, `foreground`, `card`, `popover`, `primary`, `secondary`, `muted`, `accent`, `destructive`, `border`, `input`, `ring`
   - statuts : `success`, `warning`, `danger`
   - sidebar : `sidebar-*`
   - extensions projet : `primary-glow`, `accent-glow`, `--gradient-*`, `--shadow-*`, `--transition-*`, `--radius`
2. **Règle EYWAI** : couleurs en **HSL** sans wrapper `hsl()` dans les variables (cf. commentaire en tête de `index.css`).
3. Aligner `tailwind.config.ts` si de **nouveaux** tokens sont ajoutés au brief.
4. Mettre à jour les utilitaires globaux dans `index.css` (`.hr-gradient`, `.status-badge-*`, etc.) pour qu’ils **consomment les tokens**, pas des couleurs Tailwind fixes (`green-500`, etc.).

### Phase 2 — Primitives UI (`components/ui`)

Parcourir **chaque** fichier sous `frontend/src/components/ui/` :

- `button`, `badge`, `card`, `input`, `select`, `tabs`, `table`, `dialog`, `sheet`, `sidebar`, `toast`, `alert`, `chart`, `status-badge`, sidebars (`app-sidebar`, `employee-sidebar`), etc.
- Remplacer couleurs/ombres/radius **en dur** par tokens (`bg-primary`, `text-muted-foreground`, `border-border`, `shadow-*` du thème).
- **Ne pas** changer les APIs (`variant`, `size`, structure Radix).

### Phase 3 — Sweep applicatif (couleurs en dur)

Recherche systématique dans `frontend/src` :

```bash
# Classes Tailwind palette nommée (à migrer vers tokens)
rg -n '(from-|to-|bg-|text-|border-|ring-|fill-|stroke-)(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-' frontend/src

# Hex / rgb inline
rg -n '#[0-9a-fA-F]{3,8}|rgb\(|rgba\(' frontend/src
```

Pour chaque occurrence :

- Mapper vers le token sémantique le plus proche (`primary`, `success`, `warning`, `danger`, `muted`, `accent`…).
- **Ne pas** déplacer de blocs JSX ; uniquement remplacer les classes/styles visuels.
- Pages à fort volume (priorité haute) : `Dashboard`, `Analytics`, `EmployeeDetail`, super-admin, `Employees`, paie/simulation — mais **tout** le dossier `src` doit finir à zéro occurrence non justifiée.

Documenter dans la synthèse le nombre de fichiers touchés et toute **exception** volontaire (ex. couleur de marque client uploadée).

### Phase 4 — Graphiques & données visuelles

- `components/ui/chart.tsx` : couleurs de grille, tooltip, légende → tokens.
- Composants `*Chart*`, `chart-container`, pages `Analytics` / `Dashboard` : séries avec `hsl(var(--primary))` ou palette dérivée du brief (max 5–6 teintes harmonisées, pas arc-en-ciel par défaut).

### Phase 5 — Cohérence inter-composants (obligatoire)

Objectif : **deux éléments qui font la même chose se ressemblent partout**. C’est ici que la refonte cesse d’être un patchwork.

#### 5.1 — Inventaire des familles d’éléments

Construire mentalement (ou en notes courtes) la liste des **familles fonctionnelles** présentes dans l’app, et vérifier qu’une famille = **un seul style** :

| Famille | Doit être identique partout |
|---------|------------------------------|
| Boutons primaires (CTA principal) | même couleur, radius, hauteur, typo, ombre, hover, focus |
| Boutons secondaires / outline | idem |
| Boutons destructifs | idem (et seul style « rouge » autorisé) |
| Boutons icône seul | même taille, même hit area |
| Liens cliquables | même couleur + hover (souligné/non), tous les écrans |
| Inputs / selects / textarea | même hauteur, bordure, focus ring, padding, état erreur |
| Champs en erreur | même bordure, même couleur d’aide |
| Badges de statut | même mapping sémantique : succès = vert thème, warning = ambre, danger = rouge thème — jamais `green-500` à un endroit et `success` ailleurs |
| Cards / panneaux | même fond, bordure, radius, ombre, espacement intérieur |
| Tableaux | même header, lignes zébrées ou non, hover row, pagination |
| Modales / dialogs / sheets | même padding, header, footer d’actions (ordre boutons : annuler à gauche / valider à droite, ou choix unique appliqué partout) |
| Toasts / alertes | même structure, même couleur par sévérité |
| Tabs / sous-navigation | même indicateur actif (couleur, soulignement, fond) |
| Avatars, chips, KPI cards | mêmes tailles/variantes |
| Sidebar / topbar | item actif, hover, focus identiques sur sidebar admin / employé / super-admin |
| Pages d’erreur / vide / loading | même illustration ou pattern, même copie tonale |

#### 5.2 — Sweep de cohérence

Pour chaque famille, faire une recherche transverse et **uniformiser** :

```bash
# Boutons définis ou ré-stylés ailleurs que via la primitive ui/button
rg -n '<button[^>]*className=' frontend/src
rg -n 'className="[^"]*(rounded|h-(8|9|10|11|12)|px-(3|4|5|6))[^"]*"[^>]*>' frontend/src/pages frontend/src/components --glob '!**/ui/**'

# Inputs faits main qui contournent ui/input
rg -n '<input[^>]*className=' frontend/src --glob '!**/ui/**'

# Status / badges artisanaux
rg -n 'rounded-full[^"]*(bg-|text-)' frontend/src
```

Règle : si un écran ré-implémente un bouton, un badge ou un input à la main, **le remplacer par la primitive** `components/ui/*` (variant adapté). On uniformise le rendu via le design system, pas avec des classes parallèles.

#### 5.3 — Variants : peu, mais clairs

- Compter les variants effectivement utilisés par primitive (ex. `Button`: `default | secondary | outline | ghost | destructive | link`). Si une page utilise un 7e style « custom », le ramener vers un variant existant ou ajouter **un seul** variant nommé au design system.
- Pas de tailles aléatoires : `Button` doit avoir un nombre fini de hauteurs (`sm | default | lg | icon`). Les `h-9`/`h-11` random dans des pages sont à supprimer.

#### 5.4 — Gabarit de page

Vérifier qu’un type de page a **toujours** le même gabarit :

- titre + breadcrumb + actions à droite → même hauteur et alignement
- bandeau KPI → même nombre de colonnes responsive et même card
- listes / tableaux → mêmes filtres en tête, mêmes pagination/footers
- pages détail employé / formation / annual review → mêmes onglets visuellement

Pas de réorganisation de contenu — juste **harmonisation** des paddings/headers/bandeaux entre pages sœurs.

#### 5.5 — Mode sombre cohérent

- Aucune surface en `#000` pur si le brief dit « pas de noir pur ».
- Bordures visibles en dark sur **toutes** les cards, pas seulement certaines.
- Primary lisible sur fond dark partout (mêmes paires de couleurs).

### Phase 6 — Vérification finale

Exécuter la checklist complète : [verification.md](verification.md).

Minimum avant clôture :

- `npm run lint` dans `frontend/` (corriger erreurs introduites).
- Re-scan `rg` : **aucune** classe `*-500` / `blue-600` etc. restante sauf exceptions documentées.
- Re-scan cohérence (5.2) : zéro `<button>` ou `<input>` natif stylé hors primitive sans justification.
- Parcours visuel comparatif : ouvrir **deux** pages différentes côte à côte (ex. `Employees` et `Recruitment`) et vérifier que **boutons, cards, tableaux, modales** sont visuellement identiques pour la même fonction.
- Mode sombre si activé : même check.

### Phase 7 — Livrable utilisateur (français)

1. Résumé du brief appliqué.
2. Fichiers clés modifiés (tokens, ui, top pages).
3. Résultat de la checklist (cochée / points ouverts).
4. Exceptions connues et prochaines étapes si quelque chose reste hors périmètre.

---

## Principes DA (pendant l’implémentation)

- **Une source de vérité** : `index.css` d’abord ; le reste consomme les tokens.
- **Cohérence clair/sombre** : chaque token `:root` a son pendant `.dark`.
- **Peu d’accents** : primary + accent + sémantiques ; éviter les dégradés « tech » non demandés dans le brief.
- **Pas de look IA générique** : s’aligner sur le brief, pas sur violet/bleu template (voir skill `frontend-design` pour signaux à éviter).
- **Contrastes** : texte et contrôles lisibles (viser WCAG AA sur paires critiques).

---

## Découpage des commits (si /push ou commit demandé)

Commits séparés recommandés :

1. `style(da): tokens et utilitaires globaux`
2. `style(da): primitives ui`
3. `style(da): sweep pages et composants métier`

Un seul commit acceptable si la session est petite et homogène.

---

## Anti-patterns

- Refactor UX « tant qu’on y est ».
- Laisser des `bg-green-500` / `#3b82f6` après le sweep.
- Modifier `main.tsx`, routes, ou logique auth pour la DA.
- Inventer une charte sans brief utilisateur.
- Clôturer sans passer [verification.md](verification.md).

---

## Ressources

- [da-prompt-template.md](da-prompt-template.md) — prompt à remplir par l’utilisateur.
- [verification.md](verification.md) — checklist finale obligatoire.
