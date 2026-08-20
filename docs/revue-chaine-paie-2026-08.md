# Revue de la chaîne de paie — 20 août 2026

**Question posée** : si les RH saisissent correctement (calendriers,
pointages, absences, variables), la paie sort-elle juste — et sinon,
est-ce signalé ?

**Méthode** : 4 explorations systématiques du backend (calendriers,
pointages/déductions, absences/variables, alertes), vérification de
l'état du paramétrage en prod, et contre-vérification manuelle des
découvertes les plus lourdes (§A1, A5, B1 relues dans le code).

## Verdict

**Non.** Le moteur de *calcul* est éprouvé (backtests au centime sur
plusieurs sociétés), mais la **chaîne de saisie applicative** — celle que
les RH utiliseront en vrai — comporte des ruptures silencieuses : des
saisies correctes qui ne produisent pas la paie attendue, et des
contrôles qui semblent protéger mais ne font rien. Les backtests ne
l'ont jamais vue : ils alimentent le moteur par les données historiques
(DSN, imports), pas par les flux RH (validation d'absence, badgeage,
imports de feuilles). **Valider le rail paie ne suffit donc pas : il faut
valider le rail saisie→paie avant la vague 1.**

---

## A. Paie fausse silencieuse, même avec une saisie correcte

Confirmés dans le code (réf. exactes) :

1. **Un congé payé validé ne produit rien en paie.** Le module absences
   écrit le type `conge` au calendrier
   (`absences/infrastructure/providers.py:236`), le moteur ne connaît
   que `conges_payes` (`payroll/engine/calcul_brut.py:925`). Ni retenue,
   ni indemnité CP, ni arbitrage 1/10 vs maintien, ni décompte du solde
   (`absences/domain/planning_cp.py:14`). *Contre-vérifié le 20/08.*
2. **Calendrier manquant = salaire plein, calendrier partiel = possible
   bulletin à ~0 €**, sans signal dans les deux cas
   (`payslip_generator.py:479-483` ; complément « absence intégrale »
   `calcul_brut.py:1009-1038` déclenché quand 0 jour de travail
   planifié). Le seul garde-fou (`payslip_run_heures.py:189-192`) est du
   code mort. 8 actifs sont aujourd'hui sans calendrier en prod.
3. **Annuler une absence validée ne remet pas le calendrier** : la
   retenue persiste sur tous les bulletins suivants
   (`absences/application/commands.py:291` — seul le statut change).
4. **Maternité/paternité traitées comme une maladie.** La branche
   maternité du moteur de maintien (100 %, sans carence) est
   inatteignable depuis le flux RH : `ArretType` ne propose pas
   `maternite` (`absences/schemas/requests.py:28-37`) alors que le
   moteur l'exige (`maintien_salaire_service.py:126-137`). Résultat :
   carence 3 j + carence employeur 7 j + barème dégressif, à tort.
5. **Un recalcul écrase un bulletin validé sans trace** : upsert sans
   `status` ni version (`payslip_generator.py:1054-1067`), les alertes
   acquittées restent acquittées, une édition manuelle est écrasée, et
   le salarié reçoit un e-mail identique sans mention de correction.
   *Contre-vérifié le 20/08.*
6. **La validation des heures sup est une impasse** : quand une revue
   manager est requise, le pointé complet — HS incluses — est retenu
   quand même (`punch_accounting_rules.py:283-286`), et une HS approuvée
   n'est jamais injectée dans le bulletin (l'injection n'est branchée
   que sur `calculate_payroll_events`, jamais sur le générateur).
