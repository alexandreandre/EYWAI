---
name: recap-event
description: >-
  Produit une liste fonctionnelle point par point de ce qui a changé depuis le
  dernier push GitHub sur la branche courante — une phrase courte par ligne,
  sans audit ni plan de correction. À utiliser lorsque l'utilisateur demande
  /recap-event, un inventaire depuis le push, un récap événement, ou attache
  explicitement ce skill.
---

# Inventaire depuis le push — `/recap-event`

## Objectif

Une **seule** livrable : une liste plate de ce qui a bougé **depuis le dernier push GitHub** (branche courante).

Phrases **courtes**, **fonctionnelles**, **non techniques**. Une ligne = un point.

**Ne pas** enchaîner avec un audit, des statuts OK/PARTIEL, ni un plan de correction — pour cela, utiliser le skill **recap-depuis-push**.

---

## Quand utiliser

- **`/recap-event`**, inventaire depuis le push, récap événement, « qu'est-ce qu'on a fait » en simple.
- Quand l'utilisateur veut **uniquement la liste**, pas la vérification de complétude.

---

## Workflow

### 1. Mettre GitHub à jour

```bash
git fetch origin
git branch --show-current
git status -sb
```

### 2. Repérer la référence « dernier push »

Branche = `DEV` (branche courante).

```bash
git rev-parse --verify origin/$DEV 2>/dev/null
git rev-list --left-right --count origin/$DEV...HEAD
git log --oneline origin/$DEV..HEAD
git diff --stat origin/$DEV
git diff origin/$DEV
```

Inclure aussi le **working tree** non commité (`git diff`, `git diff --cached`) s'il existe.

Si **`origin/$DEV` n'existe pas** : comparer au dernier commit connu sur `origin` pour cette branche, ou indiquer qu'aucun push antérieur n'est trouvé et décrire **tout** le working tree + commits locaux.

### 3. Analyser les changements

Lire commits, diffs et noms de fichiers pour **comprendre l'intention métier**.

Regrouper les petits changements liés en **un seul point**.

**Traduire en langage RH / produit**, pas en langage dev :

| Éviter | Préférer |
|--------|----------|
| migration SQL, router, endpoint | paramétrage, écran, export |
| refactor repository | amélioration interne (ne pas lister sauf impact visible) |
| module employee_loans | prêts aux salariés |

Ne pas citer fichiers, dossiers, tables, classes, routes, librairies.

### 4. Cas particuliers

- **Rien depuis le dernier push** (working tree propre + compteur droit = 0) → une phrase : « Rien de nouveau depuis le dernier push sur GitHub. »
- **Seulement des commits non poussés** → les lister.
- **Seulement des modifs non commitées** → les lister quand même.
- **Les deux** → une seule liste fusionnée, sans distinguer commit / non commité.

---

## Format de réponse (obligatoire)

Répondre **en français**. **Uniquement** des lignes commençant par `- `.

Règles :

- **Une phrase courte par point** (sujet + verbe, ≤ ~12 mots si possible).
- **Fonctionnel** : ce que l'utilisateur RH ou le salarié gagne / voit / peut faire.
- **Pas de titres**, pas de tableaux, pas de hash de commit, pas de stats Git.
- **Pas de jargon technique**.
- **Pas de section Audit ni Plan** — inventaire seul.
- **Pas de regroupement par dossier** — liste plate, du plus important au plus secondaire.
- Regrouper les micro-fixes du même écran en **une ligne**.

Exemple :

```markdown
- Ajout de la gestion des prêts aux salariés
- Génération automatique du contrat de prêt
- Rappels par mail avant les échéances RH
- Médailles d'ancienneté visibles sur la fiche employé
- Correction de l'affichage du net à payer sur le bulletin
- Export des charges sociales au format attendu par l'organisme
```

---

## Règles agent

- **Exécuter** les commandes Git et lire le diff réel — ne pas inventer.
- **Ne pas inventer** de fonctionnalités absentes du diff.
- **Ne pas corriger** le code : ce skill **liste** uniquement.
- Pour audit + plan de finalisation → skill **recap-depuis-push**.
- Pour vérifier qu'une feature fonctionne → skill **check-feature**.

---

## Anti-patterns

- Lister fichier par fichier ou commit par commit.
- Copier les messages de commit tels quels s'ils sont techniques.
- Ajouter une intro longue, une conclusion, un audit ou un plan.
- Mentionner « backend », « frontend », « API » sauf si indispensable pour le sens.

---

## Exemple d'invocation

> `/recap-event` — dis-moi ce qu'on a fait depuis le dernier push, en simple.

L'agent exécute le workflow, lit le diff réel, et renvoie **uniquement** la liste.
