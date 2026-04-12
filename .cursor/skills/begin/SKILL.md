---
name: begin
description: >-
  Démarre une session Git sur la branche personnelle du dépôt (dev-mathieu,
  dev-jose, dev-alex), vérifie la branche courante, demande confirmation si
  des modifications locales sont en cours avant fetch/merge, synchronise
  cette branche avec origin/main sans basculer sur main, et affiche un
  mini-bilan utile. À utiliser lorsque l’utilisateur demande de commencer une
  session de travail sur sa branche dev-* ou attache explicitement ce skill.
---

# Begin — session de travail sur branche dev-*

## Objectif

Aider les développeurs à **démarrer une session** : être sur **la bonne branche**, **récupérer les derniers changements de `main`** dans **leur** branche, **sans jamais checkout `main`** ni modifier l’état de la branche locale `main` (on ne fait que `fetch` + intégration sur la branche courante).

## Quand utiliser ce skill

- L’utilisateur demande explicitement de **préparer / démarrer une session** (ou équivalent) sur `dev-mathieu`, `dev-jose` ou `dev-alex`, ou attache ce fichier.

## Branches autorisées

Noms **exacts** attendus (adapter si le dépôt ajoute d’autres dev-* en concertation) :

- `dev-mathieu`
- `dev-jose`
- `dev-alex`

Si le projet étend la liste, l’agent peut appliquer la **même procédure** pour toute branche `dev-*` documentée dans le dépôt (ex. `guidebranche.md`).

---

## Workflow (à exécuter dans l’ordre)

### 1. Contexte dépôt

- Vérifier qu’on est à la **racine du dépôt Git** (ou un sous-dossier du même repo) via `git rev-parse --show-toplevel` si besoin.

### 2. Vérifier la branche courante

Exécuter :

```bash
git branch --show-current
```

- Si la branche **n’est pas** une des branches autorisées ci-dessus :
  - **Ne pas** merger/rebaser tant que l’utilisateur n’est pas sur la bonne branche.
  - Indiquer clairement la branche actuelle et la commande à utiliser, par ex. :  
    `git checkout dev-alex`  
  - S’arrêter ici sauf si l’utilisateur demande explicitement une autre branche documentée.

### 3. État du working tree (obligatoire avant toute intégration)

Exécuter :

```bash
git status -sb
```

- **Arbre de travail propre** (aucune modification non commitée, staging vide pour les changements en cours) : enchaîner directement avec l’étape 4.
- **Modifications en cours** (fichiers modifiés, ajoutés, supprimés non commités, conflits en cours, etc.) :
  1. **Ne pas** exécuter l’étape 4 (`fetch` / `merge` / `rebase`) tant que l’utilisateur n’a pas répondu clairement.
  2. **Demander explicitement** à l’utilisateur s’il souhaite poursuivre malgré les changements locaux, en rappelant le risque (conflits, état pénible, pertes si mal géré).
  3. Proposer des options courtes, par exemple :
     - **Annuler pour l’instant** : committer ou ranger le travail, puis relancer `/begin`.
     - **Continuer après stash** : si l’utilisateur accepte, exécuter **`git stash push -u -m "begin session"`** avant l’étape 4, puis **`git stash pop`** après une intégration réussie (uniquement avec accord explicite).
     - **Continuer sans stash** : seulement si l’utilisateur le demande **explicitement** et en connaissance de cause (l’agent peut rappeler que ce n’est pas l’option par défaut).
  4. Si l’utilisateur ne confirme pas ou refuse : **s’arrêter** après `git status` (éventuellement résumer l’état et la branche), sans `fetch` ni merge/rebase.

### 4. Mettre à jour **sans toucher à `main`**

Principe : **`fetch`** met à jour les **refs distantes** ; la branche locale `main` n’est **pas** checkoutée ni modifiée par défaut. Cette étape n’a lieu **qu’après** validation de l’étape 3 (arbre propre ou accord explicite de l’utilisateur).

```bash
git fetch origin main
```

Puis, **toujours sur la branche dev-*** courante**, intégrer `origin/main` :

- **Par défaut (simple et sûr pour branches partagées)** :

```bash
git merge origin/main
```

- **Option rebase** (historique linéaire ; à éviter si la branche est déjà poussée et partagée sans convention rebase) :

```bash
git rebase origin/main
```

En cas de conflits : les signaler, lister les fichiers concernés, guider vers résolution (`git status`, édition, `git add`, puis `git merge --continue` ou `git rebase --continue`). Ne pas forcer (`--force`) sans demande explicite.

### 5. Mini-bilan « gadget » (à afficher dans la réponse)

Après intégration réussie, exécuter au besoin et résumer en **quelques lignes** :

```bash
git log -1 --oneline
git rev-list --left-right --count origin/main...HEAD
```

Interprétation rapide du compteur `left	right` : gauche = commits sur `origin/main` pas dans HEAD (normalement faible après merge/rebase) ; droite = commits locaux pas encore sur `main`.

**Bonus utiles** (si pertinent pour le repo) :

- Si `package.json` / `package-lock.json` / `pnpm-lock.yaml` / `requirements.txt` ont changé par rapport à avant le merge : rappeler **`npm install`** ou équivalent.
- Rappeler le lancement dev du projet si documenté (ex. selon `guidebranche.md` : `npm run dev`).

### 6. Synthèse pour l’utilisateur (en français)

Répondre avec :

- Branche vérifiée (OK ou erreur + commande `checkout`).
- Si l’étape 3 a bloqué (modifs locales sans accord) : résumer `git status -sb` et rappeler qu’aucun `fetch`/merge n’a été lancé tant que l’utilisateur n’a pas choisi.
- Actions Git effectuées (`fetch`, `merge` ou `rebase`).
- Dernier commit (`git log -1 --oneline`).
- Éventuellement divergence `origin/main...HEAD` en une phrase.
- Prochaine étape courte (ex. lancer le serveur de dev, ouvrir une tâche).

---

## Anti-patterns à éviter

- Ne pas faire `git checkout main` ni `git pull` **sur** `main` dans ce workflow (hors périmètre « session sur dev-* »).
- Ne pas rebaser une branche **déjà poussée et utilisée par d’autres** sans accord / convention d’équipe.
- Ne pas ignorer un working tree **sale** : **demander confirmation** et **ne pas** lancer `fetch` / merge / rebase sans réponse claire de l’utilisateur.

---

## Exemple d’invocation

> Je démarre ma journée — mets-moi à jour proprement sur ma branche dev (workflow begin du dépôt).

L’agent exécute les commandes, respecte les arrêts si mauvaise branche ou si des modifications locales sont en cours **sans accord explicite**, et renvoie le mini-bilan structuré une fois l’intégration terminée.
