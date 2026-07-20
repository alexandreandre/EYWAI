---
name: backtest-paie-auto
description: >-
  Backtest paie autonome de bout en bout pour une entreprise et un mois donnés :
  compare tous les bulletins EYWAI aux bulletins réels (Cegid PDF + DSN), diagnostique
  chaque écart en utilisant la DSN comme source de vérité au centime, corrige (données
  puis, si nécessaire et sans risque de régression, moteur), boucle jusqu'à convergence
  (tier S ≤ 0,05 € pour tous), et documente les écarts résiduels. À utiliser quand
  l'utilisateur demande un backtest paie complet et automatique pour une entreprise/mois
  ("fais le backtest de <Entreprise> pour <mois>", "backtest automatique", "fais
  converger tous les bulletins de <Entreprise>"). Contrairement à `/backtest-paie`
  (mode collaboratif, un salarié à la fois avec l'utilisateur), ce skill tourne seul
  jusqu'à convergence ou blocage documenté.
---

# Backtest paie autonome (`backtest-paie-auto`)

Reproduit la méthode qui a fait converger **Colorplast mai 2026 à 7/7 salariés** (tier S
≤ 0,05 € partout), en partant des mêmes outils et du même raisonnement. Ne demande pas
de validation à chaque étape — ne repasser la main à l'utilisateur que si genuinement
bloqué (donnée manquante indispensable, ou risque de régression qu'aucune piste ne
résout).

## Entrées attendues

- **Entreprise** (ex. Colorplast) et **mois/année** (ex. 05/2026).
- Fichiers sources dans `Config/<Entreprise>/` :
  - `DSN/*.dsn` (déclarations réelles, LA source de vérité au centime — voir Phase 2).
  - `Compteur CP (bulletins de <mois>)/` ou équivalent : PDF Cegid de référence, et
    surtout le sous-dossier `bulletins_md_<AAAA>-<MM>/` généré par
    `scripts/backtest/export_reference_md.py` (voir ci-dessous) — **à lire en priorité,
    bien plus lisible qu'un PDF multi-colonnes**.
  - `Calendrier/`, `Enrichissement Salarié/` si présents (contexte calendaires).
  - `Pointages/` : badgeuse réelle, un PDF par semaine (`semaine NN (x).pdf`). **À
    consulter dès qu'un écart touche une absence, des heures sup. conjoncturelles, ou un
    brut qui ne colle pas alors que rien dans la config employé ne l'explique** — un
    pointage réel mal repris (ex. jour marqué travaillé à tort, ou l'inverse) est une
    cause fréquente d'absences fictives (déjà vécu sur GAUTHERON avril 2026 : jours
    27-28-29 à `heures_faites=0` en base alors que réellement travaillés, visible en
    recoupant avec le pointage réel). Extraire en texte (`pdftotext -layout`) et
    comparer semaine par semaine aux `employee_schedules.actual_hours` en base.
- Si un de ces dossiers n'existe pas, le signaler et proposer de continuer avec ce qui
  est disponible plutôt que de bloquer.

### Générer les bulletins de référence en Markdown (à faire en premier si absent)

```bash
cd backend && .venv/bin/python -m scripts.backtest.export_reference_md \
  --company <Entreprise> --year <AAAA> --month <MM>
```

Écrit un fichier par salarié dans
`Config/<Entreprise>/Compteur CP (bulletins de mai)/bulletins_md_<AAAA>-<MM>/<MATRICULE>.md`
(+ un `README.md` récapitulatif) avec :
- Un tableau des figures clés (brut, net imposable, MNS, net avant impôt, PAS, net à
  payer) — champs **fiables**, à comparer en premier.
- Un tableau des rubriques détaillées — parsé automatiquement, à vérifier contre le
  texte brut en cas de doute (les PDF Cegid multi-colonnes font parfois glisser une
  valeur dans la mauvaise colonne).
- Le texte brut complet (`pdftotext -layout`) en fin de fichier, pour l'inspection
  manuelle ligne par ligne quand une rubrique précise doit être vérifiée au centime.

Si le dossier `bulletins_md_<AAAA>-<MM>/` existe déjà pour ce mois, le réutiliser tel
quel plutôt que de re-générer (idempotent, mais inutile de repasser dessus).

## Principe directeur : corriger pour de bon, pas pour ce mois précis

**Chaque correction doit rester valable pour n'importe quel autre mois**, pas seulement
celui backtesté. Le but n'est pas de faire matcher mai 2026 par tous les moyens, mais de
corriger la cause de fond pour que juin, juillet, etc. soient corrects **par
conséquence**, sans repasser dessus.

Avant d'appliquer une correction, se demander : *"Si je backteste ce même salarié le
mois prochain sans y retoucher, est-ce que ça reste juste ?"*

- **Une config permanente mal saisie** (taux de cotisation, coefficient, mutuelle,
  `specificites_paie`, statut, classification) → corriger la config elle-même, une
  fois. Elle sert alors pour tous les mois passés et futurs. C'est le cas normal —
  la plupart des corrections de cette méthode (mutuelle 100%/0%, taux prévoyance,
  `is_forfait_jour`, coefficient) sont de cette nature.
- **Un événement réel mais ponctuel** (un arrêt maladie précis, une participation
  versée ce mois-ci, un acompte) → une saisie mensuelle (`monthly_inputs`, absence
  datée) est correcte et attendue : elle ne doit PAS se reproduire automatiquement le
  mois suivant si l'événement ne s'est pas reproduit. Ne pas la transformer en réglage
  permanent par erreur (ex. ne pas mettre un acompte ponctuel dans `specificites_paie`).
- **Un bug moteur** (formule, filtre, calcul) → toujours corriger le code, jamais
  contourner par une rustine de données pour un mois donné. Une donnée bricolée pour
  faire disparaître un symptôme de bug moteur cassera silencieusement un autre mois ou
  un autre salarié qui rencontre le même bug sans qu'on s'en aperçoive.
- **Piège à éviter** : si une correction ne fonctionne qu'en ajoutant une condition sur
  l'année/le mois en cours, ou en codant en dur un nom d'entreprise/de salarié dans le
  moteur (`app/modules/payroll/engine/`, `app/modules/payroll/documents/`), ce n'est
  **pas** une correction, c'est un hack à revert. Le moteur reste généraliste (voir
  `.cursor/rules/product-context.mdc`) — un paramètre par entreprise/salarié est
  acceptable (ex. `specificites_paie.jours_feries_anciennete_min_mois`), un `if`
  sur une date ou un nom ne l'est jamais.
- Après coup, si un mois précédent (`DSN` du mois M-1, M-2…) est disponible pour la
  même entreprise, c'est une bonne vérification de non-régression rétroactive : si le
  temps le permet, relancer rapidement la comparaison sur un mois déjà backtesté avant
  cette session pour confirmer qu'aucune correction n'a régressé un autre mois.

## Principe directeur n°2 : un salarié (ou un petit batch) à la fois, jamais un patch de masse aveugle

**Constat qui a motivé ce principe** (Mont Blanc Composite, 56 salariés, 2026-07) :
l'orchestrateur automatique applique ses patterns VERT à **tous** les salariés qui
matchent une signature à la fois (ex. `classification_coeff` appliqué à 48/51 salariés
en un seul coup). Résultat mesuré : certains salariés se sont **améliorés**, d'autres se
sont **dégradés** (un salarié cadre est passé de 4201 € à 6341 € d'écart après une seule
itération), parce que le même pattern heuristique n'est pas forcément la bonne
explication pour chaque salarié — seulement une corrélation statistique. Appliquer en
masse revient à corriger à l'aveugle : on ne sait plus, après coup, laquelle des N
corrections a aidé et laquelle a nui.

**Règle : ne jamais traiter plus de salariés à la fois qu'on ne peut individuellement
vérifier avant de continuer.**

- **Taille de lot recommandée : 1 salarié.** Un batch de 3-5 est acceptable seulement
  quand les salariés partagent une cause racine déjà confirmée identique (ex. même
  barème mutuelle partagé, déjà vérifié sur un premier cas) — jamais sur la seule base
  d'un score de confiance heuristique (`participation_missing`, `classification_coeff`,
  etc. depuis `diagnosis.py`).
