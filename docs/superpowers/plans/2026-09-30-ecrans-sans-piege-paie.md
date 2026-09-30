# Écrans de paie sans piège — plan d'exécution

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**But :** qu'aucune action de la gestionnaire ne puisse sembler réussie si elle a échoué, et qu'aucun écran ne montre un état périmé sans le dire. Ce plan couvre tous les points de l'appel du 30/09/2026.

**Spec :** `docs/superpowers/specs/2026-09-30-ecrans-sans-piege-paie-design.md` (159b19ff). Les numéros entre parenthèses renvoient à ses sections.

**Architecture :** des corrections ciblées, écran par écran. La logique de détection vit dans des modules purs, dans `domain/` côté backend et `utils/` côté front, testés à part. Les refus de génération passent par le canal existant des refus structurés `{code, message, …}` (voir `frontend/src/features/payroll/utils/generationGuards.ts`, `extractGenerationRefusal`, `REFUSAL_DIALOG_LABELS`). Aucune donnée réelle n'est modifiée.

**Stack :** FastAPI (Python 3.11 en CI), React/TypeScript, TanStack Query, Supabase (base de test `tlvkjwleahkmuzcegrde`), Vitest, pytest, Playwright (`frontend/e2e/connecte/08-mode-paie.spec.ts` = écran de la gestionnaire).

## Contraintes globales

