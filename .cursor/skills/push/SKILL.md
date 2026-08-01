---
name: push
description: >-
  Clôture une session Git sur la branche courante : vérifie qu’on n’est pas
  sur main/master, regroupe ou découpe les commits selon les changements,
  rédige des messages détaillés et propres, pousse vers origin sur la même
  branche (jamais main). À utiliser en fin de journée ou de session, lorsque
  l’utilisateur demande /push, de sauvegarder ou pousser son travail, ou
  attache explicitement ce skill.
---

# Push — clôture de session Git

## Objectif

En fin de session, **sécuriser le travail** : **stager**, **committer** avec des messages **lisibles et détaillés**, puis **`push` uniquement la branche courante** vers `origin` — **sans jamais pousser sur `main` / `master`**.

## Quand utiliser ce skill

- L’utilisateur demande **`/push`**, une **fin de session**, de **tout committer et pousser**, ou attache ce fichier.

## Branches

- **Autorisées** : toute branche courante **autre que** `main` et `master` (`dev-*`, `feat/*`, `fix/*`, etc.).
- **Interdites** : `main` et `master` — la prod a son propre circuit (ex. skill **merge-dev-to-main**).

---

## Garde-fous (obligatoires)

1. **Branche courante** : `git branch --show-current`
   - Si la branche est **`main`** ou **`master`** → **arrêter**. Ne pas `add` / `commit` / `push`. Indiquer la branche actuelle et proposer de basculer sur une branche de travail (ex. `git checkout -b feat/…` ou `git checkout dev-alex`).
2. **Ne jamais** exécuter un push qui cible explicitement `main` ou `master` (ex. `git push origin main`).
3. **Pousser** uniquement la branche courante vers le **même nom** sur `origin`, par ex. :  
   `git push -u origin "$(git branch --show-current)"`  
   (ou équivalent sûr : la ref distante doit être `origin/<branche-courante>`.)

---

## Workflow (à exécuter dans l’ordre)

### 1. Contexte dépôt

- Racine du repo : `git rev-parse --show-toplevel` si besoin.

### 2. Vérifier la branche

```bash
git branch --show-current
```

Appliquer les **garde-fous** ci-dessus. Si arrêt, résumer en français ce qui bloque.

### 3. État des changements

```bash
git status -sb
```

- S’il n’y a **aucune** modification à committer :
  - Vérifier s’il reste des commits locaux non poussés : `git status` / `git log origin/<branche>..HEAD` si upstream configuré.
  - Si oui : proposer **seulement** `git push` (même branche) après re-vérification du nom de branche.
  - Si non : message court « rien à committer / rien à pousser » et arrêt propre.

### 4. Analyser le diff avant staging

- `git diff` (non stagé) et, si utile, `git diff --stat`.
- **Ne pas** committer de fichiers manifestement sensibles ou locaux s’ils ne doivent pas être versionnés (ex. secrets, `.env` contenant des clés) : respecter `.gitignore` ; si un fichier douteux apparaît, **alerter** l’utilisateur avant `git add`.

### 5. Staging

- Par défaut : **`git add -A`** à la racine du dépôt (ou chemins pertinents) pour inclure ajouts/suppressions, **sauf** si l’utilisateur impose un périmètre plus restreint.
- Re-vérifier : `git status` avant commit.

### 6. Commits : détaillés, propres, adaptés aux changements

**Principe** : messages en **français** ou **anglais** selon l’habitude du dépôt ; rester **cohérent** avec l’historique récent (`git log -5 --oneline`).

**Format recommandé** (style conventionnel, une ligne courte + corps détaillé si besoin) :

```text
<type>(<scope>): <résumé impératif, ≤ ~72 caractères>

- Détail 1 (fichier ou zone fonctionnelle)
- Détail 2
```

Types courants : `feat`, `fix`, `docs`, `refactor`, `chore`, `test`, `style` (UI), etc.  
**Scope** : `frontend`, `backend`, `api`, nom de module, etc., si ça clarifie.

**Découpage** :

- Si les changements regroupent **plusieurs sujets indépendants** (ex. correctif API + refonte UI sans lien) → **plusieurs commits** : stager par groupes (`git add -p` ou chemins ciblés), un message par intention.
- Si tout est **une même intention** → **un seul** commit bien rédigé.

Le corps du message doit refléter **le diff réel** (comportement ajouté, bug corrigé, risques connus), pas un texte générique.

### 7. Push

Après au moins un commit réussi sur la branche courante (non `main` / `master`) :

```bash
git push -u origin "$(git branch --show-current)"
```

- Si le push est refusé (non fast-forward, etc.) : **ne pas** `force push` sans demande explicite ; expliquer l’erreur et les options sûres (`git pull --rebase` sur la branche après accord, etc.).

### 8. Synthèse pour l’utilisateur (en français)

- Branche confirmée.
- Fichiers / thèmes principaux commités.
- Hashes ou titres des commits créés (`git log -3 --oneline`).
- Confirmation du **push** vers `origin/<branche>`.

---

## Anti-patterns à éviter

- Pousser depuis ou vers **`main`** / **`master`** dans ce workflow.
- Message du type « update » / « fix » sans détail quand le diff est large.
- Un seul commit « fourre-tout » quand deux intentions distinctes ressortent clairement du diff.
- `git push --force` sur une branche partagée sans instruction explicite.

---

## Exemple d’invocation

> `/push` — je ferme la session, tout est prêt à être sauvegardé sur ma branche.

L’agent vérifie que la branche n’est pas `main`/`master`, qualité des messages, pousse la branche courante vers `origin`, et renvoie une synthèse courte.