- **Après chaque salarié (ou micro-batch) traité** :
  1. Régénérer son bulletin, comparer — l'écart doit avoir diminué. S'il augmente ou ne
     bouge pas, ne PAS continuer sur le suivant : comprendre pourquoi d'abord (le
     diagnostic était probablement faux pour ce cas précis).
  2. Régénérer et comparer **tous les salariés déjà validés (tier S ≤ 0,05 €)** de cette
     campagne — pas seulement ceux qu'on vient de traiter. Un salarié qui régresse
     signifie une correction partagée (barème, cotisation globale) appliquée à tort.
  3. Si régression : revert la correction pour CE salarié spécifiquement (pas pour tous
     les salariés du dernier batch — un correctif de masse peut être juste pour 3
     salariés sur 5 et faux pour les 2 autres ; les traiter au cas par cas).
  4. Ajouter le salarié à la liste des « validés » seulement une fois son tier S ≤
     0,05 € confirmé ET aucune régression détectée ailleurs.
- **L'orchestrateur automatique (`backtest_company_payroll.py`) reste utilisable comme
  point de départ rapide**, mais seulement pour **une itération** (pas la boucle
  complète de 12), et son résultat doit ensuite être **audité salarié par salarié**
  avant de le laisser tourner davantage — ne jamais le laisser tourner plusieurs
  itérations sans supervision sur une entreprise pas encore backtestée.