7. **Arrêt maladie posé directement au planning** (sans passer par une
   demande d'absence) : déduction intégrale, **ni maintien ni IJSS**
   (`payslip_run_heures.py:139-140` exige un `arret_type` que l'éditeur
   de planning ne pose pas).
8. **Arrêt long multi-mois : le maintien repart à taux plein chaque
   mois.** `date_debut_arret_reel` n'a aucun producteur applicatif (seul
   un script de backtest l'écrit) → le barème D1226-1 ne s'épuise
   jamais.
9. **Acomptes, trois circuits non réconciliés** : une avance
   (`salary_advances`) sans ligne miroir en saisies peut être **déduite
   deux fois** à la première génération, le net change entre deux
   générations du même mois, un acompte saisi en **positif** devient une
   prime cotisée, et les bulletins forfait-jour lisent une colonne
   inexistante (aucune ligne d'avance au brut).
10. **Bug de clé JSON** : le générateur écrit `calendrier_reel`, le
    moteur lit `calendrier` (`payslip_generator.py:975-978` vs
    `payslip_run_heures.py:327`) → le « réel » est toujours vu vide →
    prorata de prime d'ancienneté forcé à 100 % quel que soit
    l'absentéisme.
11. **Jours fériés garantis seulement si le calendrier est généré par
    l'outil.** Saisi à la main ou importé sans férié : le 1er mai
    devient un jour ouvré, voire une absence injustifiée. Le moteur ne
    réinjecte jamais les fériés.
12. **Pauses** : le prompt IA d'import contient toujours « déduire ~1 h
    de pause » (`timesheet_page_schema.py:80` — le fix du 05/08 n'a pas
    touché le prompt) ; « pause = 0 » et « tolérance = 0 » sont
    impossibles à enregistrer (`or 45` / `or 30`,
    `punch_accounting_repository.py:31-32`) ; avec moteur activé, la
    pause réellement badgée peut être réintégrée puis une pause
    forfaitaire redéduite (première entrée / dernière sortie seulement).
13. **Badgeuse en UTC** (horloge du conteneur, pas de TZ) : un badge de
    8 h stocké à 6 h → fausses HS « entrée en avance », nuits coupées en
    deux.
14. **`sans_solde` et `jtc` n'ont aucun mapping calendrier**, `rtt` est
    ignoré par le calcul du brut (pas de retenue, pas d'heures
    assimilées) — congé sans solde non déduit si le mois n'a pas de
    pointage.
15. **La validation d'absence sur un mois non planifié fabrique un
    calendrier avec les week-ends typés « travail »**
    (`providers.py:280-316`) → jusqu'à ~8 jours d'absence injustifiée
    fictifs dès qu'un pointage existe.
16. **Échecs avalés** : génération auto des variables, avances,
    enrichissement, maintien — tous sous `try/except` → le bulletin part
    incomplet avec un simple warning serveur. Et l'UPDATE de traçabilité
    participation est sans filtre société (risque de reclassement massif
    de primes en participation exonérée).

## B. Illusions de contrôle

1. **L'e-mail « bulletin disponible » part à la génération**, avant
   toute validation RH et sans consulter la moindre alerte
   (`payslips/application/commands.py:61-82`).
2. Le rapport d'anomalies bulletins (brut nul, net>brut, cotisations
   négatives…) est **calculé mais jamais affiché** nominativement —
   l'API est orpheline côté frontend.
3. Les anomalies « bloquantes » de la revue pré-paie **ne bloquent
   rien** : la génération ne les consulte pas ; un clic « générer quand
   même » suffit.
4. La règle R11 « acompte déduit sans avance déclarée » est du code mort
   (contexte jamais renseigné).
5. Le réglage `use_last_nonzero_exit` est exposé mais jamais lu ;
   `manual_override` ne protège ni les lignes créées à la main, ni les
   suppressions, ni les renommages (doublon → double paiement).
6. Trois échelles de sévérité incompatibles selon le système d'alerte.

## C. Garde-fous absents (standard paie)

Net à payer négatif ; salarié actif sans bulletin (le compteur existe,
jamais nominatif) ; variation de masse salariale ; salaire sous le SMIC
(le proxy utilise un SMIC **figé à 2024**) ; durées légales (10 h/j,
48 h/sem, repos 11 h) ; écart badgeage vs feuille importée ; bulletin
périmé après modification d'une absence/variable ; arrêt « en cours »
vs terminé (structurellement indistinguables).

## D. État prod (20/08)

- Réglages de pause : **Colorplast et MBC seulement**. Cartol, Comitech,
  LEWIS badgent leurs pauses (chemin badgeuse : correct sans réglage),
  mais tout **import de feuille** chez eux subit le 1 h du prompt IA.
- **8 actifs sans aucun calendrier** (4 Cartol, 1 Comitech, 1 MBC,
  1 MAJI, 1 Zone 404) → salaire plein silencieux (§A2).
- MAJI/Zone 404 : aucun plan horaire société (cohérent, pas de badgeuse).

## E. Ce que les RH doivent savoir (réunion du 24)

Déductions et transformations automatiques, à dire explicitement :

1. Pause déduite selon le réglage société (45 min par défaut si le
   moteur est activé sans réglage ; **1 h sur les feuilles importées**
   dans les sociétés non paramétrées).
2. Écart pointé/théorique ≤ 30 min → on paie le théorique.
3. Jour importé sans pointage → absence à 0 h (retenue).
4. Mois entièrement sans pointage → le planning fait foi (aucune
   retenue) ; c'est voulu, mais une badgeuse en panne un mois = bulletin
   plein.
5. HS au-delà du théorique + tolérance → détectées automatiquement,
   mais la « validation manager » n'a aujourd'hui aucun effet réel (§A6).
6. Les congés doivent passer par les demandes d'absence — et tant que
   §A1 n'est pas corrigé, même ce chemin ne produit pas la paie.

## F. Ce qui peut clôturer

- **#29 Alertes de paie** : le bruit est bien traité (rétrogradations
  CCN, fix VM arrondissements, « bulletins non validés » conditionné au
  circuit de validation). Clos.
