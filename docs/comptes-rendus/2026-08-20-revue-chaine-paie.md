# Revue de la chaîne de paie — édition vérifiée du 20 août 2026

**Question** : si les RH saisissent correctement, la paie sort-elle juste,
et sinon est-ce signalé ?

**Méthode** : 4 explorations systématiques (calendriers, pointages,
absences/variables, alertes), puis **contre-vérification adversariale**
de chaque finding décisionnel par 5 vérificateurs indépendants chargés de
les réfuter (chemins alternatifs, frontend compris), plus vérifications
en base de production. Chaque point ci-dessous porte son verdict.

## Verdict global

**Non.** Le moteur de calcul est éprouvé (les backtests le prouvent au
centime), mais la chaîne applicative écran→moteur comporte des ruptures
silencieuses. La contre-vérification a **confirmé ou aggravé** la quasi-
totalité des findings, en a **nuancé** plusieurs (portées précisées, deux
conclusions corrigées), et a découvert **de nouveaux problèmes majeurs**,
dont deux atteignables dès aujourd'hui depuis l'UI.

Réfutations à retenir (honnêteté du rapport précédent) :
- « ni décompte de solde CP » était **faux** — le solde est décompté via
  les demandes ; c'est l'effet *paie* du CP qui manque.
- « prorata d'ancienneté toujours à 100 % » était **surestimé** — le réel
  atteint le moteur par un autre chemin ; le bug de clé JSON ne mord que
  sur les mois sans aucune heure travaillée, et ampute les cumuls SMIC
  des HS conjoncturelles.
- `backend/.env` n'est **pas** versionné (fausse alerte de fuite).
- Les e-mails de prod sont **tous redirigés** vers la boîte de test
  depuis le 07/08 (commit `71b5faaa`) — l'e-mail prématuré de bulletin ne
  part donc à personne aujourd'hui ; la notification **in-app**, si.

---

## A. Confirmés — paie fausse silencieuse (verdicts et portées exactes)

1. **CP validé sans effet paie** — CONFIRMÉ. Aucune branche `conge` dans
   le moteur, aucun normaliseur, et *tous* les producteurs (UI, validation
   d'absence, apply-model, import Quadra) écrivent `conge`. Le seul
   producteur de `conges_payes` est… la récup modulation (à tort, voir
   D3). **Aggravation** : le garde-fou « absence intégrale » ne compte que
   `travail`/`conges_payes` → un mois CP + arrêt donne un **bulletin
   ~0 €** (le complément déduit tout le mensualisé). Le fix n'est pas
   1 ligne : chantier vocabulaire (~25 fichiers front+back), reprise des
   calendriers existants (369 jours en prod, dont ~85 bulletins LEWIS et
   8 MAJI générés dessus), heures assimilées à trancher, sous backtest.
2. **Calendrier manquant → salaire plein** — CONFIRMÉ, pire : la
   « génération en masse » est une boucle frontend, 4 chemins de la page
   Paie ne consultent jamais le préflight, le seul garde est un
   `window.confirm` du widget dashboard. Point de correction unique :
   `generate_payslip` (couvre heures + forfait). 8 actifs sans calendrier
   en prod.
3. **Annuler une absence validée** — CONFIRMÉ techniquement, mais
   **inatteignable aujourd'hui** : l'UI n'offre pas d'annulation. À
   requalifier : *construire* la fonction d'annulation avec remise du
   calendrier (le backend accepte déjà n'importe quelle transition, sans
   garde — rejouer `validated` re-déclenche tout, y compris un **second
   débit modulation**).
4. **Maternité en régime maladie** — CONFIRMÉ aggravé : contrainte SQL,
   sélecteur obligatoire limité aux natures maladie/AT, branche moteur
   morte. **L'import DSN fait pire** : nature `None` → déduction sèche
   sur les mois historiques rejoués. Bon fix : **dériver** la nature du
   type d'absence (mapping + migration CHECK + DSN), pas l'ajouter au
   menu.
5. **Recalcul écrase un bulletin validé** — CONFIRMÉ élargi : les deux
   générateurs (heures + forfait) ; `status` n'est même pas exposé à la
   liste RH (l'UI ne peut rien afficher) ; l'historique d'édition ne
   reçoit rien ; `manually_edited` ment après écrasement.
6. **Heures sup** — CONFIRMÉ, pire : exiger la validation manager fait
   payer **plus** que ne pas l'exiger (pointé complet vs théorique +
   excédent) ; refuser une HS est un no-op ; chaque génération **écrase**
   `payroll_events` où vivaient les validations. ⚠ Ne PAS brancher
   l'injection au générateur (double comptage garanti) : retenir en
   attente dans `punch_accounting_rules` + recalcul à l'approbation.
7. **Arrêt sans nature = déduction sèche** — CONFIRMÉ + découverte
   majeure (voir D1) : le POST du planning efface les métadonnées des
   arrêts corrects. Le rapprochement IJSS n'est **pas** un filet (le
   salarié y est invisible), la simulation reproduit les bugs.