- Sur une grosse entreprise (40+ salariés), **prioriser par écart croissant** (les plus
  proches de la convergence d'abord) : ce sont souvent les mêmes causes simples
  (participation, coefficient, absence mal typée) qui, une fois comprises sur 2-3 cas
  faciles, se généralisent en toute confiance aux autres cas similaires — au lieu de
  s'attaquer d'abord aux cas extrêmes (souvent des profils atypiques : cadres,
  sorties, temps partiel) qui ont plusieurs causes empilées.

## Vue d'ensemble du flux

```
Phase 0 — Cadrage          : localiser les fichiers, résoudre l'entreprise, lister les mois DSN dispo
Phase 1 — Premier signal   : UNE itération de scripts/backtest/backtest_company_payroll.py, puis
                              audit individuel de son résultat (pas de confiance aveugle, voir ci-dessus)
Phase 2 — Boucle salarié par salarié : diagnostic DSN + correction + vérif régression, un par un,
                              du plus proche de la convergence au plus loin
Phase 3 — Discipline moteur : tout changement de code suit la même règle de vérif anti-régression
Phase 4 — Vérification     : pytest + re-comparaison globale + non-régression explicite
Phase 5 — Rapport final    : tableau avant/après, corrections appliquées, écarts résiduels documentés
```

---

## Phase 0 — Cadrage

1. Résoudre l'entreprise (`scripts.backtest.employee_matching.resolve_company_id`).
2. Lister les DSN disponibles dans `Config/<Entreprise>/DSN/` (un fichier par mois,
   nommé `NNNNNN_MMAA_NNNNNN (x).dsn`). Le fichier du mois cible sert de vérité terrain.
3. Convertir l'encodage si besoin (les DSN sont souvent en ISO-8859-1) :
   ```bash
   iconv -f ISO-8859-1 -t UTF-8 "Config/<Entreprise>/DSN/<fichier>.dsn" > /tmp/dsn.txt
   ```
4. Charger les références PDF (`scripts.backtest.pdf_loader.load_reference_bulletins`)
   et apparier les employés (`scripts.backtest.employee_matching.match_employees`).
5. Identifier les salariés déjà **gelés/validés** d'une session précédente (à ne jamais
   modifier sans instruction explicite) — chercher un fichier de campagne existant
   (`docs/backtest/<entreprise>/<AAAA-MM>/state.json` ou équivalent) ou demander.
