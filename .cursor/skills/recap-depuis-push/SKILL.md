---
name: recap-depuis-push
description: >-
  Depuis le dernier push GitHub : liste fonctionnelle point par point de ce qui
  a été ajouté ou corrigé, audit complet de complétude (artefacts, branchements
  manquants, TODO), puis plan détaillé pour tout terminer et tout tester.
  À utiliser lorsque l'utilisateur demande /recap-depuis-push, un récap +
  vérification complète, ou attache explicitement ce skill.
---

# Récap, audit et plan — `/recap-depuis-push`

## Objectif

Trois livrables **dans l'ordre**, à partir du delta **depuis le dernier push GitHub** (branche courante) :

1. **Inventaire** — liste fonctionnelle, phrases courtes, non techniques.
2. **Audit de complétude** — vérifier que chaque point est **vraiment fini**, sans artefact ni oubli.
3. **Plan de finalisation** — plan exhaustif pour **terminer** et **tester** chaque implémentation.

**Ne pas s'arrêter** après la liste : enchaîner phases 2 et 3 sans demander confirmation.

---

## Quand utiliser

- **`/recap-depuis-push`**, récap depuis le dernier push, audit de complétude, plan pour finir et tester.

---

## Phase 0 — Collecte Git (obligatoire)

```bash
git fetch origin
git branch --show-current
git status -sb
```

Branche = `DEV`.

```bash
git rev-parse --verify origin/$DEV 2>/dev/null
git rev-list --left-right --count origin/$DEV...HEAD
git log --oneline origin/$DEV..HEAD
git diff --stat origin/$DEV
git diff origin/$DEV
git diff
git diff --cached
```

Si **`origin/$DEV` absent** : signaler et analyser tout le working tree + commits locaux.

Cartographier les zones touchées (modules backend, pages frontend, migrations, workflows CI, tests).

---

## Phase 1 — Inventaire fonctionnel

### Règles de rédaction

- **Français**, lignes `- ` uniquement.
- **Phrases courtes** (≤ ~12 mots), **langage RH / produit**, pas de jargon dev.
- Regrouper les micro-changements du même sujet en **une ligne**.
- Ne pas citer fichiers, tables, routes, classes.
- Du plus important au plus secondaire.

| Éviter | Préférer |
|--------|----------|
| migration SQL, router, endpoint | paramétrage, écran, export |
| module employee_loans | prêts aux salariés |
| refactor repository | (ne lister que si impact visible) |

**Cas vide** : une seule ligne « Rien de nouveau depuis le dernier push sur GitHub. »

---

## Phase 2 — Audit de complétude (très complet)

Pour **chaque point** de la phase 1, vérifier systématiquement. Ne pas se contenter de « le fichier existe ».

### 2.1 Checklist par fonctionnalité

| Critère | Vérifier |
|---------|----------|
| Métier | Comportement conforme à l'intention du diff |
| Backend | Handler, service, règles domaine, validation, erreurs 4xx/5xx |
| Persistance | Migration appliquée, schéma cohérent, pas de colonne morte |
| Câblage API | Route enregistrée dans `backend/app/api/router.py` ou router module |
| Frontend | Page/composant, route dans `App.tsx` / `lazyPages.ts`, menu si attendu |
| Client API | Hook ou appel dans `frontend/src/api/` / `hooks/` |
| Droits | Rôles, guards, accès inter-company |
| UX | Textes en français, états vide/chargement/erreur, toasts |
| Documents / exports | Génération PDF/Excel branchée et téléchargeable |
| Paie / exports | Impact bulletin, DSN, cumuls si le diff touche la paie |
| Notifications | Envoi mail/cron/workflow GitHub relié au code |
| Tests | pytest unit/integration existants et pertinents |
| CI | Workflow ou job cohérent avec le code ajouté |

### 2.2 Détection d'artefacts et oublis

Chercher dans **tout le périmètre du diff** :

```bash
# Depuis la racine du repo, sur les fichiers du diff
git diff --name-only origin/$DEV
```

Puis `Grep` / lecture ciblée sur :

