# Guide du dossier `.claude/`

Ce dossier contient la **configuration Claude Code** du dépôt : **commandes** (fichiers décrivant des workflows slash), **règles** (conventions `.mdc` alignées sur celles de Cursor pour le même code) et **skills** Claude spécifiques.

Il complète [`AGENTS.md`](../AGENTS.md), [`CONTRIBUTING.md`](../CONTRIBUTING.md), [`GUIDE-DEV.md`](../GUIDE-DEV.md) et les README `backend/` / `frontend/`.

Pour l’équipe qui utilise **Cursor** en parallèle : règles équivalentes sous [`.cursor/rules/`](../.cursor/rules/) ; skills et commandes Cursor sous [`.cursor/skills/`](../.cursor/skills/) (voir [`.cursor/README.md`](../.cursor/README.md)).

---

## Structure du dépôt

```
.claude/
├── README.md              ← ce guide
├── rules/
│   ├── backend.mdc        ← conventions Python / FastAPI (`backend/`)
│   └── frontend.mdc       ← conventions React / Vite (`frontend/`)
├── commands/
│   ├── commit.md
│   ├── debug-local.md
│   ├── debug-prod.md
│   ├── merge-dev-to-main.md
│   ├── security-check.md
│   └── update.md
└── skills/
    ├── backtest-paie-auto/
    ├── elsa/
    ├── fix-supabase/
    └── questions-elsa/
```

---

## Fichiers `rules/*.mdc`

Même contenu que **`.cursor/rules/`** pour `backend.mdc` et `frontend.mdc` : à modifier **en paire** si vous changez les conventions (voir tâche `/update` du projet).

| Fichier | Rôle |
|---------|------|
| `backend.mdc` | Point d’entrée `app.main:app`, couches d’import, logging, portée des diffs, français côté utilisateur, politique DB / tests CI. |
| `frontend.mdc` | Stack React / Vite / TS, UI Radix/shadcn, imports, lint, textes UI en français. |

Les règles Cursor additionnelles `database.mdc` et `product-context.mdc` (alwaysApply) n’ont pas de doublon sous `.claude/rules/` : elles restent côté Cursor.

---

## Fichiers `commands/*.md`

Procédures détaillées pour Claude Code (debug, merge, sécurité, synchronisation doc, etc.). Les noms correspondent aux **commandes slash** configurées côté Claude Code pointant vers ces fichiers.

| Commande (fichier) | Usage typique |
|-------------------|----------------|
| `commit.md` | Aide à la préparation de commits / messages. |
| `debug-local.md` / `debug-prod.md` | Diagnostic environnement local ou production. |
| `merge-dev-to-main.md` | Intégration branche perso → `main`. |
| `security-check.md` | Revue sécurité ciblée. |
| `update.md` | Actualiser doc, navigation, smoke tests et cohérence repo. |

---

## Dossier `skills/`

Skills Claude Code spécifiques au dépôt (en complément des skills Cursor).

| Skill | Usage |
|-------|--------|
| `backtest-paie-auto/` | Backtest paie autonome de bout en bout pour une entreprise. |
| `elsa/` | Retours paie terrain (Elsa). |
| `fix-supabase/` | Répare le MCP Supabase Claude Code (`/fix-supabase` + script `.sh`). |
| `questions-elsa/` | Cherche les réponses déjà présentes aux questions en suspens Elsa. |

---

**Maintenance** : après ajout ou suppression d’un fichier sous `.claude/commands/`, `.claude/rules/` ou `.claude/skills/`, mettre à jour la section **Structure** de ce README.