6. **Avant tout : vérifier que les bulletins se génèrent sans planter** pour un
   échantillon de 2-3 salariés (`process_payslip_generation`). Une exception à la
   génération (ex. période de paie invalide, cf. bug catalogué n°15) produit des écarts
   énormes et incohérents qui ressemblent à des bugs de calcul mais n'en sont pas —
   toujours écarter cette cause avant de diagnostiquer plus finement.

## Phase 1 — Premier signal rapide (une seule itération, pas de confiance aveugle)

Lancer l'orchestrateur existant **pour une seule itération** (pas la boucle complète) :

```bash
cd backend && .venv/bin/python -m scripts.backtest.backtest_company_payroll \
  --company <Entreprise> --year <AAAA> --month <MM>
```

Si aucune option d'itération unique n'est exposée, le lancer en tâche de fond, le
laisser faire son itération 1, puis **l'arrêter** (le process reste vivant entre les
itérations, `kill <pid>` est sûr — c'est juste une boucle de comparaison/écriture, rien
d'irréversible) avant qu'il n'enchaîne une 2ᵉ itération sans supervision.

**Ne jamais traiter le résultat de cette passe comme acquis.** Elle sert à repérer
des signaux macro (combien de salariés ont un écart énorme vs modéré, quels patterns
reviennent souvent) — la vraie correction se fait en Phase 2, salarié par salarié, avec
vérification individuelle à chaque fois (voir Principe directeur n°2 ci-dessus).

**Note généralisation** : `REGRESSION_MATRICULES` dans ce script est actuellement
hardcodé à `{"COTTE", "BUGNY"}` (spécifique Colorplast) — de toute façon insuffisant
pour la Phase 2 (qui vérifie TOUS les salariés déjà validés, pas une liste fixe).

## Phase 2 — Boucle salarié par salarié (le cœur de la méthode)

Construire la liste des salariés KO, **triée par écart croissant** (le plus proche de
la convergence en premier). Pour chaque salarié, dans cet ordre, un par un :

1. **Comparer les figures clés déclarées** contre le bulletin EYWAI généré, en
   utilisant en priorité `bulletins_md_<AAAA>-<MM>/<MATRICULE>.md` puis la DSN pour
   trancher au centime :
   - `S21.G00.50.002` = net imposable officiel, `.009` = montant PAS.
   - `S21.G00.58` type `03` = **montant net social (MNS), fiable, à comparer directement**.
   - `S21.G00.58` type `01` = « montant net des heures compl/suppl exo. » — **PURE
     INFORMATION (cumul annuel plafond IR), PAS un terme du calcul du net imposable**.
     Ne jamais essayer de faire coller ce nombre en modifiant un taux de calcul
     (piège déjà tombé dedans, voir Anti-patterns ci-dessous).
   - `S21.G00.54` type `92` = mutuelle patronale (à réintégrer au net imposable via
     `_get_part_patronale_mutuelle`). Type `93` = prévoyance + retraite sup. patronale
     — **déclaratif, ne PAS réintégrer au net imposable** (casse tout le reste, voir
     Anti-patterns).
   - `S21.G00.60` = arrêt de travail déclaré (dates réelles début/fin/reprise) — utile
     pour confirmer/corriger le typage d'une absence.
   - `S21.G00.81` = détail de chaque cotisation par code URSSAF (base/montant/taux) —
     permet de vérifier N'IMPORTE QUELLE ligne de cotisation au centime près (comparer
     `taux × base` au montant déclaré pour confirmer/infirmer un taux suspect en base).
   - Chaque salarié démarre à `S21.G00.30.002,'NOM'`.
2. **Diagnostiquer la cause racine** (données vs moteur) avant de corriger quoi que ce
   soit. Ne pas réutiliser aveuglément l'étiquette de pattern posée par la Phase 1
   (`classification_coeff`, `fillon_systemic`, etc.) — ce sont des hypothèses à
   confirmer cas par cas, pas des diagnostics.
