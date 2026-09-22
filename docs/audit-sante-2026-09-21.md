# État de santé EYWAI — 21 septembre 2026

Audit demandé par Alexandre : parcours utilisateurs, routes, données (test et
production), incohérences, dette technique. Trois inspections en parallèle plus
des contrôles directs sur le code, la base de test et la base de production.

**Légende** : « vérifié » = contrôlé directement pendant l'audit. « rapporté » =
remonté par une inspection, non recontrôlé ligne à ligne.

---

## A. La chaîne de vérification ne vérifie pas

| # | Constat | État |
|---|---|---|
| A1 | `frontend/tsconfig.json` porte `files: []` et ne fait que référencer les sous-projets : `tsc --noEmit -p tsconfig.json` **ne contrôle rien**. Le vrai projet est `tsconfig.app.json` → **113 erreurs**. | vérifié |
| A2 | `vite build` ne lance aucun contrôle de types ; `package.json` n'a pas de script `typecheck`. | vérifié |
| A3 | `.github/workflows/ci.yml` n'a **aucune étape de type-check frontend**. | vérifié |
| A4 | Ruff tourne en `continue-on-error: true` (ci.yml:84) : le linter n'a jamais fait échouer une fusion. **339 erreurs** sur `app/` + `scripts/` (34 dans `app/`, dont 18 imports morts). | vérifié |
| A5 | `npm run lint` = `eslint .` sans `--max-warnings` : **412 avertissements**, sortie 0, donc non bloquant. Dont 247 `any` (les plus coûteux sont dans `src/api/*`, ils annulent le typage jusque dans les écrans de paie). | rapporté |

**Conséquence** : tout le bloc B ci-dessous serait arrêté par une seule étape de
contrôle de types en intégration continue.

---

## B. Écrans cassés, en production aujourd'hui

| # | Écran | Défaut | Effet |
|---|---|---|---|
| B1 | Mes documents (`components/documents/EmployeeSelfDocumentsFolderContent.tsx:46`) | `DOCUMENT_TYPE_LABELS` utilisé sans import | page blanche dès qu'un document généré existe |
| B2 | Entretien annuel (`pages/rh/AnnualReviewDetail.tsx:350,369`) | `openBlobInNewTab` et `downloadBlob` non importés | le PDF ne s'ouvre jamais, impasse |
| B3 | Liste des entretiens (`pages/rh/AnnualReviews.tsx:473,493`) | `openBlobInNewTab` non importé, variable `a` orpheline d'un remaniement | message d'échec alors que le fichier est téléchargé |
| B4 | Planning, actions groupées (`components/schedules/CalendarBulkActionsBar.tsx:52`) | lit `activeCompany?.id` là où le contexte expose `company_id` | « Réel depuis badgeuse » grisé en permanence, sans explication |

Tous vérifiés. B1 à B3 apparaissent dans les 113 erreurs de types (A1).
Même défaut que B4, moins grave : `features/company/components/TimesheetImportSettingsCard.tsx:20`.
Reste de remaniement identique à B3 : `pages/rh/PromotionDetail.tsx:295`,
`pages/rh/cse/ExportsTab.tsx:58`, `components/employee-detail/EmployeeDetailAnnualReviewsTab.tsx:432`.

---

## C. Garde-fous qui sautent en silence

| # | Constat | Effet |
|---|---|---|
| C1 | `features/dashboard/widgets/GeneratePayrollModal.tsx:88` ne lit pas `isError` du contrôle avant paie | interface en panne → zéro anomalie affichée **et** plus de demande de confirmation : la paie part en croyant le terrain propre |
| C2 | `hooks/useRhPendingTasks.ts:345` renvoie `?? 0` sans `isError` | la liste de contrôle affiche « vous pouvez lancer la paie » quand une interface est en panne |
| C3 | `features/payroll/components/BlocPeriodeVariables.tsx:38` : `return null` si erreur | la fenêtre des variables disparaît sans un mot |
| C4 | `features/payroll/components/OvertimeRoutingPanel.tsx:73` : `rows = []` → `return null` | les décisions heures sup payer/compteur deviennent invisibles, la paie part sans elles |
| C5 | `saisies_avances/application/service.py:706` : `except Exception: pass` sur la mise à jour d'une avance **alors que la retenue est déjà au bulletin** | l'avance reste ouverte avec son ancien reste → **re-déduite le mois suivant**, sans trace |
| C6 | `payroll/documents/payslip_run_common.py:197` : `except Exception: pass` sur la politique de congés | repli sur juin en dur ; une société dont la période CP ne démarre pas en juin calcule sur la mauvaise fenêtre |

C1 à C4 rapportés, C5 et C6 rapportés. Tous plausibles et localisés.

---

## D. Cloisonnement entre sociétés

