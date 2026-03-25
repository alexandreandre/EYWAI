## GRAND I : Travailler sur une branche feature


# 0) Voir ce que la feature apporte à main (à faire AVANT merge, idéalement)

git status

git log main..feature/ma-fonctionnalite --oneline



# Réponse OK (exemple) :
# 1a2b3c4 Commentaire
# 9d8c7b6 Another commit message
#
# Variante utile pour voir les fichiers concernés :
# git diff --name-only main..feature/ma-fonctionnalite





# 1) Créer une nouvelle branche à partir de la branche courante (idéalement main à jour)

git branch feature/ma-fonctionnalite

# (alternative recommandée : créer + switch en une commande)
# git checkout -b feature/ma-fonctionnalite
# Réponse OK (souvent silencieux) :
# (aucune sortie)


# 2) Vérifier sur quelle branche on se trouve

git branch

# Réponse OK (exemple) :
#   main
# * feature/ma-fonctionnalite
#
# Si tu n’es pas dessus, basculer :

git checkout feature/ma-fonctionnalite

# Réponse OK (exemple) :
# Switched to branch 'feature/ma-fonctionnalite'


# 3) Vérifier l’état du répertoire de travail (ce qui est modifié / non suivi)

git status

# Réponse OK (exemple si tu as des fichiers modifiés) :
# On branch feature/ma-fonctionnalite
# Changes not staged for commit:
#   modified:   path/to/file.ts
# Untracked files:
#   path/to/new_file.py
# (rien de grave : ça confirme juste ce que tu vas commit)


# 4) Ajouter au “staging” tout ce que tu veux inclure dans le commit

git add .

# Réponse OK :
# (aucune sortie)


# 5) Créer le commit (snapshot) avec un message au format Conventional Commits
#    Types : feat, fix, chore, docs, … — Scopes : payroll, auth, frontend, infra, api, ci
#    (voir CONTRIBUTING.md et commitlint à la racine ; un commit = une intention)

git commit -m "feat(frontend): description courte du changement"

# Variantes :
# git commit -m "fix(api): corriger la validation du bulletin"
# git commit -m "docs: mettre à jour le guide de déploiement"

# Réponse OK (exemple) :
# [feature/ma-fonctionnalite 1a2b3c4] feat(frontend): description courte du changement
#  5 files changed, 42 insertions(+), 6 deletions(-)
#  create mode 100644 path/to/new_file.py


# 6) Pousser la branche sur GitHub (remote) pour la sauvegarder / ouvrir une PR

git push -u origin feature/ma-fonctionnalite


# Réponse OK (exemple) :
# Enumerating objects: 12, done.
# Counting objects: 100% (12/12), done.
# Compressing objects: 100% (6/6), done.
# Writing objects: 100% (7/7), 2.10 KiB | 2.10 MiB/s, done.
# Total 7 (delta 4), reused 0 (delta 0)
# To https://github.com/<org>/<repo>.git
#  * [new branch]      feature/ma-fonctionnalite -> feature/ma-fonctionnalite
#
# (si la branche existe déjà sur le remote, la sortie sera similaire mais sans [new branch])



## GRAND II : Merge avec main


# 7) Revenir sur main pour intégrer la feature

git checkout main

# Réponse OK (exemple) :
# Switched to branch 'main'
# Your branch is up to date with 'origin/main'.


# 8) Mettre main à jour depuis le remote (important avant de merge)

git pull origin main

# Réponse OK (exemple) :
# From https://github.com/<org>/<repo>
#  * branch            main       -> FETCH_HEAD
# Already up to date.
#
# ou (si main récupère des commits) :
# Updating 1234567..89abcde
# Fast-forward
#  ...


# 9) Fusionner la branche de feature dans main

git merge feature/ma-fonctionnalite

# Réponse OK (exemple) :
# Merge made by the 'ort' strategy.
#  path/to/file.ts | 10 +++++-----
#  1 file changed, 5 insertions(+), 5 deletions(-)
#
# Note : Git peut ouvrir un éditeur pour le message de merge (ex: nano).
# Dans nano : CTRL+X, puis Y, puis Enter pour valider.


# 10) Pousser main sur GitHub (le merge devient effectif sur le remote)

git push origin main

# Réponse OK (exemple) :
# Enumerating objects: 5, done.
# Counting objects: 100% (5/5), done.
# Writing objects: 100% (3/3), 420 bytes | 420.00 KiB/s, done.
# Total 3 (delta 2), reused 0 (delta 0)
# To https://github.com/<org>/<repo>.git
#    89abcde..fedcba9  main -> main


# 11) Vérification finale : il ne doit rien rester en attente

git status

# Réponse OK (exemple) :
# On branch main
# nothing to commit, working tree clean






Exemple ou ça marche bien : 
alex@MacBook-Air-94 beta_test % git branch
  feature/entretiens_annuels
  feature/exports
* feature/mutuelle
  feature/onglet-exports
  feature/saisies
  feature/titre-de-sejour
  main