3. **Corriger les données d'abord** (`monthly_inputs`, `specificites_paie`, absences,
   classification) — scopé à **ce salarié uniquement**.
4. **Régénérer et comparer CE salarié** — confirmer que l'écart diminue vraiment. Sinon,
   revert et reconsidérer le diagnostic avant de toucher au salarié suivant.
5. **Régénérer et comparer tous les salariés déjà validés** de cette campagne (pas
   seulement celui-ci) — si un seul régresse, identifier lequel des changements en est
   responsable et le limiter/revert pour ce cas-là spécifiquement.
6. Marquer le salarié comme validé (tier S ≤ 0,05 €, non-régressif ailleurs) avant de
   passer au suivant.
7. **Ne toucher au code moteur que si un bug clair et généralisable est identifié**
   (voir catalogue ci-dessous), et dans ce cas suivre la Phase 3 (vérification élargie
   à TOUS les salariés, pas seulement le lot en cours) — jamais un fix de code pour un
   seul salarié isolé sans comprendre le principe général.

## Phase 3 — Discipline de correction moteur (règle absolue anti-régression)

Après **chaque** changement de code moteur (jamais après un simple changement de
donnée employé, qui reste scopé à la Phase 2) :

1. Régénérer le bulletin du salarié concerné, vérifier l'amélioration attendue.
2. Régénérer et comparer **TOUS** les salariés déjà à tier S ≤ 0,05 € (pas seulement
   celui qu'on corrige) — un fix qui améliore un cas isolé casse presque toujours au
   moins un autre salarié dans cette base de code (vécu plusieurs fois sur Colorplast).
3. `pytest tests/unit/payroll/` — si un nouvel échec apparaît, l'isoler
   (`git stash` puis re-tester) pour confirmer qu'il vient bien du changement en cours.
4. **Si régression détectée : revert immédiat**, ne pas essayer de « rattraper » avec
   un correctif supplémentaire empilé par-dessus. Documenter la piste écartée (voir
   Anti-patterns) pour ne pas la retenter.
5. Un fix validé sur **un seul exemple** (un seul salarié PEE, un seul cadre avec
   retraite sup., etc.) reste une hypothèse, pas une certitude — dire explicitement à
   l'utilisateur si un 2ᵉ exemple serait utile pour confirmer, plutôt que de généraliser
   silencieusement une règle à un seul point de données.

## Phase 4 — Vérification finale

- `pytest tests/unit/payroll/` complet.
- Re-générer et re-comparer **tous** les salariés de l'entreprise/mois (pas seulement
  ceux qui étaient KO) — la Phase 2 valide déjà au fil de l'eau, cette passe est la
  confirmation finale que rien n'a glissé entre deux vérifications intermédiaires.
- Confirmer noir sur blanc : tableau tier S avant/après pour chaque salarié.

## Phase 5 — Rapport final

Produire (et mettre à jour `docs/backtest/<entreprise>/<AAAA-MM>/report.md` si le
dossier existe) :

1. Tableau tier S avant/après par salarié.
2. Liste des corrections appliquées (données DB + code moteur), avec justification DSN
   quand disponible.
3. Fausses pistes explorées et écartées (pour ne pas les retenter en session suivante).
4. Écarts résiduels documentés comme KNOWN_GAP (avec la donnée manquante qui
   permettrait de les résoudre, si identifiable).
5. Mise à jour de la mémoire persistante (fichier memory dédié au backtest paie) avec
   tout nouveau bug moteur généralisable trouvé.

---

## Catalogue de bugs déjà rencontrés (vérifier en premier, gain de temps garanti)

1. **Arrêts maladie/AT jamais déduits** : les événements `arret_maladie`/`ferie` à 0 h
   étaient filtrés avant `calcul_brut.py` (`analyzer.py`). Symptôme : brut du salarié en
   arrêt = brut plein, aucune retenue.
2. **Absence chevauchant un week-end/férié** écrase ces jours en absence au lieu de les
   laisser neutres (`CalendarUpdateProvider.update_calendar_from_days`) → sur-déduction.
   Ne retyper que les jours `type=="travail"`.
