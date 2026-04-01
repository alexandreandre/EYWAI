---
name: check-feature
description: Vérifie qu’une fonctionnalité demandée a bien été implémentée, teste son fonctionnement, et complète ou corrige le code si nécessaire. À utiliser lorsque l’utilisateur tape /check-feature avec le prompt d’origine décrivant la fonctionnalité.
---

# Check Feature

## Objectif

Ce skill sert à **vérifier qu’une fonctionnalité décrite dans un prompt d’origine est réellement implémentée, fonctionnelle et complète**, puis à **compléter ou corriger le code si besoin**.

Il est pensé pour être appelé quand l’utilisateur écrit quelque chose comme :  
`/check-feature` suivi du **prompt d’origine** qui décrivait la fonctionnalité à développer.

## Quand utiliser ce skill

Utiliser ce skill lorsque :

- l’utilisateur tape explicitement **`/check-feature`** ;
- et fournit un **prompt d’origine** décrivant une fonctionnalité (souvent longue ou multi-étapes) ;
- et souhaite savoir **si tout a été fait**, si c’est **vraiment fonctionnel**, et que l’agent **complète ou corrige** si nécessaire.

Ne pas utiliser ce skill pour des questions générales ou des micro-modifs isolées ; il est destiné à des **fonctionnalités complètes** (plusieurs fichiers, front + back, etc.).

---

## Workflow global

Lorsque ce skill est actif, suis ce workflow :

1. **Comprendre la fonctionnalité demandée**
   - Lire soigneusement le **prompt d’origine** fourni après `/check-feature`.
   - En extraire :
     - les **objectifs métier** (ce que l’utilisateur final doit pouvoir faire) ;
     - les **fonctionnalités attendues** (liste d’actions, écrans, endpoints, comportements) ;
     - les **contraintes techniques** importantes (auth, rôles, perfs, UX, validations, etc.).
   - Construire une **checklist structurée** (en mémoire ou dans la réponse) de tout ce qui doit être vrai pour considérer la fonctionnalité comme “finie”.

2. **Cartographier les zones de code concernées**
   - Identifier rapidement les zones probables :
     - frontend : pages, composants, API client, routes ;
     - backend : endpoints, services, modules, modèles, migrations, permissions ;
     - tests : unitaires, d’intégration, e2e si présents.
   - Utiliser les outils de navigation de code (SemanticSearch, Grep, Glob, Read) pour trouver :
     - les noms de pages, routes, endpoints, composants ;
     - les nouvelles entités métier ou modules techniques mentionnés dans le prompt.

3. **Vérifier la couverture fonctionnelle**
   - Pour chaque point de la checklist :
     - Chercher l’**implémentation correspondante** dans le code.
     - Vérifier que :
       - le code existe réellement ;
       - il est relié au reste de l’application (routes, navigation, injections, exports/imports, etc.) ;
       - il traite les cas principaux et, si précisé, les cas limites/erreurs.
   - Marquer mentalement (ou dans la réponse) chaque point comme :
     - **OK** : implémenté et cohérent ;
     - **PARTIEL** : présent mais incomplet ou fragile ;
     - **MANQUANT** : non trouvé ou non branché.

4. **Vérifier le comportement par l’exécution**
   - Quand c’est possible dans ce projet :
     - Lancer ou relancer les **tests** pertinents (unitaires / d’intégration) via `Shell` (ex. `pytest`, `npm test`, etc.).
     - Lancer les **vérifications statiques** utiles (linters, type-checkers) sur les fichiers modifiés.
   - Si un serveur de dev ou une appli web est en place et que le contexte s’y prête, utiliser un agent de type **browser** pour :
     - naviguer jusqu’à la fonctionnalité ;
     - exécuter les scénarios principaux décrits par le prompt (ex. créer un élément, valider un formulaire, changement d’état, etc.) ;
     - vérifier les états d’UI, messages d’erreur, redirections, droits d’accès.
   - Noter les comportements incorrects, incohérences UX ou erreurs techniques visibles.

5. **Corriger et compléter si nécessaire**
   - Pour chaque point **PARTIEL** ou **MANQUANT** :
     - Concevoir la modification minimale mais propre pour respecter le prompt d’origine et l’architecture actuelle du projet.
     - Apporter les modifications de code nécessaires (frontend, backend, tests, config, etc.).
     - Éviter de casser les parties existantes qui ne sont pas concernées.
   - Ajouter ou adapter des **tests** :
     - tests unitaires pour la logique critique ;
     - tests d’intégration ou e2e si l’infrastructure est déjà présente.
   - Relancer les tests et les validations rapides (lint, type-check) pour s’assurer que les corrections tiennent.

6. **Évaluer la complétude finale**
   - Repasser en revue la checklist construite à l’étape 1.
   - Mettre à jour le statut de chaque point après corrections :
     - **OK / implémenté** ;
     - **Non fait / compromis** (si le projet ou le temps ne permet pas).
   - Si certains points restent non implémentés (limitations techniques, manque de contexte, risques de régression), les **documenter explicitement** dans la réponse.

7. **Produire une synthèse claire pour l’utilisateur**
   - Répondre en français (sauf demande contraire explicite).
   - Fournir une synthèse structurée, par exemple :
     - **Résumé rapide** : oui/non, la fonctionnalité est considérée comme complète.
     - **Checklist de conformité** :
       - chaque point important avec statut (OK / PARTIEL / MANQUANT) ;
     - **Modifications effectuées** :
       - liste courte et high-level des fichiers/parties modifiées sans copier-coller de gros blocs de code ;
     - **Tests exécutés** :
       - quels tests/commandes ont été lancés et le résultat ;
     - **Limites connues / TODO** :
       - ce qui reste éventuellement à faire ou les risques identifiés.

---

## Détails d’implémentation à respecter

- **Ne pas s’arrêter à la première difficulté** :
  - Si un test ou une commande échoue, analyser l’erreur, ajuster le code et relancer.
  - Ne pas demander de validation à l’utilisateur juste pour confirmation si l’action est raisonnable à entreprendre.

- **Respecter le style et la structure du projet** :
  - Suivre les conventions déjà présentes (patterns backend/frontend, outils de test, structure des modules).
  - Éviter d’introduire des dépendances lourdes sans nécessité claire.

- **Limiter la verbosité du code ajouté** :
  - Pas de commentaires évidents qui ré-expliquent littéralement le code.
  - Les commentaires doivent uniquement expliciter des choix non évidents ou des contraintes métier.

- **Toujours vérifier les lints sur les fichiers modifiés** lorsque des outils sont configurés dans le projet.

---

## Exemple d’utilisation attendu

Demande typique de l’utilisateur :

> "/check-feature  
> Voici le prompt d’origine de la fonctionnalité que je voulais implémenter :  
> [texte du prompt d’origine décrivant la fonctionnalité, les écrans, les règles métier, etc.]  
> Peux-tu vérifier que tout est bien en place, que ça fonctionne, et compléter si besoin ?"

Comportement attendu de l’agent avec ce skill :

1. Analyse du prompt d’origine et création d’une checklist.
2. Inspection structurée du code (front, back, tests) pour chaque point de la checklist.
3. Exécution des tests / linters / éventuellement scénarios via navigateur si possible.
4. Corrections et compléments de code pour se rapprocher au maximum du prompt d’origine.
5. Synthèse claire en français de l’état de la fonctionnalité, des modifications effectuées et de ce qu’il reste éventuellement à faire.

