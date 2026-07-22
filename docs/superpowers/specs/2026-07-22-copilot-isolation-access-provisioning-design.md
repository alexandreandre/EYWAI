# Isolation du Copilot et création des accès

## Objectif

Garantir qu'un utilisateur ne puisse jamais obtenir via le Copilot des données d'une entreprise non autorisée, puis créer les accès métier demandés avec des mots de passe temporaires uniques et un fichier Excel transmissible.

## Ordre de livraison

1. Confinement immédiat du Copilot data.
2. Remplacement du SQL arbitraire par des outils métier scopés.
3. Tests d'isolation inter-entreprises.
4. Réactivation du Copilot data.
5. Configuration des accès et génération de l'Excel.

## Confinement

- Désactiver les parcours Copilot qui interrogent les données RH.
- Conserver l'aide à l'utilisation d'EYWAI et les réponses CCN sans données confidentielles.
- Retourner un message explicite indiquant l'indisponibilité temporaire des questions portant sur les salariés, bulletins, absences, indicateurs et autres données RH.

## Architecture cible du Copilot

- Les endpoints exigent un accès RH sur l'entreprise active.
- L'entreprise provient exclusivement du contexte authentifié et validé par `user_company_accesses`.
- Aucun repli sur une entreprise fournie par le prompt ou sur un profil potentiellement obsolète.
- Le LLM choisit parmi des outils métier autorisés ; il ne produit plus de SQL exécutable.
- Chaque outil exige `company_id` et applique ce filtre dans le repository.
- Les outils ne reçoivent jamais la liste des autres entreprises ni leurs identifiants.
- L'ancien chemin `execute_sql` n'est plus accessible depuis les endpoints Copilot.

## Outils métier initiaux

- Recherche et comptage des salariés.
- Bulletins et agrégats de paie.
- Absences et congés.
- Planning et temps de travail.
- Indicateurs RH autorisés.
- Conventions collectives de l'entreprise active.

Les demandes non couvertes doivent être refusées proprement, sans basculer vers du SQL libre.

## Sécurité et tests

- Refuser les collaborateurs sans droit RH.
- Refuser un `X-Active-Company` non présent dans les accès utilisateur.
- Tester une RH MBC demandant explicitement des données MAJI.
- Tester une injection demandant d'ignorer le périmètre.
- Tester chaque outil avec des données homonymes dans deux entreprises.
- Vérifier qu'aucune réponse debug ne renvoie de SQL ou de données brutes.

## Accès métier après sécurisation

- Utiliser les comptes existants sans créer de doublons.
- Accorder les rôles par entreprise via `user_company_accesses`.
- Ajouter les permissions par action et le périmètre MOI/MOD avant de promouvoir les profils « RH personnalisé ».
- Ne jamais coder une personne par son nom : l'envoi banque devient une permission attribuée à Vanessa Amate.
- Interdire la suppression d'un salarié dès qu'un bulletin existe.
- Réserver la vision consolidée et les données financières de participation aux administrateurs.
- Gérer les exceptions d'approbation des directeurs par configuration.

## Mots de passe et document final

- Générer un mot de passe temporaire robuste et unique par compte.
- Mettre à jour le compte Auth existant lorsque la personne possède déjà un profil salarié.
- Ne pas versionner les mots de passe.
- Générer un Excel local contenant : identité, identifiant de connexion, mot de passe temporaire, entreprises, rôles, périmètres et permissions principales.
- Le fichier est destiné à une transmission sécurisée et doit être supprimé après remise.

## Points métier encore à confirmer avant les écritures d'accès

- Liste exacte des salariés MOI/MOD.
- Portée de validation de Michael Francony sur les bulletins MBC.
- Consultation seule ou action de validation sur les contrats.
- Périmètre de Dorothée Boulay.
- Périmètre administrateur de Vanessa Amate et Gérault Verny.