3. **Repli journalier d'absence sur durée légale (35h/5=7h), pas contractuelle**
   (`calcul_brut._heures_journalieres_contrat`, plafonné `min(contrat,35)/5`).
4. **Jour férié non payé si ancienneté < seuil** : paramètre
   `specificites_paie.jours_feries_anciennete_min_mois`. 1er mai protégé sans condition.
   "Journée de solidarité" neutralisée via `companies.settings.jour_solidarite`.
5. **Absence + `salaire_hors_hs_structurelles`** : réduire aussi la quote-part
   journalière des HS structurelles mensualisées (ligne "Réduction HS structurelles"),
   ET l'exclure du calcul de défiscalisation IR (`is_reduction_hs` flag) sinon
   sur-exonération d'impôt.
6. **HS conjoncturelles 50%** : canal dédié `heures_supplementaires_conjoncturelles_50`
   (en plus du canal 25% existant) — sinon toute HS à 50% saisie manuellement est
   écrasée à zéro.
7. **Participation en PEE jamais câblée côté générateur** (`_is_participation_pee_input`
   dans `payslip_generator.py`, `part_pee` dans le moteur).
8. **MNS et participation 100% PEE** : `net_social += net_participation + csg_total_pee`
   où `csg_total_pee = csg_total - csg_total_numeraire` (la CSG de la part PEE contribue
   quand même au montant net social, même si le capital est différé).
9. **`net_avant_impot` ≠ copie de `montant_net_social`** dès qu'il y a une régularisation
   nette ou une participation PEE — recalculer en `net_a_payer + PAS réintégré`.
10. **Régularisations hors-DSN (absentes de la déclaration réelle)** : type "Report NAP
    négatif", "Régularisation GAN mutuelle famille" — ne réduisent QUE le net à payer,
    jamais le montant net social. Router via le mécanisme d'acompte existant
    (`saisies_data["acompte"]`), pas via les primes non soumises génériques. Confirmer
    leur absence de la DSN (`grep <montant> <dsn>`) avant de les modéliser ainsi.
11. **Mutuelle importée à 100% salarial / 0% patronal** (bug DSN import récurrent,
    table `company_mutuelle_types`). Vérifier `montant_patronal` contre le bulletin réel
    à chaque nouveau barème mutuelle rencontré — ne pas supposer qu'un barème existant
    est correct juste parce qu'il est déjà en base.
12. **Taux prévoyance/retraite sup. mal saisis lors d'une correction antérieure** :
    toujours vérifier `patronal`/`salarial` contre le bulletin réel (ligne "EPR3 GAN
    PREVOYANCE...", souvent 0,465%/0,465% symétrique), même sur un salarié qu'on pense
    déjà correctement configuré.
13. **`coefficient` de `classification_conventionnelle` = métadonnée DSN pure**, sans
    effet sur le taux horaire réel (qui vient d'un champ contractuel séparé). Ne pas
    chercher un bug de calcul si seul le coefficient diffère.
14. **Acomptes sur participation déjà versés** : `monthly_input` négatif, non
    taxable/non social (mécanisme `_apply_monthly_input`, action
    `monthly_input_acompte`).
15. **`companies.paie_jour_de_fin` invalide (ex. `31`) fait planter la génération de
    TOUS les bulletins de l'entreprise** (`definir_periode_de_paie` attend un jour de
    semaine 0-6, pas un jour du mois). Symptôme trompeur : la comparaison affiche des
    écarts énormes sur tous les champs (`eywai=None` partout, bulletin jamais généré) et
    les heuristiques de diagnostic les étiquettent à tort comme des bugs de calcul
    systémiques (ex. `fillon_systemic`, `mns_calculation`) alors qu'il n'y a même pas de
    bulletin généré. **Bug systémique confirmé sur 6 entreprises/7** (seule Colorplast,
    qui utilise un vrai cycle hebdomadaire glissant, avait une valeur valide). Fix
    générique : repli sur un mois calendaire plein (`_periode_calendaire`) quand
    `jour_de_fin` n'est pas dans 0-6, dans
    `payslip_run_common.definir_periode_de_paie`. **Toujours vérifier en Phase 0
    (génération de 2-3 bulletins tests) avant de diagnostiquer quoi que ce soit d'autre.**
16. **Paniers/frais professionnels "non soumis" doivent être ajoutés au net à payer
    SANS toucher au montant net social ni au net imposable** (contrairement à une prime
    non soumise classique, qui elle contribue au MNS). Signal DSN : le `S21.G00.58`
    type `03` (MNS) est inférieur au net avant impôt de tout ou partie du montant du
    panier. Mécanisme : `_is_frais_pro_non_soumis_input` (`payslip_generator.py`) route
    ces lignes vers le même canal net-only que les acomptes/régularisations
    (`saisies_data["acompte"]`, désormais bidirectionnel — signe positif = retenue,
    signe négatif = ajout net, cf. `calcul_net._calculer_net_a_payer`). Détection par
    le mot "panier" dans le libellé + `is_socially_taxed=False`.
17. **Primes variables courantes à ne pas oublier lors d'un import DSN incomplet** :
    primes de présence, d'assiduité, paniers "soumis" (différents des "non soumis" du
    point 16), heures sup. conjoncturelles à 25%/50% — toujours comparer la liste
    complète des rubriques du bulletin réel à ce qui existe dans `monthly_inputs`, pas
    seulement les gros postes (participation, absences).