alex@MacBook-Air-94 beta_test % git status

On branch feature/mutuelle
Changes not staged for commit:
  (use "git add/rm <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
        deleted:    backend_api/backend_calculs/data/employes/DA SILVA CARDOSO_Vitor manuel/contrat.json
        modified:   backend_api/backend_calculs/moteur_paie/calcul_cotisations.py
        modified:   backend_api/backend_calculs/moteur_paie/calcul_net.py
        modified:   backend_api/main.py
        modified:   frontend/src/pages/CompanyPage.tsx
        modified:   frontend/src/pages/Employees.tsx
        modified:   frontend/src/pages/PayrollDetail.tsx

Untracked files:
  (use "git add <file>..." to include in what will be committed)
        backend_api/api/routers/mutuelle_types.py
        backend_api/schemas/mutuelle_type.py
        frontend/src/api/mutuelleTypes.ts

no changes added to commit (use "git add" and/or "git commit -a")
alex@MacBook-Air-94 beta_test % git add .

alex@MacBook-Air-94 beta_test % git commit -m "Ajout gestion de la mutuelle depuis page 'Mon Entreprise'"

[feature/mutuelle 72ffe88] Ajout gestion de la mutuelle depuis page 'Mon Entreprise'
 10 files changed, 1281 insertions(+), 78 deletions(-)
 create mode 100644 backend_api/api/routers/mutuelle_types.py
 delete mode 100644 backend_api/backend_calculs/data/employes/DA SILVA CARDOSO_Vitor manuel/contrat.json
 create mode 100644 backend_api/schemas/mutuelle_type.py
 create mode 100644 frontend/src/api/mutuelleTypes.ts
alex@MacBook-Air-94 beta_test % git push origin feature/mutuelle)
zsh: parse error near `)'
alex@MacBook-Air-94 beta_test % git push origin feature/mutuelle)
zsh: parse error near `)'
alex@MacBook-Air-94 beta_test % git push origin feature/mutuelle 
Enumerating objects: 44, done.
Counting objects: 100% (44/44), done.
Delta compression using up to 8 threads
Compressing objects: 100% (23/23), done.
Writing objects: 100% (24/24), 14.51 KiB | 7.25 MiB/s, done.
Total 24 (delta 19), reused 0 (delta 0), pack-reused 0
remote: Resolving deltas: 100% (19/19), completed with 19 local objects.
remote: 
remote: Create a pull request for 'feature/mutuelle' on GitHub by visiting:
remote:      https://github.com/alexandreandre/beta_test/pull/new/feature/mutuelle
remote: 
To https://github.com/alexandreandre/beta_test.git
 * [new branch]      feature/mutuelle -> feature/mutuelle
alex@MacBook-Air-94 beta_test % git checkout main
M       git/README.md
Switched to branch 'main'
Your branch is up to date with 'origin/main'.
alex@MacBook-Air-94 beta_test % git pull origin main
From https://github.com/alexandreandre/beta_test
 * branch            main       -> FETCH_HEAD
Already up to date.
alex@MacBook-Air-94 beta_test % git merge feature/mutuelle
Auto-merging backend_api/backend_calculs/moteur_paie/calcul_net.py
Merge made by the 'ort' strategy.
 backend_api/api/routers/mutuelle_types.py        | 408 ++++++++++++++++
 .../DA SILVA CARDOSO_Vitor manuel/contrat.json   |  18 -
 .../moteur_paie/calcul_cotisations.py            |  58 ++-
 .../backend_calculs/moteur_paie/calcul_net.py    |  34 +-
 backend_api/main.py                              |   3 +-
 backend_api/schemas/mutuelle_type.py             |  46 ++
 frontend/src/api/mutuelleTypes.ts                |  68 +++
 frontend/src/pages/CompanyPage.tsx               | 485 ++++++++++++++++++-
 frontend/src/pages/Employees.tsx                 | 155 ++++--
 frontend/src/pages/PayrollDetail.tsx             |  84 +++-
 10 files changed, 1281 insertions(+), 78 deletions(-)
 create mode 100644 backend_api/api/routers/mutuelle_types.py
 delete mode 100644 backend_api/backend_calculs/data/employes/DA SILVA CARDOSO_Vitor manuel/contrat.json
 create mode 100644 backend_api/schemas/mutuelle_type.py
 create mode 100644 frontend/src/api/mutuelleTypes.ts
alex@MacBook-Air-94 beta_test % git push origin main 
Enumerating objects: 19, done.
Counting objects: 100% (19/19), done.
Delta compression using up to 8 threads
Compressing objects: 100% (7/7), done.
Writing objects: 100% (7/7), 1.12 KiB | 1.12 MiB/s, done.
Total 7 (delta 6), reused 0 (delta 0), pack-reused 0
remote: Resolving deltas: 100% (6/6), completed with 6 local objects.
To https://github.com/alexandreandre/beta_test.git
   cb48a06..2baedfa  main -> main