- `TODO`, `FIXME`, `HACK`, `XXX`, `WIP`, `stub`, `placeholder`, `NotImplemented`, `pass  #`, `raise NotImplementedError`
- `console.log`, `debugger`, code commenté volumineux
- Fonctions vides, composants squelettes, retours `null` sans UI
- Routes backend **non montées** ; pages frontend **non routées**
- Migration SQL **sans** code applicatif (ou l'inverse)
- Module backend **sans** écran ni consommation API
- Écran **sans** hook API ou avec données mockées restantes
- Fichiers orphelins (créés mais jamais importés / référencés)
- Seeds ou config **non lues** par le code
- Workflow `.github/workflows/` **sans** endpoint/handler correspondant
- Tests absents sur logique métier non triviale
- Strings anglaises ou clés i18n manquantes sur l'UI
- Données runtime locales (`backend/app/runtime/`) commitées par erreur si hors scope

### 2.3 Exécution minimale

Lancer ce qui est pertinent pour le périmètre :

```bash
# Backend — depuis backend/
python -m pytest tests/ -m "not e2e" -v --tb=short

# Frontend — depuis frontend/
npm run lint
npm run build
```

Cibler pytest par module si le diff est localisé. Relancer après correctif.

Utiliser `ReadLints` sur les fichiers modifiés du diff.

Si serveur dev ou navigateur disponible : parcourir au moins le **happy path** de chaque feature nouvelle.

### 2.4 Statuts par point (phase 1)

Pour chaque ligne de l'inventaire :

| Statut | Signification |
|--------|----------------|
| **OK** | Implémenté, branché, testé ou vérifiable sans réserve |
| **PARTIEL** | Existe mais incomplet, fragile, UX/API incohérente |
| **MANQUANT** | Absent, non branché, ou non fonctionnel |
| **ARTEFACT** | Code mort, placeholder, branchement oublié, dette visible |

### 2.5 Format de réponse phase 2

Section **`## Audit`** — pour chaque point de la phase 1 :

```markdown
- [OK] Ajout de la gestion des prêts aux salariés
- [PARTIEL] Rappels par mail avant les échéances RH — cron présent, pas de test d'envoi
- [MANQUANT] Export des charges sociales — backend seul, écran absent
- [ARTEFACT] Médailles d'ancienneté — TODO sur la notification push
```

Phrases **courtes** après le statut. Mentionner l'écart concret, **sans** lister 20 fichiers (1–2 indices max si utile).

---

## Phase 3 — Plan de finalisation et tests complets

Construire un plan **exhaustif** pour amener **chaque point PARTIEL, MANQUANT ou ARTEFACT** à **OK**, puis tester **tout** l'inventaire (y compris les OK, en non-régression).

### 3.1 Structure du plan

Section **`## Plan`** avec blocs numérotés par **thème métier** (reprenant la phase 1).

Pour chaque thème :

**A. Travail restant** — tâches concrètes, ordonnées, finissables (verbe d'action + livrable).

**B. Definition of done** — critères objectifs « c'est fini quand… ».

**C. Matrice de tests** — scénarios numérotés `T01`, `T02`, … couvrant au minimum :

| Dimension | Exemples |
|-----------|----------|
| Happy path | parcours nominal bout en bout |
| Rôles | admin RH, manager, employé, accès refusé |
| Erreurs | validation, 403/404, réseau, données invalides |
| États UI | vide, chargement, erreur, succès |
| Données limites | dates, montants 0, listes vides |
| Régression | flux adjacents impactés par le diff |
| Backend | pytest ciblé sur règles métier |
| Export / document | fichier généré, contenu plausible |

Viser **≥ 8 scénarios** par feature simple, **≥ 15** par feature riche (paie, prêts, exports).

**D. Ordre d'exécution** — séquence recommandée (migrations → backend → frontend → tests → recette manuelle).

**E. Commandes de validation finale** — liste exacte à rejouer avant de considérer le thème clos.

### 3.2 Priorisation globale

En tête du plan, un bloc **`### Priorité`** :

1. **Bloquant** — MANQUANT sur parcours principal ou sécurité
2. **Important** — PARTIEL visible par l'utilisateur RH
3. **Artefacts / polish** — TODO, tests manquants, finitions UX
4. **Non-régression** — re-test des points OK

### 3.3 Estimation d'effort (optionnel, une ligne par thème)

`S` (< 1 h), `M` (1–4 h), `L` (> 4 h) — sans justifier longuement.

---

## Format de réponse global (obligatoire)

Trois sections dans cet ordre, **en français** :

```markdown
## Inventaire
- …
- …

## Audit
- [OK] …
- [PARTIEL] …

## Plan

### Priorité
1. …

### 1. [Nom du thème]
**A. Travail restant**
1. …
**B. Definition of done**
- …
**C. Tests**
- T01 — …
- T02 — …
**D. Ordre d'exécution**
1. …
**E. Validation**
- `python -m pytest tests/unit/…`
- …

### 2. [Autre thème]
…
```

---

## Règles agent

- **Exécuter** les commandes Git, pytest, lint, build — ne pas simuler l'audit.
- **Ne pas inventer** de fonctionnalités absentes du diff.
- **Ne pas abandonner** au premier échec de test : noter, proposer correctif dans le plan.
- **Corriger** uniquement si l'utilisateur le demande explicitement ; ce skill **diagnostique et planifie** par défaut (contrairement à **check-feature** qui corrige).
- Pour l'écriture de tests automatisés → renvoyer vers le skill **test** (`.cursor/skills/test/SKILL.md`).
- Pour une recette exécutée scénario par scénario → renvoyer vers **test-complet** une fois le plan validé.

---

## Anti-patterns

- S'arrêter après l'inventaire sans audit ni plan.
- Audit superficiel (« fichier présent » sans câblage).
- Plan vague (« ajouter des tests » sans scénarios numérotés).
- Jargon technique dans l'inventaire.
- Oublier migrations, menus, cron, exports, droits.

---

## Exemple d'invocation

> `/recap-depuis-push` — liste ce qu'on a fait, vérifie que c'est complet, et fais le plan pour finir et tester.

L'agent enchaîne les trois phases sur le diff réel depuis `origin/$DEV`.