18. **Bulletins avec un salarié "forfait jour" (`is_forfait_jour=True`) passent par un
    chemin de code totalement différent** (`payslip_generator_forfait.py` /
    `payslip_run_forfait.py`) jamais couvert par les corrections trouvées côté
    "heures" — à traiter comme une famille de bugs à part, ne pas supposer qu'un fix
    validé sur des salariés "heures" s'applique aux forfait-jour.
19. **Une absence/événement daté d'un mois mais apparaissant sur le bulletin du mois
    suivant** (régularisation/rattachement DSN, cf. `S21.G00.65`) est un cas complexe :
    une simple prime générique (même négative, même `is_socially_taxed=True`) ne
    reproduit PAS le comportement d'une vraie absence sur les cotisations — elle peut
    corriger le brut tout en dégradant le net. Ne pas se contenter d'un ajustement
    forfaitaire si le résultat empire un des trois indicateurs (brut/net imposable/MNS)
    même si un autre s'améliore ; documenter en KNOWN_GAP plutôt que d'insister.
20. **Barème mutuelle partagé importé avec un seul côté à 0** — pas systématiquement
    salarial=0 (comme sur Colorplast) : sur Mont Blanc Composite, plusieurs barèmes
    avaient **patronal=0** avec un salarial déjà correct, ou les deux côtés faux.
    Toujours comparer les DEUX montants du barème contre la ligne réelle du bulletin
    (`EMUx GAN Mutuelle ...`), ne pas supposer que seul le patronal est en cause.
21. **Taux prévoyance non uniforme d'un salarié à l'autre au sein de la même
    entreprise** (0,465 % chez certains, 0,5 % chez d'autres sur MBC) — ne pas
    réutiliser le taux trouvé sur un premier salarié sans revérifier au cas par cas
    contre le bulletin réel (`EPRx GAN PREVOYANCE ...`).
22. **`specificites_paie.dsn_anciennete.date_anciennete` peut écraser la vraie date
    d'embauche par une date de reprise erronée**, supprimant à tort la prime
    d'ancienneté (`resolve_seniority_reference_date` priorise cette valeur sur
    `hire_date`). Symptôme : écart de brut = exactement le montant de la prime
    d'ancienneté manquante. Vérifier la cohérence de cette date contre l'ancienneté
    réelle (hire_date) avant de l'utiliser telle quelle ; la supprimer si elle est
    manifestement incohérente (ex. plus récente que hire_date alors qu'aucune rupture
    de contrat ne le justifie).
