---
name: resume
description: >-
  Résume en une seule phrase courte ce qui vient d'être implémenté, corrigé ou
  amélioré (session courante ou changements Git locaux). À utiliser lorsque
  l'utilisateur demande /resume, une phrase récap, un résumé en une ligne, ou
  attache explicitement ce skill.
---

# Résumé en une phrase — `/resume`

## Objectif

**Une seule livrable** : **une phrase courte** qui dit ce qui vient d'être fait — implémenté, corrigé ou amélioré.

Pas de liste, pas d'audit, pas de plan, pas d'intro.

---

## Quand utiliser

- **`/resume`**, « résume en une phrase », « une ligne pour dire ce qu'on vient de faire ».
- Après une implémentation, correction ou amélioration, quand il faut un libellé court (commit, PR, changelog, message Slack).

Pour une **liste** de plusieurs points → skill **recap-event**.
Pour inventaire + audit + plan → skill **recap-depuis-push**.

---

## Workflow

### 1. Identifier le périmètre

Priorité des sources :

1. **Conversation courante** — ce qui vient d'être fait ou demandé dans le fil.
2. **Working tree + commits locaux non poussés** — si le fil est ambigu ou vide.

```bash
git fetch origin 2>/dev/null || true
git branch --show-current
git status -sb
git diff --stat
git diff --cached --stat
git log --oneline -5
```

Si plusieurs sujets distincts dans le diff, **fusionner en une seule phrase** en gardant le sujet principal ; mentionner le secondaire seulement s'il est indissociable.

### 2. Choisir le verbe (obligatoire)

| Type | Verbe en tête de phrase | Quand |
|------|-------------------------|-------|
| **Implémenté** | **Ajout** / **Mise en place** | nouvelle feature, écran, export, flux |
| **Corrigé** | **Correction** | bug, régression, mauvais calcul, affichage erroné |
| **Amélioré** | **Amélioration** | UX, perf, robustesse, textes, sans nouveau parcours |

Un seul verbe par réponse. Ne pas mélanger « Ajout » et « Correction » dans la même phrase.

### 3. Rédiger

- **Français**, langage **RH / produit** — pas de jargon dev.
- **Une phrase**, sujet + verbe + complément (≤ ~15 mots).
- Ne pas citer fichiers, dossiers, tables, routes, classes, librairies.
- Ne pas inventer ce qui n'est pas dans la conversation ni le diff.

| Éviter | Préférer |
|--------|----------|
| endpoint, composant React, migration | écran, export, bulletin, notification |
| fix du hook useNotifications | alertes document sur le tableau de bord |

---

## Format de réponse (obligatoire)

Répondre **en français**. **Exactement une phrase**, sans tiret, sans titre, sans guillemets, sans point final optionnel (le point final est accepté).

Exemples :

```text
Correction de l'affichage du net à payer sur le bulletin de paie.
Ajout des alertes document sur le tableau de bord RH.
Amélioration des notifications lors de l'upload d'un document employé.
```

**Cas vide** (rien de identifiable) :

```text
Rien de nouveau à résumer pour le moment.
```

---

## Règles agent

- **Lire** le diff ou la conversation réelle — ne pas inventer.
- **Ne pas corriger** le code : ce skill **résume** uniquement.
- **Ne pas** enchaîner avec une liste, un audit ou un plan.
- **Une phrase seulement**, même si le diff touche plusieurs fichiers.

---

## Anti-patterns

- Plusieurs phrases ou une liste à puces.
- Copier un message de commit technique tel quel.
- Intro du type « Voici le résumé : » ou conclusion.
- Mentionner « backend », « frontend », « API » sauf si indispensable pour le sens.

---

## Exemple d'invocation

> `/resume` — une phrase pour dire ce qu'on vient de faire.

L'agent produit **une seule phrase** fonctionnelle.