- **Revue pré-paie** : le contrôle « calendrier du mois incomplet »
  existe et fonctionne (informatif). Le concept est bon, à rendre
  bloquant plutôt qu'à reconstruire.
- **#27 Post-traitement pointages** : le chemin badgeage et le recalcul
  serveur sont alignés sur le réglage société — mais **ne peut pas
  clôturer** tant que le prompt IA garde son heure en dur (§A12) et que
  « pause 0 » est inenregistrable.
- La comparaison N/N-1 avec blocage de validation sur alerte critique
  est un vrai garde-fou qui marche (hors R11).

## G. Priorités de correction

**Avant la vague 1 (salariés qui badgent et posent des congés) :**
1. §A1 mapping `conge`→`conges_payes` (+ `sans_solde`, `rtt`, `jtc`)
2. §A3 annulation d'absence → remise du calendrier
3. §A15 week-ends « travail » à la validation d'absence
4. §A12 prompt IA + `or 45`/`or 30` (pause 0)
5. §A13 fuseau horaire badgeuse
6. Alerte bloquante « calendrier manquant/incomplet » à la génération
   (§A2) + les 8 actifs sans calendrier en prod

**Avant la bascule paie d'une société (critères des 5 verts) :**
7. §A5 recalcul : versionner, invalider le statut, ne plus écraser une
   édition manuelle ; ne plus notifier le salarié avant validation (§B1)
8. §A6 circuit HS réel ; §A9 acomptes (réconciliation + signe + forfait)
9. §A4 maternité, §A7 arrêt au planning, §A8 `date_debut_arret_reel`
10. Contrôles manquants : net négatif, actif sans bulletin, SMIC à jour

**Ensuite** : §A10 (clé JSON — attention, corriger change les bulletins,
à passer par backtest), fériés réinjectés, afficher le rapport
d'anomalies, unifier les sévérités.

---

*Les points non contre-vérifiés individuellement sortent d'une
exploration statique : re-vérifier chaque référence avant de corriger
(règle backtest : tout changement moteur reste généraliste et passe par
les backtests).*