8. **Arrêt multi-mois** — CONFIRMÉ au jour près : sur 3 mois, ~6 j
   d'IJSS et ~14 j de maintien perdus, barème D1226-1 qui redémarre.
   `date_debut_arret_reel` sans producteur ; continuité <48 h et carence
   annuelle unique **inertes** (champs jamais produits — le toggle UI est
   un placebo). Fix : producteur + historique enrichi (jours consommés)
   + cumul dans le calcul du rang.
9. **Acomptes** — CONFIRMÉ : double déduction quand l'avance n'a aucune
   ligne de saisie « net seulement » en face ; **régénérer efface une
   retenue single** (remaining=0 au 1er passage) ;
   `get_advances_to_repay` ignore year/month ; acompte saisi positif =
   prime cotisée (aucun garde, ni front ni back). **Forfait-jour : deux
   bugs s'annulent** (circuit du brut mort + enrichissement qui déduit) —
   les corriger séparément crée une régression : lot unique.
10. **Clé JSON `calendrier_reel`** — bug CONFIRMÉ, conclusion corrigée :
    portée réelle = mois à 0 h travaillée (prorata figé, inversé si CC en
    politique proratisée) + `heures_sup_conjoncturelles_mois` toujours 0
    → **cumuls SMIC amputés des HS** (persistés). Second bug indépendant :
    lecture `heures` vs `heures_faites`. À corriger **sous backtest**
    (change des bulletins et des cumuls historiques).
11. **Fériés** — CONFIRMÉ : le hint frontend ne rattrape jamais un
    calendrier déjà persisté ; « copier le mois précédent » recopie par
    numéro de jour (week-ends décalés, fériés du mois cible perdus). Fix
    côté serveur à l'écriture, pas dans le hint.
12. **Pauses** — CONFIRMÉ : le « ~1 h » vit dans le prompt **et** dans le
    repli serveur ; `or 45`/`or 30` sur **5 sites** (créneaux compris —
    précisément ce que configurerait une boîte qui badge ses pauses) ;
    l'UI réaffiche 45 avec un toast « enregistré ». Nuance : ne touche
    que les feuilles manuscrites IA, pas les exports CSV. ⚠ invalider le
    cache d'aperçus (l'empreinte ignore la version du prompt).
13. **Fuseau horaire badgeuse** — CONFIRMÉ requalifié : l'instant stocké
    est correct (timestamptz) ; c'est l'arithmétique murale sans
    conversion qui fabrique 2 h de fausses HS l'été et coupe les nuits.
    Fix : conversions explicites Europe/Paris aux points de calcul (pas
    un simple `TZ=`). Aucun dégât historique : la badgeuse n'a jamais
    servi en prod (2 badges de test).
14. **Pause badgée avec moteur activé** — requalifié : substitution, pas
    double déduction — et c'est pire : une pause badgée longue fabrique
    des **HS fantômes**. Activer le moteur *dégrade* le chemin badgeuse.
15. **sans_solde / jtc / rtt** — NUANCÉ en 3 cas : `sans_solde`
    inatteignable par l'UI mais **produit par l'import DSN** (défaut du
    mapping) → no-op silencieux ; `jtc` réel (demande possible, aucun
    effet) ; `rtt` surtout un problème de vocabulaire (repos payé = pas
    de retenue, correct), mais type perdu à la moindre ré-édition et
    retypé `travail` par « Appliquer le modèle ».
16. **Week-ends « travail » du calendrier de repli** — NUANCÉ : neutralisé
    tant que le mois n'a aucun pointage (repli planning), **dangereux dès
    qu'un pointage arrive** — exactement la population de la vague 1.
    Aussi déclenché par l'import DSN sur des mois passés. Fix : réutiliser
    la génération standard (plan + fériés + temps partiel) + clé
    `periode` manquante.

## B. Illusions de contrôle (confirmées)

Anomalies « bloquantes » qui ne bloquent rien (aucun chemin de génération
ne consulte le préflight) ; rapport d'anomalies bulletins jamais affiché ;
R11 acomptes = code mort ; `use_last_nonzero_exit` = réglage mort ;
salarié qui **voit les bulletins brouillon** (aucun filtre `status` dans
son espace — le vrai périmètre du « e-mail prématuré ») ; renotification
à chaque régénération.