23. **Montant de participation numéraire parfois importé avec une valeur par défaut
    erronée partagée entre plusieurs salariés** (ex. `3673.06` retrouvé identique et
    faux chez deux salariés différents de MBC alors que leurs vrais montants
    diffèrent) — toujours vérifier le montant exact contre le bulletin réel, ne pas
    supposer qu'une valeur déjà en base est correcte simplement parce qu'elle existe.
24. **Paniers/indemnités forfaitaires non soumis (mécanisme généralisé)** :
    `_is_frais_pro_non_soumis_input` (`payslip_generator.py`) route "panier" et
    "indemnité forfaitaire"/"déplacement" (non soumis) vers le canal net-only
    (`saisies_data["acompte"]`, désormais bidirectionnel signé — négatif = ajout net,
    positif = retenue nette, cf. `calcul_net._calculer_net_a_payer`). **Ne PAS y
    inclure "remboursement de notes de frais"** (dépenses réelles justifiées) : celui-ci
    reste dans le net social normal (vérifié régressif sur BUGNY sinon — testé et
    reverté une fois). Si un nouveau type de libellé "non soumis" apparaît et qu'il
    crée un écart MNS-vs-net-à-payer inexpliqué, vérifier d'abord s'il s'agit d'un frais
    professionnel (exclu du MNS) ou d'une vraie rémunération non soumise (incluse).

## Anti-patterns (pistes déjà testées, invalidées — ne pas retenter sans nouvelle donnée)

- **"CSG/CRDS sur HS non déductible" à 6,8% au lieu de 9,7% pour l'exonération IR** :
  semblait coller exactement à la DSN (`S21.G00.58` type `01`) pris salarié par salarié
  — cette valeur DSN est en réalité **informative** (cumul annuel), pas un terme réel du
  calcul. Change le taux casse tous les salariés déjà exacts.
- **Réintégrer la prévoyance/retraite sup. patronale au net imposable** (suggéré par
  `S21.G00.54` type `93`) : casse tout salarié avec prévoyance mais sans retraite sup.
  Ce code DSN sert à une déclaration statistique distincte.
- **Généraliser une formule à partir d'un seul exemple** (ex. participation PEE) sans
  la tester contre TOUS les salariés déjà validés — deux tentatives de formule MNS/PEE
  ont sur-corrigé avant de trouver la bonne (`net_participation + csg_total_pee`).
- **Exclure du MNS tout libellé contenant "frais"** (élargissement trop large de
  `_is_frais_pro_non_soumis_input` pour capter une "Indemnité forfaitaire dep.") : a
  cassé BUGNY (Colorplast, déjà à 0,00 €) dont le "Remboursement de notes de frais"
  DOIT rester dans le MNS. Corrigé en excluant explicitement "note de frais" et en ne
  matchant que "panier"/"indemnité forfaitaire"/"déplacement". Confirme la règle
  générale : élargir un pattern de détection par mot-clé sans re-tester TOUS les
  salariés déjà validés d'une autre entreprise est une régression quasi garantie.

## Fichiers clés

- `backend/scripts/backtest/backtest_company_payroll.py` — orchestrateur Phase 1.
- `backend/scripts/backtest/export_reference_md.py` — génère les bulletins de référence
  en Markdown lisible (Phase 0).
- `backend/scripts/backtest/employee_matching.py`, `pdf_loader.py`, `remediation.py`.
- `backend/app/modules/payroll/backtest/{comparator,diagnosis,thresholds,models}.py`.
- `backend/app/modules/payroll/engine/{calcul_brut,calcul_net,calcul_cotisations}.py`
  et `backend/app/modules/payroll/documents/{payslip_generator,payslip_run_heures}.py`
  — moteur, à modifier avec la discipline de la Phase 3 uniquement.
- `backend/app/modules/absences/infrastructure/providers.py` — synchronisation
  absence → calendrier de paie.
- Mémoire persistante dédiée (si présente dans le système de mémoire de l'agent) :
  contient l'historique détaillé des bugs et décisions par entreprise/mois — la
  consulter en début de session avant de redécouvrir un bug déjà connu.