- Aucune écriture dans les données de Colorplast ni de Comitech, qui portent la vraie paie. Les tests en base utilisent la société de démonstration (MAJI, compte QA). Les calculs sur données réelles se font en bac à sable, avec toutes les écritures piégées.
- Jamais la production (`slleauhyjnmiawosvlcg`).
- Aucun nom de salarié dans git : ni dans le code, ni dans les tests, ni dans les commits (table `data/_outils/pseudonymes.json`, garde `python -m scripts.verification_rgdu.sans_nom`).
- Commits en français, sur `fix/payslip-edit-state`, terminés par `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. Jamais de push sur `main`.
- Chaque tâche suit le TDD : test rouge d'abord, puis vert.
- Un changement du moteur de paie passe le filet (`make filet`) à zéro écart avant son commit.
- Tests backend : `cd backend && env -u APP_ENV .venv/bin/python -m pytest -q -p no:faulthandler <chemins>`. Deux tests connus échouent en local à cause de l'environnement (`test_app_env_defaut_est_prod`, `test_api_failure_manual_fallback`).
- Tests front : `cd frontend && npx vitest run <chemins>` ; types avec `npx tsc --noEmit -p tsconfig.app.json`, ou le script du dépôt.
- Textes de l'écran : en français, simples, qui disent quoi faire ; jamais « Une erreur est survenue » seul.
- Déploiement sur le site de test seulement à la fin des deux lots, après CI verte et test de bout en bout, avec l'accord d'Alexandre : `gh workflow run deploy-test-env.yml --ref fix/payslip-edit-state`.

## Faits déjà établis (30/09/2026)

- **Départs.** `backend/app/modules/employee_exits/application/queries.py:55-76` (`list_exit_eligible_employees`) exclut tout salarié sans contrat de travail généré par EYWAI (`employee_has_work_contract`, `exit_block_reason(..., has_work_contract=...)`). Le front affiche alors « Aucun collaborateur éligible » (`frontend/src/components/exits/CreateExitDialog.tsx:160-175, 314-333`).
- **Heures pendant un arrêt.** Des heures saisies au réel un jour d'arrêt au prévu deviennent des heures sup par deux chemins : le calcul normal (`payslip_generator.payroll_analyzer_analyser`, `analyser_horaires_du_mois`) et l'option société `compensation_semaines` (`backend/app/modules/payroll/application/compensation_semaines.py`). Neutraliser un seul chemin ne suffit pas, c'est vérifié à blanc. L'arrêt n'est alors retenu que sur les jours sans heures.
- **Écran périmé.**
  - Le bouton « Régénérer » (`frontend/src/components/payslip-edit/RegeneratePayslipButton.tsx`) appelle bien `generatePayslip`.
  - Le cache TanStack Query est persisté 24 h (`eywai-rq-cache-v1`).
  - Une suppression d'un bulletin déjà supprimé renvoie 500 (PGRST116, `.single()` sur 0 ligne, `payslips/api/router.py` → « Échec de delete_payslip_route »). L'écran a ensuite demandé un bulletin inexistant (404).
  - Le PDF est réécrit au même chemin (`payslip_generator.py:1284-1295`, `x-upsert`).
- **Création de salarié.** Aucune requête (POST ni OPTIONS) n'est partie du navigateur. L'écran a affiché « Une erreur est survenue », avec une erreur sur le nom, alors que tous les champs obligatoires étaient remplis (RIB absent, contrat PDF déposé). Le formulaire n'a pas `noValidate` (`CreateEmployeeForm.tsx:893`). Le nom n'exige que deux caractères (`createEmployeeFormSchema.ts:13`). Le texte du `catch` sans réponse serveur est « Une erreur inattendue est survenue. Veuillez réessayer. » (`CreateEmployeeForm.tsx:~840`).
- **La génération écrit `employee_schedules.cumuls`.** `employee_schedules.updated_at` bouge donc à chaque génération : il ne peut pas servir seul à détecter qu'un bulletin est périmé.

---

## LOT A — ce qui bloque la paie

### Tâche A1 : un salarié repris peut partir (4.1)

**Fichiers :**
- Modifier : `backend/app/modules/employee_exits/application/queries.py` (`list_exit_eligible_employees`), la fonction `exit_block_reason` (la trouver par grep) et ses appelants ;
- Modifier : `frontend/src/components/exits/CreateExitDialog.tsx` ;
- Tests : `backend/tests/unit/employee_exits/` (fichier existant ou nouveau `test_eligibilite_depart.py`) et le test vitest du dialogue s'il existe.

- [ ] **Étape 1 : lire et cartographier.** Tous les appelants de `exit_block_reason` et `employee_has_work_contract` ; les blocages légitimes à garder (déjà parti, départ en cours, statut non actif).
- [ ] **Étape 2 : tests rouges (pytest).**
  - Un salarié actif sans contrat généré est éligible, avec `contrat_absent=True`.
  - Un salarié actif avec contrat est éligible, avec `contrat_absent=False`.
  - Un salarié déjà parti, ou avec un départ en cours, n'est pas éligible.
- [ ] **Étape 3 : implémenter.**
  - L'absence de contrat n'est plus un motif de blocage ; elle devient une information : champ `contrat_absent: bool` dans `SimpleEmployee`, ou un modèle dédié si ce type est partagé.
  - Le dialogue affiche, pour un salarié sans contrat : « Contrat non présent dans EYWAI (repris de l'ancien logiciel) : le départ se crée quand même ».
  - Le texte « Seuls les collaborateurs actifs disposant d'un contrat de travail généré… » est remplacé par une explication juste des cas restants.
- [ ] **Étape 4 : vert, puis la suite `tests/unit/employee_exits`.**
- [ ] **Étape 5 : contrôle à blanc en lecture.** La requête d'éligibilité, lancée sur Colorplast en lecture seule (appel de la fonction avec le client admin, sans écriture), renvoie les salariés actifs.
- [ ] **Étape 6 : commit** « fix(departs): un salarié repris sans contrat EYWAI peut partir ».

### Tâche A2 : heures saisies un jour d'arrêt (3.1 à 3.4)

**Fichiers :**
- Créer : `backend/app/modules/schedules/domain/conflits_arret.py` (module pur) et `backend/tests/unit/schedules/test_conflits_arret.py`.
- Modifier :
  - le générateur : garde avant calcul, dans `payroll/documents/payslip_generator.py` et en forfait si pertinent ;
  - le moteur : les deux chemins, analyse des horaires et `compensation_semaines.py` ;
  - l'endpoint de correction (router des calendriers) ;
  - l'import des pointages (`assisted-fill/persist-timesheet`) ;
  - le front : dialogue de refus (`generationGuards.ts` et les composants de refus), calendrier (`CalendarEmployeeTable` ou éditeur par salarié), récapitulatif d'import.

**Interfaces :**
- `jours_en_conflit(calendrier_prevu: list[dict], calendrier_reel: list[dict], absences_validees: list[dict] | None = None) -> list[JourEnConflit]`
- `@dataclass JourEnConflit(jour: int, type_prevu: str, heures_saisies: float)`

Un jour est en conflit si le prévu est un arrêt, ou une absence non travaillée (tous les types `arret_*`, et les absences que le moteur traite comme non travaillées : à lister depuis le code), ET si le réel porte des heures > 0.

- [ ] **Étape 1 : lire et cartographier.** Où le moteur lit le prévu et le réel sur la fenêtre des variables (`creer_calendrier_etendu`, `resoudre_fenetre_variables`), où les heures sup conjoncturelles sont calculées, d'où `compensation_semaines` lit les heures réelles, comment une absence validée écrit le prévu, et le format des refus structurés existants (`calendrier_incomplet`).
- [ ] **Étape 2 : module pur, TDD.** Cas à tester :
  - prévu arrêt et réel 9 h : conflit ;
  - prévu arrêt et réel 0 h : pas de conflit ;
  - prévu travail et réel 9 h : pas de conflit ;
  - prévu congés payés et réel 8 h : conflit (même règle) ;
  - un week-end sans heures : ignoré ;
  - plusieurs mois de la fenêtre.
- [ ] **Étape 3 : garde de génération.** Si un jour de la fenêtre est en conflit, la génération répond 422 avec :
  - `detail = {code: "heures_sur_jour_d_arret", message: "<Prénom> est en arrêt, mais des heures sont saisies les 7, 8… septembre.", jours: [{annee, mois, jour, heures}]}` ;
  - pas de forçage possible : la seule sortie est une correction.

  Tests pytest sur le refus.
- [ ] **Étape 4 : filet dans le moteur.** Dans les deux chemins, une heure saisie un jour en conflit est écartée : elle ne crée ni heure travaillée ni heure sup, et une alerte est posée sur le bulletin. Tests sur un calendrier synthétique : 0 heure sup, et arrêt retenu sur tout le mois.
  - Puis `make filet` : zéro écart attendu, puisque Colorplast en août n'a pas ce conflit ; sinon, signaler.
  - Puis un calcul à blanc, piège posé, sur la salariée réelle de Colorplast en arrêt en septembre : plus aucune heure sup, arrêt retenu sur tout le mois, net éventuellement négatif (voir A3).
- [ ] **Étape 5 : correction en un clic.** Endpoint `POST /api/employees/{id}/actual-hours/effacer-jours`, corps `{year, month, jours: [int]}` :
  - il remet les jours au type du prévu, avec 0 h ;
  - il est journalisé ;
  - il est réservé aux RH de la société (même garde que les autres écritures de calendrier).

  Tests : l'effacement et le refus pour une autre société.
- [ ] **Étape 6 : front.**
  - Le dialogue de refus pour `heures_sur_jour_d_arret` liste les jours et propose deux boutons :
    - « Elle était en arrêt : effacer ces heures » (conseillé) : il appelle l'endpoint, puis relance la génération ;
    - « Elle a travaillé : modifier l'arrêt » : il ouvre l'arrêt concerné dans l'écran des absences.
  - Le calendrier du salarié marque chaque jour en conflit (fond et info-bulle « Heures saisies pendant l'arrêt »).
  - Le récapitulatif de l'import des pointages signale les lignes tombées sur un jour d'arrêt.
  - Tests vitest du dialogue et du marquage.
- [ ] **Étape 7 : commits séparés** (module et garde, moteur, endpoint, front).

### Tâche A3 : mois entier d'arrêt, net négatif (3.5)

- [ ] **Étape 1 : lire.** Traitement d'un net à payer négatif : est-il ramené à 0 ou conservé ? Report au mois suivant : saisies `sur_le_net`, « Report NAP négatif ». Affichage sur le bulletin.
- [ ] **Étape 2 : calcul à blanc**, piège posé, de la salariée réelle arrêtée tout septembre, sans les heures en conflit (après A2). Relever le brut, les retenues et le net.
- [ ] **Étape 3.** Si le net négatif n'est pas conservé, n'est pas affiché comme tel, ou n'est pas proposé en report sur le mois suivant : écrire les tests rouges, corriger, repasser au vert, puis passer le filet.
- [ ] **Étape 4 : commit.** Le rapport chiffre le cas réel, sans nom.

### Tâche A4 : écran toujours à jour (2.1, 2.2, 2.5)

**Fichiers :** configuration du persister TanStack (clé `eywai-rq-cache-v1`) ; écrans de la paie du mois (`PayrollMonthExplorer`, `PayrollEmployeeExplorer`, `usePayrollGeneration`, ligne de bulletin avec les boutons œil et supprimer) ; `PayslipEdit.tsx` et `RegeneratePayslipButton.tsx` ; `backend/app/modules/payslips/api/router.py` (suppression) ; `payslip_generator.py:1284-1295` (PDF).

- [ ] **Étape 1 : lire et cartographier.** Clés de requête des bulletins, de la paie du mois et des calendriers ; invalidations actuelles après génération, régénération et suppression ; le générateur garde-t-il l'id du bulletin (upsert sur salarié, année, mois) ?
- [ ] **Étape 2 : tests rouges.**
  - Vitest : après génération, régénération ou suppression, les requêtes de la paie du mois et du bulletin sont invalidées.
  - Vitest : les clés « bulletins » ne sont pas persistées.
  - Pytest : supprimer un bulletin déjà supprimé répond 204, avec « déjà supprimé ».
- [ ] **Étape 3 : implémenter.**
  - Invalidations explicites.
  - Les requêtes des bulletins et de la paie du mois sont exclues de la persistance (`shouldDehydrateQuery`).
  - Suppression idempotente : pas de `.single()` sur une ligne absente.
  - Un bulletin introuvable côté écran affiche « Ce bulletin a été remplacé : rechargement… » et recharge la liste.
- [ ] **Étape 4 : PDF à jour.** Chemin versionné (`…/bulletins/<nom>_<horodatage>.pdf`) avec suppression de l'ancien fichier, ou `cacheControl` minimal au dépôt. Choisir après lecture et justifier dans le rapport. Test pytest sur le chemin.
- [ ] **Étape 5 : commits.**

### Tâche A5 : « Bulletin à recalculer » (2.3, 2.4)

**Principe retenu :** une empreinte des données d'entrée, et non les dates, puisque la génération écrit `employee_schedules`.

À la génération, le bulletin enregistre `payslip_data.parametres.empreinte_entrees`. C'est une empreinte stable (sha256 d'un JSON trié) de tout ce qu'il utilise :
- calendriers prévu et réel des mois de la fenêtre, hors `cumuls` ;
- absences validées qui touchent ces dates ;
- saisies du mois ;
- champs de la fiche qui servent au calcul.

**Interfaces :**
- module pur `backend/app/modules/payroll/domain/empreinte_entrees.py` : `empreinte(entrees: dict) -> str` ;
- service `empreinte_actuelle(employee_id, year, month) -> str` ;
- la liste de la paie du mois expose `a_recalculer: bool` par bulletin.

- [ ] **Étape 1 : lire.** Ce que lit exactement le générateur (pour ne rien oublier dans l'empreinte), l'endpoint de liste de la paie du mois, et la garde existante « un bulletin non recalculé ne se valide pas » (commit 19c16ebc).
- [ ] **Étape 2 : TDD du module pur.**
  - Une empreinte stable pour les mêmes entrées.
  - Changer les heures d'un jour change l'empreinte.
  - Changer les cumuls ne la change pas.
- [ ] **Étape 3 : service et exposition de `a_recalculer`.**
  - Un bulletin sans empreinte, parce qu'il a été généré avant ce changement, est « à recalculer : inconnu ». Il n'est pas marqué à tort.
  - La validation est refusée si `a_recalculer`, avec le message « Le calendrier ou les absences ont changé depuis le calcul : recalculez avant de valider ».
- [ ] **Étape 4 : front.**
  - Un badge « À recalculer » sur la ligne, et le bouton « Recalculer » à côté.
  - En tête de la page, un bouton « Recalculer tout ce qui a changé », qui relance la génération des seuls bulletins périmés et affiche la progression.
  - Après un recalcul, le toast résume les différences : heures sup, brut, net, avant → après.
  - Tests vitest.
- [ ] **Étape 5 : test de bout en bout** (Playwright, société de démonstration) : générer, modifier le calendrier, voir le badge, recalculer, voir le badge disparaître.
- [ ] **Étape 6 : commits.**

### Tâche A6 : création de salarié (1, 1.7, 1.8)

**Fichiers :** `frontend/src/features/employees/components/CreateEmployeeForm.tsx` et ses sous-composants ; `createEmployeeFormSchema.ts` ; `NouveauSalarieRecap.tsx` ; le client API front (intercepteurs) ; `backend/app/modules/employees/api/router.py:410` et la commande de création ; un nouvel endpoint de journal des erreurs de l'écran.

- [ ] **Étape 1 : reproduire.**
  - Vitest et testing-library : remplir le formulaire comme la gestionnaire (nom, prénom, date d'entrée le 21/09, contrat PDF déposé, RIB vide), puis soumettre.
  - Relever l'exception ou la validation exacte qui empêche l'envoi : lire toute la chaîne de `onSubmit`, l'extraction du contrat PDF qui pré-remplit des champs, et les intercepteurs d'`apiClient`.
  - Si la reproduction échoue en test unitaire, la faire en Playwright local contre le site de test, compte QA sur la société de démonstration.
  - Écrire la cause exacte dans le rapport.
- [ ] **Étape 2 : corriger la cause**, avec un test rouge qui la reproduit, puis vert.
- [ ] **Étape 3 : garde-fous.**
  - `noValidate` sur le formulaire, et plus de pas imposé sur les champs numériques.
  - Pastilles d'erreurs par onglet.
  - Encadré « Il reste à remplir », avec des liens vers les onglets.
  - Texte du bouton selon l'état.
  - Confirmation avant de fermer une saisie non enregistrée.
  - Bandeau rouge « Salarié NON enregistré : <raison> », sans jamais le message générique seul.
  - Succès : `NouveauSalarieRecap`, avec le salarié en tête de liste et le badge « Nouveau ».
  - Tests vitest.
- [ ] **Étape 4 : RIB facultatif.**
  - La fiche s'enregistre sans RIB, côté front et côté backend.
  - Mention « RIB à compléter » dans la liste.
  - Rappel dans la liste de contrôle du mois (tâche B3).
  - Tests pytest et vitest.
- [ ] **Étape 5 : journal des erreurs de l'écran.**
  - Endpoint `POST /api/client-errors`, authentifié, avec un débit limité.
  - Il reçoit l'écran, l'action, le message et la pile tronquée, sans données personnelles, et journalise côté serveur.
  - Le formulaire de création l'appelle dans son `catch`, et sur une erreur de validation inattendue.
  - Tests.
- [ ] **Étape 6 : entrée après la clôture des variables.** Test backend (ou calcul à blanc sur la société de démonstration) : une entrée le 21/09 avec une fenêtre close au 20/09 doit donner :
  - un bulletin payé au prorata du 21 au 30 ;
  - aucune variable ;
  - aucun refus « calendrier incomplet » pour des jours hors fenêtre.

  Corriger si besoin (`schedules/domain/periode_a_saisir.py`, `reprise_paie.raison_de_cumul_manquant`, `calcul_brut`).
- [ ] **Étape 7 : test de bout en bout.** Compléter `08-mode-paie.spec.ts` :
  - une valeur piège produit une erreur visible ;
  - fermer la fenêtre demande confirmation ;
  - une création sans RIB réussit, avec la mention « RIB à compléter ».
- [ ] **Étape 8 : commits.**

---

## LOT B — guider et expliquer

### Tâche B1 : sortie guidée (4.2 à 4.5)

- [ ] **Bandeau sur la page de paie du mois** : pour chaque salarié dont la fin de contrat tombe dans le mois sans départ créé, afficher « X quitte l'entreprise le JJ/MM : créez son départ », avec le bouton « Créer le départ » qui ouvre `CreateExitDialog`, salarié présélectionné.
- [ ] **Après la création du départ**, proposer « Générer le bulletin de sortie ».
- [ ] **Documents de sortie** grisés tant que le bulletin du mois de sortie n'existe pas, avec la mention « Générez d'abord le bulletin de sortie ».
- [ ] **Test** : une fin de CDD en cours de mois, où les montants des documents (indemnité de congés, précarité, dernier salaire) égalent ceux du bulletin.
- [ ] **Tests vitest et pytest ; commits.**

### Tâche B2 : aide sur le bulletin (6.1)

- [ ] **Explication par ligne**, côté backend, dans `payslip_data`, pour les lignes qui surprennent :
  - heures sup : détail semaine par semaine, depuis `compensation_semaines` ou le détail des heures ;
  - absences : type et dates ;
  - réduction générale : « régularisation depuis janvier ».

  Côté front, un astérisque et une info-bulle dans la vue du bulletin.
- [ ] **Section « Ce qui a changé par rapport au mois dernier »** : brut, net, heures sup et absences, comparés au bulletin du mois précédent.
- [ ] **Tests ; commits.**

### Tâche B3 : manuel opérateur et liste de contrôle (6.2, 6.3, 7)

- [ ] **Manuel opérateur** : une page du mode paie, avec la paie du mois étape par étape (pointages, calendrier, absences, générer, vérifier, recalculer, valider, sorties), les pièges connus et quoi faire. Le contenu est rédigé en français simple et relu par Alexandre avant la mise en ligne.
- [ ] **Liste de contrôle du mois** sur la page de paie, avec les étapes cochées automatiquement :
  - calendriers complets (`periode_a_saisir`) ;
  - aucun conflit arrêt/heures (A2) ;
  - absences saisies ;
  - bulletins générés et à jour (A5) ;
  - sorties créées (B1) ;
  - RIB manquants (A6) ;
  - actions en attente de la gestionnaire.
- [ ] **Tests ; commits.**

---

## FIN

### Tâche C1 : plan de recette pour Claude dans Chrome (8)

- [ ] Écrire `docs/recette/2026-10-recette-mode-paie.md`. Il est destiné à Alexandre, qui le donnera à Claude dans Chrome sur le site de test.
  - **Pré-requis** : compte QA et société de démonstration, **jamais Colorplast ni Comitech**.
  - **Pour chaque point de la spec**, un parcours numéroté : clics, données saisies, résultat attendu, capture à prendre.
  - **Parcours couverts** : création de salarié (valeur piège, fermeture, sans RIB, succès) ; heures un jour d'arrêt (refus, effacer, modifier l'arrêt) ; bulletin à recalculer ; suppression puis relance ; PDF à jour ; départ d'un salarié sans contrat ; bulletin de sortie ; aide sur le bulletin ; liste de contrôle ; manuel.
  - **Un prompt prêt à coller dans Claude dans Chrome.**
  - **Une grille de résultats** (OK, KO, remarque).
- [ ] Commit.

### Tâche C2 : vérifications finales et déploiement

- [ ] Suites complètes : backend, vitest, types, lint.
- [ ] `make filet`, à zéro écart.
- [ ] CI verte sur la branche.
- [ ] Test de bout en bout du mode paie contre le site de test, après déploiement.
- [ ] Déploiement sur le site de test **avec l'accord d'Alexandre**.
- [ ] Mettre à jour la mémoire (`ecran-sans-piege-pour-gaelle`, `visio-gaelle-2026-09-30`).

## Ensuite (hors de ce plan)

Reprendre le chantier « réduction générale » à la tâche 9 : `docs/superpowers/plans/2026-09-29-verification-reduction-generale.md`, registre `.superpowers/sdd/progress.md` et complément `.superpowers/sdd/rgdu-task-9-addendum.md`. Puis les corrections de la revue du 29/09 (réduction de janvier Comitech, forfait jours, heures des arrêts, étape 2 des lectures bloquantes).