## C. Sécurité (découvert en chemin)

- **Clés Supabase inversées** : `SUPABASE_KEY` porte un JWT
  `service_role`, `SUPABASE_SERVICE_KEY` un `anon`. Le client « par
  défaut » de toute l'app contourne donc la RLS. Amplifie l'UPDATE
  participation sans filtre société (tamponne les saisies de **toutes**
  les sociétés → primes reclassées en participation exonérée). Deux
  correctifs distincts : cibler l'UPDATE par ids (les ids sont déjà
  retournés par l'insert), et remettre les clés à l'endroit.
- Les e-mails prod étant tous redirigés (07/08), les **e-mails
  d'activation** de la vague 0/1 ne partiront pas sans une levée ciblée
  par flux (ne pas retirer le redirect global).

## D. Nouveaux problèmes majeurs (hors rapport initial)

1. **Enregistrer le planning d'un mois efface les métadonnées d'absence**
   (nature d'arrêt, subrogation, historique) : le schéma GET/POST ne
   connaît que `{jour, type, heures}` et réécrit le mois entier. Un
   arrêt correctement saisi est dégradé en déduction sèche dès qu'une RH
   touche au planning. **Atteignable aujourd'hui — correctif le plus
   rentable du lot** (préserver les clés inconnues, merge au lieu de
   remplacement).
2. **Régénérer un planning efface les absences validées**
   (`OVERWRITE_ALL` par défaut, et rien ne marque les jours d'absence
   comme « manuels »). Atteignable aujourd'hui depuis l'UI.
3. **Récup modulation** : seule productrice de `conges_payes` → double
   débit (compteur modulation **et** solde CP) + affichage « congés
   payés » sur le bulletin. Et rejouer un PATCH de validation double le
   débit (aucune idempotence).
4. **Régénérer un bulletin efface une retenue d'avance** (voir A9).
5. « Copier le mois précédent » décale week-ends/fériés (voir A11).

## E. Ce que les RH doivent savoir (réunion du 26) — inchangé

Pause selon réglage société (45 min par défaut moteur activé ; 1 h sur
feuilles manuscrites importées sans réglage) ; écart ≤ 30 min → théorique
payé ; jour importé sans pointage → absence retenue ; mois sans pointage
→ planning payé tel quel ; HS auto-détectées mais validation aujourd'hui
sans effet ; congés via demandes d'absence (une fois le lot A livré).

## F. Clôturable

#29 alertes (bruit traité) : clos. Revue pré-paie : bon concept, à rendre
bloquante. #27 pauses : ne clôture pas (prompt + `or 45`). Comparaison
N/N-1 bloquante : vrai garde-fou (hors R11).

## G. Cadre de correction — lots cohérents, dans l'ordre

Chaque lot = TDD + backtest de non-régression (tout fix moteur reste
généraliste) ; migrations d'abord sur l'environnement de test.

- **Lot 1 — Préservation du planning** (D1+D2) : schéma qui préserve les
  clés inconnues, merge, `manuel` sur les jours d'absence. *Le plus
  rentable, atteignable aujourd'hui.*
- **Lot 2 — Vocabulaire calendrier** (A1+A15+D3, garde-fou « absence
  intégrale », heures assimilées, reprise des 369 jours + réexamen des
  bulletins LEWIS/MAJI concernés). *Le plus gros ; sous backtest.*
- **Lot 3 — Génération sûre** (A2 garde calendrier, A5 statut
  validé/version, notification après validation, filtre `status` espace
  salarié, B renotifications).
- **Lot 4 — Pauses/HS/TZ avant vague 1** (A12 prompt+repli+`or45`+cache,
  A6 retenue en attente + recalcul à l'approbation, A13 conversions TZ,
  A14 pause mesurée prioritaire).
- **Lot 5 — Arrêts** (A4 dérivation nature + DSN, A7, A8 producteur +
  historique enrichi, D« transition d'états » + annulation A3).
- **Lot 6 — Acomptes** (A9 en bloc : les deux générateurs ensemble,
  year/month, idempotence, garde de signe).
- **Lot 7 — Sécurité** (C : clés Supabase, UPDATE participation ciblé,
  levée ciblée du redirect e-mail pour l'activation).
- **Lot 8 — Fond** (A10 clé JSON sous backtest juillet, fériés côté
  serveur, afficher le rapport d'anomalies, préflight bloquant, contrôles
  manquants : net négatif, actif sans bulletin, SMIC à jour).

Ordre recommandé avant la **vague 1** : Lots 1, 3 (garde calendrier +
statut), 4. Le Lot 2 démarre en parallèle (le plus long). Avant toute
**bascule paie** : 2, 5, 6, 8-A10.