Le serveur utilise la clé technique Supabase (`core/database.py:42`) : aucune
protection de la base ne rattrape un défaut de périmètre applicatif.

| # | Route | Défaut |
|---|---|---|
| D1 | `modulation/api/router.py:183` | seul endpoint du fichier sans contrôle de rôle ni de société : tout compte connecté lit le compteur d'heures de n'importe qui |
| D2 | `employee_loans/api/router.py:105,118,130,142,154,166,181` | `require_rh_or_admin` puis accès par identifiant sans filtre société : un RH modifie, annule ou supprime le prêt d'une autre société |
| D3 | `trial_periods/api/router.py:51,70,79` | même schéma : confirmation ou renouvellement d'une période d'essai d'une autre société |
| D4 | `absences/api/router.py:789,815` | l'attestation de salaire (rémunération nominative) ne reçoit même pas l'utilisateur courant : téléchargeable par tout compte connecté |
| D5 | `payslips/api/router.py:558` | route de diagnostic sans filtre, et morte côté frontend : à supprimer plutôt qu'à corriger |
| D6 | `test_env/api/router.py:29` | resynchro depuis la production sans authentification, protégée seulement par le drapeau d'environnement |

Rapportés. Le remède existe déjà dans le code : le patron `_require_payslip_scope`.

---

## E. Production contre test

| # | Constat | État |
|---|---|---|
| E1 | La migration `20260917090000_reprise_paie_bascule` **n'est pas appliquée en production** : ni `payslips.origine`, ni `company_payroll_takeover`. Dernière migration appliquée : `20260915120000`. | vérifié |
| E2 | Mon code d'aujourd'hui lisait `origine` : en production, supprimer ou modifier un bulletin aurait échoué. **Corrigé** (commit 7834c1f3), la lecture retombe sur le statut seul. | vérifié |
| E3 | La production s'arrête à juin 2026 pour les sept sociétés ; aucun bulletin validé nulle part. | vérifié |

**À faire avant toute mise en production de la branche : appliquer la migration.**

---

## F. Données

| # | Portée | Constat |
|---|---|---|
| F1 | production, 1 379 bulletins | 6 bruts négatifs (Mont Blanc Composite : Baba, Osmani, Remini) |
| F2 | production | 4 bulletins à brut nul avec un net supérieur à 100 € (Maji : André, 3 800 € et 3 213 €) |
| F3 | production | 16 nets négatifs (Lewis : Baster, Sanchez, quatre mois chacun) |
| F4 | production | 151 bulletins avec un net supérieur au brut — souvent normal (frais, indemnités non soumises), déjà signalé par le moteur, mais à trier |
| F5 | test, 127 bulletins 2026 | 2 sans cumuls, 4 à brut nul, **aucune incohérence** entre la somme des lignes et le brut |
| F6 | test | aucun bulletin rattaché à une société différente de celle du salarié |

Tous vérifiés.

---

## G. Moteur de paie

| # | Constat | État |
|---|---|---|
| G1 | `engine/calcul_reduction_generale.py:69` lit `parametres_paie["taux_at_mp"]`, que **personne n'écrit** : les générateurs posent `parametres_paie["taux_specifiques"]["taux_at_mp"]`. Le taux vaut donc toujours zéro et la réduction est sous-évaluée. **Périmètre : uniquement les paies antérieures à 2026** ; 2026 passe par la réduction dégressive unique. | vérifié |
| G2 | `engine/calculT.py::calculer_parametre_T` est exporté par le paquet mais **n'a aucun appelant** ; il plafonne le taux accident du travail à une valeur 2025 en dur et somme d'autres taux que la vraie fonction. Deux paramètres divergents, le mauvais étant le plus facile à importer. | rapporté |
| G3 | `super_admin/infrastructure/queries.py:815-865` **réimplémente** la réduction Fillon avec ses coefficients en dur et un taux accident du travail par défaut à 3,1 % : l'écran d'administration et le bulletin ne donnent pas le même résultat pour 2025. | rapporté |
| G4 | `engine/calcul_indemnites_sortie.py:78,96` : les salaires de référence 12 et 3 mois renvoient le salaire de base, avec un `TODO`. Primes, treizième mois et heures sup ignorés → préavis et indemnité de licenciement sous-évalués. `:657` : `total_net = total_brut  # Temporaire`. | rapporté |
| G5 | `payslips/application/anomalies_report.py:34` : `SMIC_HORAIRE_2024 = 11.65`. En 2026 l'alerte sous-SMIC ne peut plus rien détecter et le message affiche « SMIC 2024 ». | rapporté |
| G6 | `engine/calcul_inverse.py:309` : `calculer_brut_depuis_net_avec_donnees` lève `NotImplementedError` alors qu'elle est exportée et appelée par `application/simulation_commands.py:33`. | rapporté |
| G7 | `payroll/backtest/comparator.py:32,34` : clé `acompte_participation` définie deux fois. | rapporté |

---

## H. Dette structurelle

| # | Constat |
|---|---|
| H1 | Fichiers hors de proportion côté serveur : `engine/calcul_brut.py` 1 755 lignes, `exports/application/service.py` 1 714, `cse_service_impl.py` 1 525, `documents/payslip_generator.py` 1 383, `engine/calcul_cotisations.py` 1 274. Les deux fichiers du cœur du calcul font 3 000 lignes sans frontière interne : c'est là qu'atterrit chaque correction et que se concentre le risque de régression. |
| H2 | Côté écran : `DsnImportWizard.tsx` 2 853 lignes, `CollectiveAgreementsCatalog.tsx` 1 725, `MedicalFollowUp.tsx` 1 689, `CreateEmployeeForm.tsx` 1 684. |
| H3 | Aucun test ne couvre le paramètre T de la réduction générale, dans aucune de ses deux versions : c'est ce qui laisse passer G1 et G2. |
| H4 | `engine/calcul_conges.py` et `engine/calcul_absences.py` ne sont importés par aucun test, alors que le double compte des congés au 1er juin est un défaut connu. |
| H5 | `engine/indemnites_sortie_brut.py` et `engine/simulation_pipeline.py` sans test : tout le solde de tout compte repose sur des tests indirects. |
| H6 | Taux de contribution sociale généralisée déductible écrit en dur pour l'affichage à trois endroits (`payslip_run_heures.py:972`, `payslip_run_forfait.py:467`, `simulation.py:257`) alors que la source existe. Le montant imprimé reste juste, le taux affiché deviendra faux au premier changement. |
| H7 | SMIC en dur à trois endroits (`anomalies_report.py:34`, `super_admin/queries.py:616`, `headcount_service.py:45`) pour une valeur qui existe dans les barèmes. Aucun plafond de sécurité sociale en dur : ce point-là est sain. |
| H8 | Routes mortes, aucun appel depuis l'écran : tout `/api/webhooks/*`, six routes d'administration des accès `/api/users/*`, quatre de simulation de participation, trois d'analyse de contrat, plus cinq isolées. |

---

## I. Affichage, points mineurs

- `pages/rh/SalarySeizures.tsx:238` : le `as any` masque un décalage réel — le serveur envoie `employee_name`, l'interface `api/saisiesAvances.ts:25` ne le déclare pas. Ajouter le champ suffit.
- `pages/rh/manager/LeaveRequests.tsx:32` : type d'absence `recuperation_modulation` sans libellé → `undefined` affiché. Lignes 48-50 : dates au format brut.
- `PunchAccountingSettingsCard.tsx:479`, `BadgeuseRh.tsx:680`, `OvertimeRoutingPanel.tsx:140` : dates brutes, statuts techniques, identifiant en repli.
- Rôle `collaborateur_rh` oublié dans trois tests de rôle écrits `admin || rh || admin` (`CompanyPage.tsx:169`, `MaintenanceSettingsCard.tsx:63`, `Absences.tsx:91`) : page atteignable mais en lecture seule.
- `pages/rh/Payroll.tsx:443` : bandeau d'erreur « Réessayez. » sans bouton de réessai.
- `pages/rh/SalaryAdvances.tsx` : montants sans séparateur de milliers ni espace insécable.

---

## J. Ce qui est sain

- Suite de tests du serveur : **6 234 verts**, deux rouges connus dus à l'environnement local.
- Base de test : aucune incohérence entre la somme des lignes et le brut, aucun bulletin mal rattaché.
- Cloisonnement correct sur les bulletins, plannings, saisies, dépenses, documents et suivi des indemnités journalières — le correctif d'août 2026 est en place et sert de modèle.
- Le webhook de signature électronique valide sa signature avant tout traitement.
- Aucune route exposée sans authentification hors authentification, webhook signé et environnement de test.
- Les plafonds de sécurité sociale et le taux d'exonération des heures supplémentaires viennent bien des barèmes, pas du code.

---

## Ordre d'attaque proposé

1. **A1 à A3** : ajouter le contrôle de types et le rendre bloquant. Une étape, qui attrape tout le bloc B.
2. **B1 à B4** : quatre écrans, correctifs d'une ligne chacun.
3. **E1** : appliquer la migration avant toute mise en production.
4. **D2 à D4** : appliquer le patron existant aux prêts, périodes d'essai et attestations.
5. **C5** : l'avance re-déduite est le seul défaut qui coûte de l'argent à un salarié.
6. **G1** puis un test sur le paramètre T, qui aurait attrapé G1 et G2.
7. Le reste selon le temps disponible.
