# Reprise de paie EYWAI — contexte pour continuer le travail

Tu reprends un chantier en cours sur EYWAI, un moteur de paie français. Lis tout
ceci avant d'agir. Rien n'est commité, la branche est `fix/payslip-edit-state`.

## Le sujet

Colorplast est un client de plasturgie (IDCC 292). Gaëlle, la gestionnaire, a fait
elle-même la paie de janvier à juin 2026 dans Quadra (Cegid) — **il n'y a pas de
cabinet**, si un document parle du « cabinet » il s'agit d'elle dans Quadra. On doit
reprendre sa paie à partir de juillet 2026 sans casser ses cumuls.

On a d'abord rejoué janvier à juin depuis les pièces sources pour la contrôler. Puis
on a compris que c'était le mauvais objet, et on a tranché une architecture :

> **Deux modes qui ne se mélangent jamais.** Le *rejeu* sert à auditer un prestataire
> ou à démarrer une société au 1er janvier. La *reprise* traite le passé comme une
> donnée d'entrée, jamais comme un calcul : un solde d'ouverture importé à une date
> de bascule, qui fait foi, et les mois d'avant affichés en lecture seule.

Le piège explicitement écarté : viser le centime sur chaque ligne du passé revient à
implémenter la méthode de Quadra partout où elle diffère, donc à en faire un clone,
erreurs comprises.

## Règles permanentes données par Alexandre

- Si Quadra se trompe, on ne reproduit pas son erreur, on l'enregistre comme constat.
- Si c'est la règle légale, on corrige le moteur pour de bon, avec des tests.
- **Ne jamais commiter sans demande explicite.** Rien n'a été commité.
- `data/` est dans .gitignore.
- Un ajustement légitime est une **donnée saisie** (des heures, une absence, un
  montant) que Gaëlle taperait pareil chez nous. Un ajustement qui change une **façon
  de calculer** n'est pas un ajustement : c'est soit notre bug, soit son erreur, et ça
  se tranche.

## Environnement

- Racine : `/Users/alex/Documents/Alexandre/01 Projets/EYWAI/EYWAI`
- Interpréteur : `backend/.venv/bin/python` (toujours celui-là)
- Tests : `cd backend && .venv/bin/python -m pytest -q` — **7 538 passent** (le
  18/09 au soir), et **2 échouent pour l'environnement local, pas pour le code** :
  `test_app_env_defaut_est_prod` et `test_api_failure_manual_fallback`. C'est normal.
- Lint : `.venv/bin/python -m ruff check <fichiers>`. Ne linte pas tout
  `app/modules/payroll/`, 8 erreurs préexistantes y traînent dans des fichiers
  qu'on n'a pas touchés (`backtest/comparator.py`, `diagnosis.py`, `rubric_map.py`,
  `exports/dsn.py`, et une annotation `Optional` non importée dans
  `engine/controles_convention.py:446`, inoffensive car annotations différées).
- Supabase : projet **TEST** via les outils MCP `supabase-eywai-test`.
- Colorplast `company_id` = `dbe2b9f5-44dd-41bc-a625-36ed33d160f7`
- Les fichiers `backend/app/runtime/payroll/data/employes/TEST_MIG_*` apparaissent
  modifiés : c'est du bruit produit par la suite de tests, ne pas commiter.

## Ce qui est fait

### L'invariant de bascule dans le moteur

Le passé n'entre dans le moteur que par **un seul canal** : la colonne `cumuls` de
`employee_schedules`, lue à exactement deux endroits,
`payroll/documents/payslip_generator.py` (~ligne 538) et son jumeau forfait
`payslip_generator_forfait.py` (~ligne 168). Tout le reste en découle.

- Migration `supabase/migrations/20260917090000_reprise_paie_bascule.sql`, **appliquée
  sur test** : table `company_payroll_takeover` (une ligne par société :
  `cutoff_year`, `cutoff_month`, `source`, `previous_software`, `note`) et colonne
  `payslips.origine` ∈ {`calcule`, `importe`}.
- Module `backend/app/shared/reprise_paie.py`. Il ne lève rien, il renvoie des
  raisons de blocage, comme `payroll_block_reason`. Deux règles :
  `raison_de_blocage_avant_bascule` refuse tout mois ≤ bascule ;
  `raison_de_cumul_manquant` transforme un cumul absent en erreur dure, sauf pour le
  tout premier bulletin d'un salarié, seul cas légitime de départ à zéro.
- Câblé dans `payslips/application/commands.py` (`generate_payslip`, à côté des
  gardes existantes) et dans les deux générateurs, là où le repli silencieux à zéro
  se trouvait.
- 18 tests : `backend/tests/unit/shared/test_reprise_paie.py`.

### La reprise Colorplast au 30 juin 2026

Bascule posée en base : Colorplast est reprise depuis Quadra au 30 juin. Janvier à
juin **refusent de se recalculer**, vérifié via la vraie commande de génération.

Deux scripts, **simulation par défaut**, `--apply` pour écrire :

1. `backend/scripts/reprise_colorplast_solde_ouverture.py` — écrit le solde
   d'ouverture dans `employee_schedules.cumuls` de 06/2026. Les sept actifs sont
   alignés au centime sur Quadra. La somme des bruts mensuels contrôle le brut
   cumulé avant toute écriture. Deux dérivations à connaître :
   - `cumul_pss_agirc_arrco` = somme des « Plafond Sécu » mensuels. Concorde pour 5
     sur 7 ; Léo Cotte et Anthony Gautheron diffèrent, ce sont les deux qui ont eu
     des absences (proratisation du plafond, sujet non tranché).
   - `hs_exonerees_ir_cumul` = cumul imprimé × (1−0,097×0,9825)/(1−0,068×0,9825).
     Quadra n'imprime qu'un compteur d'heures sup exonérées (brut des HS moins la
     seule CSG déductible) ; notre moteur en tient un second, le montant réellement
     défiscalisé, qui retire aussi la CSG/CRDS non déductible et sert à écrêter au
     plafond de 7 500 € (art. 81 quater CGI). Vérifié à 3 centimes près sur les deux
     salariés dont le brut concorde.
2. `backend/scripts/reprise_colorplast_import_litteral.py` — découpe les PDF Quadra
   par salarié (le lecteur connaît les pages de chacun) et les sert tels quels.
   **39 bulletins** de janvier à juin marqués `origine = 'importe'`, dont deux créés
   pour Chaleyssin et Da Silva Cardoso, anciens salariés qui n'ont touché qu'une
   participation 2025 en mai et n'avaient pas de bulletin chez nous. Quadra tronque
   les matricules à dix caractères, d'où l'appariement par préfixe.
   `payslip_data` garde notre rejeu sauf `salaire_brut`, `net_a_payer` et `cumuls`,
   alignés sur le PDF, plus un bloc `reprise` qui dit quelles sections ne font pas foi.

Lecteur des PDF Quadra : `backend/scripts/backtest/colorplast_lignes_quadra.py`,
`lire_bulletins(annee, mois)` puis `.lignes`, `.droite`, `.net`, `.cp`, `.pages`.
Piège : Quadra utilise **deux libellés** pour les heures sup, « H. supp majorées à
25 % » pour les 17,33 h structurelles et « Heures supplémentaires 25/50 » pour les
réelles. Un filtre qui n'attrape que le premier sous-estime de moitié.

### État de la base test pour Colorplast

| Période | Contenu | Origine | Verrou |
|---|---|---|---|
| 01 à 06/2026 | 39 bulletins, PDF de Quadra découpés | importé | oui |
| 30/06/2026 | compteurs de Quadra, alignés au centime | importé | oui |
| 07 à 09/2026 | 13 bulletins, les nôtres | calculé | non |
| Congés | reprise au 30/06/2026 pour les sept (écarts N-1, N = 0), demandes d'été nettoyées | importé | — |

La chaîne des cumuls est **juste au centime de juin à septembre** : chaque mois vaut
le précédent plus le brut du mois.

**Piège majeur du rechaînage.** Le générateur n'écrit que le cumul du mois demandé,
il n'existe aucune cascade. Changer le solde d'ouverture oblige à régénérer juillet,
août, septembre **dans l'ordre**, et il faut
`force_calendrier_incomplet=True, regenerer_bulletin_valide=True` : sinon juillet est
refusé et août se reconstruit sur un juillet périmé, ce qui donne une chaîne
cohérente mais fausse. La régénération ne change **rien** au contenu des bulletins,
seulement aux cumuls (vérifié sur quatre salariés).

### Deux bugs moteur corrigés

1. **Remise à zéro de janvier.** Le générateur lit délibérément décembre N-1 pour
   produire janvier, et six compteurs n'étaient jamais remis à zéro. La réduction
   générale partait donc du brut de toute l'année précédente et pouvait rembourser
   la réduction de l'an dernier. Le correctif est **double**, et c'est le point
   important : une garde **à la lecture** (une remise à zéro à l'écriture n'y change
   rien puisque c'est décembre qui est lu) dans
   `calcul_reduction_generale._lire_cumuls_precedents` et dans le plafond apprenti de
   `calcul_net._base_pas_du_mois`, même patron que l'Agirc-Arrco et le plafond des
   HS ; et une remise à zéro **à l'écriture** dans
   `payslip_run_common.mettre_a_jour_cumuls` pour que le bulletin de janvier imprime
   un cumul d'année civile.
   `brut_total` est **volontairement exclu** : il sert aussi la prime de précarité et
   l'IFM (fenêtre du contrat) et la base du dixième des congés (1er juin au 31 mai).
   9 tests : `backend/tests/unit/payroll/test_remise_a_zero_janvier.py`, dont un qui
   relit le code source pour signaler tout compteur ajouté ou retiré.
   Vérifié en base : aucune société n'avait un cumul de décembre suivi d'un bulletin
   de janvier, le bug n'avait jamais tourné. Il s'allumait au passage à 2027.

2. **Phrase d'arbitrage des congés fausse.** `bulletin.creer_bulletin_final`
   construisait la mention « calculée selon la règle X, plus favorable que Y » en
   balayant les libellés au lieu d'utiliser la méthode que l'arbitrage renvoie déjà.
   L'indemnité du mois arrive en deux lignes qu'il écrasait au lieu d'additionner, et
   l'indemnité compensatrice de fin de CDD écrasait tout : le juillet de Cédric
   Demory annonçait la règle du dixième à 876,74 € face à un maintien de 98,48 €,
   deux grandeurs sans rapport. Montants justes, seule la phrase mentait, sur un
   point opposable. 8 tests :
   `backend/tests/unit/payroll/test_arbitrage_conges_texte.py`. Un seul bulletin sur
   les huit portant la mention était faux ; régénéré, montants inchangés.

## Ce qui reste, dans l'ordre

### 1. Compteurs de congés — FAIT (mois importés figés, reprise au 30/06 appliquée)

Précision sur le mécanisme, qui corrige ce qui était écrit ici : les soldes **sont**
stockés au bulletin, dans `payslip_data.pied_de_page.solde_conges`, posés à la
génération par `bulletin.build_solde_conges_pied_de_page` →
`get_absence_balances_for_payslip`. Ils ne bougent qu'à une régénération, que la
bascule interdit pour les mois importés.

**a. Mois importés figés (18/09).** `reprise_colorplast_import_litteral.py` copie le
bloc « CP N-1 / CP N » (Acquis, Total pris, Solde) de chaque PDF Quadra dans
`pied_de_page.solde_conges`, dans la forme que `bulletin_view.construire_compteurs`
lit ; `reprise.sections_copiees_du_pdf` le déclare. Les 39 bulletins importés portent
leurs compteurs Quadra. Rien de fabriqué pour les repos (Quadra ne les imprime pas).
6 tests : `backend/tests/unit/scripts/test_reprise_colorplast_import_litteral.py`.

**b. Reprise des congés au 30/06 (18/09), décidée par Alexandre.** Une reprise datée
du 31/08 (recalage du 12/09, feuille « compteurs fin août », idem en prod le 08/09)
laissait notre juillet sans compteurs et absorbait, dans ses écarts au théorique,
des saisies d'été en double. `backend/scripts/reprise_colorplast_conges.py`
(simulation par défaut, `--apply`, rejouable) a fait, dans l'ordre :

1. nettoyage des demandes par la commande applicative — trois doublons annulés
   (Bugny 10 j sur les mêmes jours que ses 12 j, Espinosa 13/07 en double,
   Gautheron 4 j sur les mêmes jours que ses 10 j) et `jours_payes` réaligné sur ce
   que le bulletin a payé (Espinosa août 15, Gautheron 13/07 et 21/07 à 1, Fuckar
   août 12). `jours_payes` est un plafond posé à la validation sous le solde de
   l'époque ; le moteur paie les jours du calendrier, seul le compteur le lit ;
2. `apply_cp_solde_import(month=6)` pour les sept : `cp_opening_reference_date =
   2026-06-30`, écarts N-1 Bugny +15, Cotte 0, Demory −3,22, Espinosa +4, Fuckar
   −1,67, Gautheron −10, Girerd +2 ; N = 0 partout (le théorique de juin vaut
   exactement 2,08) ; RTT 0 ;
3. régénération de juillet → septembre dans l'ordre (13 bulletins,
   `force_calendrier_incomplet`, `regenerer_bulletin_valide`) ; le juillet
   d'Espinosa portait un `manually_edited` périmé (historique fait uniquement de
   régénérations, brut et net identiques depuis le 14/09), régénéré par dérogation
   documentée dans le script ;
4. contrôle : brut, net et cumuls inchangés sur les 13 ; **juillet et août égalent
   les bulletins Quadra** (soldes et jours pris) pour Bugny, Cotte, Espinosa,
   Gautheron, Girerd. Sauvegardes d'avant dans le scratchpad de la session
   (`avant_ajustements_conges.json`, `avant_bulletins_7_9_complets.json`).

Deux constats laissés tels quels :
- **Fuckar, août** : Quadra a payé 10 j de CP et mis 17–18/08, 24/08 (½), 28/08 (½)
  et 31/08 en congés sans solde ; nous avons payé 12 j de CP, rien pour les trois
  derniers jours, et une « absence injustifiée » de 0,9 j le 19/08. Écart de paie
  d'août, à traiter dans le rapprochement de juillet-août, pas un écart de compteur
  (compteur N : −2,43 chez nous, −0,43 chez Quadra, soit ces 2 jours).
- **Demory, bulletin de sortie de juillet** : Quadra imprime des compteurs à zéro
  (soldés par l'indemnité compensatrice), nous imprimons 2,78 / 4,16. Présentation
  du bulletin de sortie à trancher.

La prod porte toujours la reprise au 31/08 : à basculer de la même façon une fois
la doctrine validée ici.

### 2. Le rejeu d'audit a son espace — FAIT : le bac à sable de génération

**Le mécanisme (18/09).** Le générateur accepte un `bac_a_sable`
([bac_a_sable.py](../backend/app/modules/payroll/documents/bac_a_sable.py)) : les
cumuls du mois précédent viennent de l'appelant (`cumuls_de_depart`, zéro si rien
n'est fourni, comme un premier bulletin), le calcul est strictement le même, et
**rien n'est persisté** — ni storage, ni `payslips`, ni `employee_schedules.cumuls`,
ni repos compensateur, ni prêts, ni mouvements de modulation ou de CET (drapeau
`persister=False` porté par `run_payslip_generation_heures` et
`apply_modulation_hour_account_to_calendar`). Le résultat rend `payslip_data` et
`cumuls` au lieu d'un identifiant et d'une URL. Entrée :
`payslip_generator_provider.generate_en_bac_a_sable(employee_id, year, month,
cumuls_precedents)`, relayée par `payslip_services` et `payslip_commands` (le
paramètre n'est transmis que s'il est fourni, les tests existants ne voient rien).
Le générateur forfait a le même mode. 8 tests : `tests/unit/payroll/test_bac_a_sable.py`,
`tests/unit/modulation/test_payroll_hook_persister.py`,
`tests/unit/payslips/test_bac_a_sable_provider.py`, et deux de bout en bout sur le
harnais de migration (`tests/migration/test_bac_a_sable_heures.py`, Supabase requis).

**Le script** `colorplast_regulier_test.py` chaîne ses six mois en mémoire
(`CHAINE`, `BULLETINS`), compare depuis la mémoire, ne relève et ne remet que
plannings, saisies, fiches et historique de salaire, et vérifie à la fin que
`payslips` et les cumuls sont identiques (`_verifier_la_chaine_intacte`). Plus de
`--garder`. Le relevé est écrit sur disque au départ ; `--remettre-depuis FICHIER`
rejoue la remise. Le rejeu « sur les entrées du cabinet »
(`colorplast_rejeu_test.py`) n'est **pas** converti : même conversion à faire s'il
doit retourner.

**Vérifié.** Janvier en bac à sable redonne les bruts documentés dans
`docs/colorplast-2026-rejeu-regulier.md` (Espinosa −23,02, Girerd +0,01, les trois
autres au centime), les écarts de champs sont les natures connues, et la chaîne est
intacte (50 bulletins, 84 cumuls). Les six mois, relancés en arrière-plan après
l'incident ci-dessous : **16 bulletins sur 37 au centime et exactement les écarts
de brut documentés**, aucune erreur, chaîne intacte, plannings et saisies remis,
fiche sans différence. La commande : `python -m scripts.colorplast_regulier_test
--apply --json-dir DOSSIER`, en arrière-plan (plus de dix minutes).

**Incident du 18/09, à connaître.** Le premier run des six mois a été lancé au
premier plan par l'outil de session, dont le timeout de 600 s a tué le processus
en mai, **avant la remise en état** ; les mois de janvier à mai sont restés dans
l'état régularisé de l'audit (plannings, `actual_hours` vidés, 5 saisies en
doublon effacées), la fiche dans l'état du setup de mai. La chaîne de paie n'a pas
bougé (bac à sable). Remise faite par le setup officiel (`apply_month` 1→5, puis
retrait des surcharges d'entrée) : fiches, réintégration mutuelle, prévoyance et
historique de salaire ressortent identiques à la sauvegarde ; le `salaire_de_base`
de Demory et Fuckar, que le setup de mai pose à 1 850,37, remis à 1 867,06 (leur
passage daté du 1er juin). Les plannings de janvier à mai sont donc à l'état du
setup (celui des saisies du cabinet), les saisies au complet du setup (95 lignes ;
il y en avait 80 avant, dont les doublons que l'audit efface). Aucun canal ne
mène de ces plannings à un bulletin futur : la recalcul des repos compensateurs
lit les bulletins, pas les plannings. Sauvegarde de l'état d'après-crash dans le
scratchpad (`etat_apres_crash_18-09.json`). Leçon : un script long se lance en
arrière-plan, jamais sous le timeout de l'outil.

### 3. Questions pour Gaëlle — seules données manquantes, consolidées le 18/09

À porter sur la page « Questions pour Gaëlle » de l'artefact (avec l'accord
d'Alexandre : la page est partagée).

1. **Saisie sur salaire d'Anthony Gautheron** (« Saisie SGC OYONNAX », 33,38 €,
   apparue en juin seulement) : montant total de la dette et déjà-retenu. Sans ça
   on l'arrête trop tôt ou trop tard, et c'est une obligation légale.
2. **Repos compensateur et récupération au 30 juin** : Quadra n'imprime pas ces
   compteurs (« Solde rep.remp. » et « Solde rep.récup. » vides) ; confirmer qu'ils
   sont à zéro. Point lié : chez nous, les crédits de repos compensateur (COR)
   se recalculent depuis les heures sup des **bulletins** de l'année — et pour
   janvier à juin ce sont celles de notre rejeu conservées dans `payslip_data`,
   pas celles de Quadra (Bugny affiche 15,82 h en août, Espinosa 23,11). Si les
   compteurs Quadra sont à zéro, les nôtres doivent le devenir aussi : à traiter
   comme une donnée de reprise, pas un calcul.
3. **Fuckar, août** : Quadra a payé 10 jours de congés (03→14/08) et mis 17–18/08,
   24/08 (½), 28/08 (½) et 31/08 en congés sans solde ; nos saisies portent 12
   jours de CP (03→18/08) et rien pour les trois derniers jours. Quelles journées
   étaient sans solde ? (Il n'avait que 9,57 jours ; Quadra en a payé 10 et laissé
   N à −0,43.)
4. **Bulletin de sortie d'Aurélien Demory (juillet)** : Quadra imprime les compteurs
   de congés à zéro (soldés par l'indemnité compensatrice) ; nous imprimons
   2,78 / 4,16. Quelle présentation veut-elle sur un bulletin de sortie ?
   **Et surtout l'indemnité compensatrice de CP (21/09)** : Quadra 940,23, nous
   876,74, tout l'écart de brut (63,49). Nous : 1/10 de la rémunération brute du
   contrat précarité comprise (6 197,76 + 1 772,64 + 797,04 = 8 767,44). Son
   940,23 suppose une base de 9 402,30 que rien ne redonne : ni ses cumuls
   (Bruts 9 707,67 moins l'ICCP = 8 767,44, la nôtre), ni le maintien sur ses
   compteurs (3,78 + 2,08 + juillet − 1 pris ≈ 7 jours × 98,48 ≈ 690 €). La
   précarité, elle, est identique (797,04), donc le brut du contrat aussi.
   Tranché le 21/09 avec son Excel : sa base mensuelle était fausse, le 940,23
   aussi ; nous appliquons la règle légale par période (§9), 766,39. Lui dire.
4 bis. **Semaine courte non compensée : retenue ou pas ?** Hugo Fuckar,
   juillet, données corrigées le 21/09 sur le test (10/07 journée travaillée
   de 7 h, 15/07 absence complète, 16/07 8,5 h comme Gaëlle l'a lu — Alexandre
   a tranché) : S28 −2,5 h, S29 +1,5 h, net −1 h. Gaëlle retient cette heure
   (portée en « absence » sur le 10/07) : brut 1 906,45. Notre option ne
   retient pas le solde négatif, elle l'écrit (« Solde non payé : −1 h ») :
   brut 1 919,10, écart 12,65 €. Aurélien Demory, S30 : 22/07 4,5 h et 24/07
   4 h sur la feuille (vérifié), net −5 h, et Gaëlle n'a rien retenu. Question
   pour elle : quand le mois finit en manque, retient-elle ou pas ? Si
   « toujours », l'option passera le solde négatif en retenue (un événement
   d'absence des heures nettes, comme les nets d'heures sup) — petit
   changement, spec à amender.
5. **Doublons d'août sur le test** (annulés le 18/09) : Bugny 10 j + 12 j sur les
   mêmes jours, Gautheron 4 j + 10 j, Espinosa 13/07 deux fois — s'assurer que la
   prod ne porte pas les mêmes (la reprise CP y est encore au 31/08, calibrée
   dessus si c'est le cas).

### 4. Défauts connus non traités

- ~~Indemnité de CP de fin de CDD : retrancher les congés déjà payés~~ — fait
  le 21/09, voir §9 (calcul par période sur les jours restants).

- **Aucune cascade** après régénération d'un mois : le générateur n'écrit que le mois
  demandé. L'invariant de bascule protège le passé, pas les mois postérieurs.
- **Indemnités de sortie** : `calcul_indemnites_sortie.py:60-99`, les références 12
  mois et 3 mois sont des ébauches marquées `TODO` qui renvoient le salaire de base
  courant. L'indemnité de licenciement ignore donc primes et variations de salaire.
  C'est du lourd, sans lien avec la reprise.
- `get_advances_to_repay` reçoit `year`/`month` mais ne les utilise pas : régénérer
  un bulletin passé applique le reliquat d'avance d'aujourd'hui.
- Proratisation du plafond de Sécurité sociale en cas d'absence : divergence avec
  Quadra non tranchée (Cotte et Gautheron).
- **Double facturation des congés au changement de période (1er juin).** Défaut de
  modèle, pas de reprise : `compute_cp_period_balances` pose
  `N-1 = acquis de la période précédente − jours pris pendant cette période`, alors
  que ces jours ont déjà été déduits du stock N-1 de l'époque. Exemple pur (entré
  01/01/2024, 20 j pris en août 2025, aucune reprise, période juin → mai) : au
  31/05/2026, N-1 10 + N 30 = 40 ; au 30/06/2026, N-1 = 30 − 20 = **10** + N 3 = 13,
  au lieu de N-1 30 (les 20 jours ont consommé le stock 2024-25, dont le reliquat
  de 10 est perdu) + 3 = 33. Tous les salariés de toutes les sociétés, à chaque
  1er juin. Le roulement des reprises (`rolled_n1 = … + taken_from_n1`) compense ce
  double compte pour les seules reprises. Corriger demande un vrai modèle par
  période (état de clôture d'une période = ouverture de la suivante) et une
  décision sur le **report du reliquat N-1** : Quadra le reporte (Bugny, juin 2026 :
  15 de reliquat 2024-25 + 25 acquis = 40), le moteur le perd. À trancher avec
  Alexandre avant d'y toucher ; chantier à part entière.
- **Le mode « fidèle au bulletin » est piloté par le texte de la note.**
  `rules._is_bulletin_cp_import` cherche « Import CP bulletin » dans la note de
  l'ajustement et `_bulletin_import_reference_date` y lit « <mois> <année> » ;
  dans ce mode, solde affiché = solde importé − jours pris depuis, sans acquisition
  (`_bulletin_faithful_cp_solde`, écrans RH et plafond `jours_payes` à la
  validation ; le bulletin N-1/N n'y passe pas). La reprise au 30/06 a remplacé
  cette note chez Colorplast, qui est donc passée au mode théorique (acquisition +
  écart) : cohérent avec le bulletin (Bugny 34,24 le 18/09 = 28 + 6,24), c'est le
  bon mode pour une société dont nous faisons la paie, mais c'est un changement
  implicite à valider. Le marqueur textuel lui-même est fragile.
- `manually_edited` n'est remis à zéro qu'après régénération forcée d'un bulletin
  **validé** ; un brouillon régénéré le garde, et l'historique plafonné à dix
  versions peut faire disparaître la retouche d'origine (Espinosa, juillet ;
  drapeau remis à zéro à la main le 18/09 après vérification de l'historique).
- ~~Les écarts de reprise des congés meurent au 1er janvier~~ **CORRIGÉ le 18/09** :
  `leave_settings_repository.resoudre_ajustement_applicable` — la ligne de l'année
  s'applique telle quelle, sinon les écarts CP de la reprise datée la plus récente
  suivent (RTT, JTC et note restent annuels) ; `get_applicable_adjustment` et
  `get_applicable_adjustments_by_employees` servent les calculs (`_leave_context`,
  `compute_balances_for_employee`, vue des soldes), l'écran de saisie garde
  `get_employee_adjustment`. `EmployeeLeaveAdjustment.cp_opening_reference_date`
  porte la date. 9 tests : `tests/unit/absences/test_ajustement_applicable.py`.
  Vérifié sur le test : Bugny N-1 28 au 31/01/2027 et au 31/05/2027.
- ~~Le roulement ignore la date de la reprise~~ **CORRIGÉ le 18/09** :
  `_resolve_cp_adjustment_for_ref_date` regarde `cp_opening_reference_date` — même
  période : écarts tels quels ; période suivante : roulement ; deux périodes plus
  tard : plus rien. Sans date, ancien comportement. Le roulement conserve
  désormais JTC et date (`dataclasses.replace`). 5 tests :
  `tests/unit/absences/test_reprise_datee_roulement.py`. Bugny : N-1 25 au
  30/06/2027 (roulé), 25 au 30/06/2028 (éteint).

### 5. Import des pointages S27–S30 du 19/09 sur le test — constat, correctif, suite

Alexandre a importé quatre feuilles (S27 à S30) en une fois sur le test (lot
`4c3ae0aa`, 120 jours, 21:04). Relecture case par case des quatre PDF : 94 cases
justes sur 120, 24 mal lues, 2 illisibles.

- **Bug de persistance, corrigé** (commits `c0341a90` persistance, `485e2f9c`
  orientation, `0acc5d0e` scripts, `23970e66` front, `a00bfaa1` docs sur
  `fix/payslip-edit-state`, poussés et déployés sur le test le 19/09 au soir) :
  `commit_batch_bulk`
  n'allait vers le chemin multi-mois que si le lot portait `month_groups`, ce que
  seul l'ancien `persist-timesheet` pose ; un lot du job groupé écrivait donc les
  jours par numéro dans le mois cible → les 29 et 30 juin de S27 ont écrasé les
  29 et 30 juillet de cinq salariés, et des heures négatives (Espinosa 16/07 :
  −10,5 h) sont passées. Désormais le commit répartit les jours par (année, mois)
  réel (`_employes_par_mois`, un upsert par mois, recalcul de paie par mois
  écrit) ; il refuse une heure négative (422 nommant salarié et jour,
  `jours_a_heures_negatives`, partagé avec `validate_persist_payload` du chemin
  legacy) ; l'extraction signale une heure négative dans les avertissements du
  salarié ; le front affiche la phrase du serveur au lieu de « L'enregistrement a
  échoué ». Tests : `tests/unit/schedules/test_commit_par_lot_mois_croise.py` (4),
  `test_timesheet_hybrid_extract.py` (+1). Le test garde le bug tant que la
  branche n'est pas poussée et redéployée.
- **Lecture** : S27 et S28 justes ; S29 et S30 fausses sur 24 cases — après le
  mardi 14 férié (hachuré ou vide), le vendredi glisse sur le jeudi et le vendredi
  reste à 0 (Michel, Léo, Anthony dont les heures deviennent négatives) ; « 16H »
  lu « 17H » ; décalages de colonne en S30. Deux cases de Marion illisibles
  (10/07 barré, 17/07 raturé) : question pour Gaëlle. La feuille
  `semaine-30.pdf` est titrée « S29 » à la main.
- **Correction des données, appliquée le 19/09 au soir** (sauvegarde des six
  lignes de juillet : `avant_correction_juillet_19-09.json` dans le scratchpad de
  session ; seul `actual_hours` a changé, contrôlé colonne par colonne) :
  `backend/scripts/correction_pointages_colorplast_juillet.py` (simulation par
  défaut, `--apply` n'écrit que `actual_hours`, relit, rejouable) a remis les 24
  cases à la feuille, retiré les 29–30/07 chez les cinq (leur réel de juillet
  était vide avant l'import, instantané du 18/09 ; Demory inchangé, il avait déjà
  8,5/8,5) et rien écrit en juin (mois repris, réel vide). Reste à faire, à la
  main d'Alexandre : régénérer les bulletins de juillet (brouillons, aucun
  régénéré depuis l'import).
- **Origine des heures négatives, et garde-fou** : le modèle de vision lit
  lui-même des cellules mélangées (Anthony jeudi S29 : debut « 16H30 », fin
  « 6H ») et rend son propre calcul (−10,5) ; le serveur recalculait, trouvait la
  plage incohérente… et gardait la valeur du modèle.
  `normalize_handwritten_weekly_payload` met désormais `heures` à `null` et pose
  l'avertissement `plage_incoherente` (nom, jour, plage), visible à la relecture
  (`test_handwritten_weekly.py`, +1).
- **Jeu d'or posé** : `tests/fixtures/timesheets/colorplast_2026_s27_s30_attendu.json`
  (120 cases attendues, `null` = pas d'heures, « illisible » pour les deux cases
  de Marion) et `backend/scripts/pointages_jeu_d_or_colorplast.py`, qui relit les
  quatre feuilles avec le pipeline réel (semaine ancrée, pause société, modèle du
  `.env` — la clé OpenRouter **est** renseignée en local, contrairement à ce que
  disait la mémoire) et compte justes / fausses / illisibles. À lancer en
  arrière-plan ; `--sortie` écrit le brut (jours lus par page, avertissements).
  C'est l'étalon de tout changement de prompt ou de pipeline.
- **Première mesure au jeu d'or (pipeline du soir, avant correction)** :
  102 justes / 16 fausses / 2 illisibles sur 120 — et un autre motif d'erreur
  que lors de l'import d'Alexandre (le modèle n'est pas déterministe). La trace
  brute a montré la vraie cause : **les images partaient de travers au modèle de
  lecture**. S29 (scan) partait à l'envers : l'OSD avait dit 270 pour une feuille
  à tourner de 90, le texte OCR était pauvre, et le dernier ressort — le modèle
  de vision — rendait toujours `None` : le schéma `{"type": "integer", "enum":
  [0, 90, 180, 270]}` fait répondre `{}` à gemini-2.5-flash via OpenRouter, en
  silence. S28 (photo) partait couchée : l'EXIF redressait la photo, et le
  court-circuit EXIF ne regardait plus si la feuille était posée de côté dedans.
- **Orientation corrigée** (`text_extraction.py`, 34 tests verts) : l'EXIF n'est
  plus qu'un point de départ (OSD, texte et modèle passent derrière) ; le modèle
  ne reçoit plus la question « de combien tourner ? » — mesuré sur S28 et S29
  dans les quatre sens, il répondait 270 à tout — mais une **mosaïque des quatre
  sens étiquetés A/B/C/D** dont il désigne la vignette droite : 16 réponses
  justes sur 16 (`_mosaique_des_quatre_sens`, `_rotation_pil_depuis_vignette`).
  **Jeu d'or relancé après correction : 115 justes / 3 fausses / 2 illisibles
  sur 120** (S29 redressée par la mosaïque, S28 par l'OSD). Les trois cases
  restantes, vues en gros plan : Hugo 24/07 « 7h → 12h00 » = 5 h, lue 10,5
  (erreur du modèle) ; Marion 09/07 « 6h → 7h » = 1 h, lue 0 (erreur du
  modèle) ; Marion 03/07 « 6h → 11h » ou « 6h → 14h », l'écriture est
  ambiguë — trois passages du modèle lisent 14h (7,5 h), ma transcription disait
  11h (5,0 h) et c'est **5,0 qui est écrit en base par la correction du soir** :
  à confirmer avec Gaëlle, la case est désormais marquée « à confirmer » dans le
  jeu d'or (comptée hors bilan, comme les deux illisibles).
- **Chantier qualité de lecture** : une fois l'image droite, il restera les
  erreurs de lecture propres au modèle (colonnes perdues, « 16H » lu « 17H »,
  photo où le tableau est petit) ; le jeu d'or les mesure. Piste la plus robuste
  si nécessaire : détecter la grille imprimée (les traits se détectent par
  projection sur un scan, moins bien sur une photo de biais) et lire par
  colonne de jour ou par cellule, ce qui interdit tout glissement.

### 6. Le garde-fou de génération juge la période de la paie, pas le mois civil (20/09)

Constat sur Michel : « Calendrier 07/2026 incomplet » pour les 27–31/07, que le
moteur ne lit pas (fenêtre des variables de juillet : **22/06 → 26/07**, S26–S30,
règle « avant-dernier vendredi » ; août : 27/07 → 23/08), et rien sur les
22–30/06 qu'il lit et qui sont vides. Spec :
`docs/superpowers/specs/2026-09-20-periode-a-saisir-pour-la-paie-design.md` ;
plan du pas 1 : `docs/superpowers/plans/2026-09-20-periode-a-saisir-socle-backend.md`.

Pas 1 livré en local (non commité) :
- `schedules/domain/periode_a_saisir.py` (pur) : jours manquants sur l'union
  mois civil ∪ fenêtre, **bloquants** dans la fenêtre, **informatifs** hors
  fenêtre, bornés par le contrat, mois civil seul pour un forfait jour ; la
  règle « jour prêt » est réutilisée, pas réécrite.
- `schedules/application/periode_a_saisir_service.py` : fenêtre par
  `resoudre_fenetre_variables`, une lecture de planning par mois couvert,
  contrat par `hire_date` / `exit_last_working_day` / `contract_end_date`.
- Trois consommateurs sur le même juge : garde-fou de génération (422 avec
  `fenetre`, `jours_manquants`, `jours_informatifs` ; forçage qui nomme les
  jours ; les jours du mois civil hors fenêtre ne bloquent pas et ne font pas
  d'alerte — la fin du mois civil dépasse la fenêtre tous les mois, une alerte
  permanente n'en est pas une, retour d'Alexandre du 21/09), revue pré-paie (anomalie
  datée), tableau de bord. `compute_row_status(..., a_saisir=)` garde les
  écarts d'heures. Au passage : `analytics_gestion` importait `is_forfait_jour`
  d'`ecart_rules` (un argument) et l'appelait avec deux — la vue « calendriers »
  plantait dès qu'un salarié est actif ; corrigé.
- Tests : 21 nouveaux (`test_periode_a_saisir`, `_service`, `test_ecart_rules`,
  `test_generation_gardes`, `test_preflight_anomalies`, `test_analytics_calendriers_periode`),
  suite complète 6 100 verts.
- Contrôle réel en lecture sur le test, juillet 2026 : les cinq (Bugny, Cotte,
  Espinosa, Fuckar, Gautheron) `a_saisir` sur **22/06–26/06, 29/06–30/06**,
  informatifs 27/07–31/07 ; Demory et Girerd `a_saisir` sur juin seulement ;
  Gautheron porte en plus le **10/07** (réel à 0 h sur un jour prévu — la case
  barrée, à demander à Gaëlle). Exactement ce que le moteur lit.

Pas 1 commité et déployé sur le test le 21/09 (`a553e25c`, `8dd11f32`,
`cbc31a53`).

Pas 2 livré en local (plan
`docs/superpowers/plans/2026-09-20-periode-a-saisir-front.md`) :
- backend : `bulletins_sur_une_autre_fenetre` (bulletins du mois calculés sur
  une autre fenêtre que l'actuelle, lus dans `payslip_data.en_tete` ; importés
  et anciens moteurs ignorés), exposés par `GET/PUT /payroll-variables/period`
  (`bulletins_a_regenerer`, `employes_a_regenerer`) et comme anomalie pré-paie
  `fenetre_modifiee` (à vérifier, message « calculé sur 22/06 → 19/07 ; celle du
  mois est 22/06 → 26/07 : à régénérer ») ;
- front : le 422 est lu avec ses détails (`RefusalDetails`), la lib
  `joursASaisir` regroupe les dates par semaine (« S26 : 22/06–26/06 »), le
  composant `JoursASaisirListe` (fenêtre, jours par semaine, jours hors fenêtre,
  lien « Compléter le planning ») est dans les deux dialogues de refus ; la
  régénération unitaire montre `BlocPeriodeVariables` en lecture avec « Modifier
  la fenêtre de juillet 2026 (pour toute la société) » qui déplie le réglage
  existant ; le bloc annonce « N bulletins déjà générés gardent l'ancienne
  fenêtre » quand le serveur en compte ; libellés et types pré-paie complétés
  (`fenetre_modifiee` → « Fenêtre modifiée », renvoi vers `/payroll`).
- Tests : backend +6 (`test_bulletins_sur_une_autre_fenetre`, pré-paie +1),
  front +5 (vitest 57 verts sur `features/payroll`), eslint et tsc propres.

Pas 2 commité et déployé sur le test le 21/09 (`104b4d0e`, `9a3c6fb9`, `4894e780`).

Pas 3 livré en local : dans l'import de pointages, le sélecteur « Semaine »
propose les semaines de la **fenêtre du mois cible et du mois civil**
(`payrollWeekOptions`, lue par `usePeriodeVariables`) — pour juillet
Colorplast : S26 à S31 — et suffixe celles qui sortent de la fenêtre
(« S31 · 27 juil. – 2 août → paie d'août ») ; une note rappelle que leurs jours
seront enregistrés à leur date. Sans fenêtre ou en mois civil, rien ne change.
Tests vitest +4 (`importWeekOptions`, `importWeekAssignments`).

Les trois pas de la spec sont faits.

**Saisie de S26 et S27 sur le test (21/09, par le même chemin de code que les
routes `start-batch` → relecture → `persist-timesheet`, en local contre la base
test)** : 60 jours écrits pour Bugny, Cotte, Demory, Espinosa, Fuckar,
Gautheron — 22–26/06 et 29–30/06 dans juin, 1–3/07 dans juillet, le reste de
juillet intact. Lecture du modèle : S27 juste sur 30 cases, S26 sur 25 ; six
corrections de relecture appliquées (Michel 25/06 9,5 et 26/06 6,5 ; Anthony
26/06 5,5 ; Aurélien 25/06 8,5 ; Marion 25/06 7,5 — annotation « −1h » en rouge
que le modèle ignore — et Marion 03/07 gardée à 5,0). **Girerd n'est sur aucune
feuille** : son juin reste vide, juillet reste « à saisir » pour lui — comment ses
heures sont-elles pointées ? Question pour Gaëlle.

Trois bugs trouvés en le faisant, corrigés (tests, non commités à cet instant) :
1. `persist-timesheet` avec un `batch_id` **ignorait les cases corrigées à
   l'écran** (le lot était commité tel quel) : `appliquer_revue_au_lot` remplace
   d'abord les jours relus dans l'aperçu (`test_revue_appliquee_au_lot`, 3).
2. Le **cache d'aperçu par empreinte** ne connaissait pas la semaine ancrée : le
   même fichier réimporté sur une autre semaine ressortait avec les dates de la
   première. `week_anchor_date` fait partie de la proposition et de la clé du
   cache (`test_timesheet_preview_cache`, +1).
3. Un aperçu resservi depuis le cache **gardait son rapprochement figé** : un
   salarié absent du roster à la première extraction (Demory, sorti le 24/07,
   hors « actifs ») restait « texte OCR non salarié » à chaque réimport.
   `rematch_proposal_employees` refait le rapprochement avec le roster du jour
   (`test_apercu_en_cache_rerapproche`, 3). À vérifier côté front : la page
   Plannings met-elle les partis du mois dans le roster de l'import ?

**Heure manquante sur une semaine courte (Cotte, 24/07, 38 h pour 39)** : le
moteur étale déjà les heures à la semaine et retient le reste ; Gaëlle compense
entre semaines sur sa fenêtre. Décision prise le 21/09 : une option société,
voir §7. À noter aussi que les heures sup des bulletins de juillet sur le test
sont sa saisie recopiée, pas nos feuilles (Cotte : 8 h saisies contre 1,5 à 3 h
calculées).

### 7. Option société « compensation des heures entre semaines » (21/09) — construite, non commitée

**La décision.** Alexandre : « je veux qu'on puisse cocher l'option pour faire
la paie comme Gaëlle. C'est pas grave si c'est illégal, c'est un logiciel
interne à eux. » La règle légale reste hebdomadaire (heures sup et absences
semaine par semaine) ; l'option est un choix explicite de l'entreprise, nommé
pour ce qu'il est, désactivée par défaut — rien ne change pour les autres
sociétés ni pour Colorplast tant qu'elle n'est pas cochée.

**La règle, lue dans son classeur** (`data/colorplast/variables/2026-06/
detail-heures-sup-06-2026-colorplast.xlsx`) : écart journalier faites − prévues ;
par semaine `majo25 = min(TOTAL, seuil25)` (négatif compris) et
`majo50 = max(TOTAL − seuil25, 0)`, avec `seuil25 = 43 − durée hebdo` (4 h à
39 h) ; par paie, somme des semaines de la fenêtre des variables, semaines
négatives comprises ; si le net à 25 % est négatif il mange le net à 50 %, le
reste n'est ni retenu ni reporté, seulement dit. Recette : juin 2026 redonne
Bugny 14 h/7 h et Fuckar 4 h/3 h (semaines +2, +4, +7,5, +7,5 et −5, +7, +1, +4).

**Où ça vit.** Spec `docs/superpowers/specs/2026-09-21-compensation-heures-entre-semaines-design.md`,
plan `docs/superpowers/plans/2026-09-21-compensation-heures-entre-semaines.md`.
- Domaine pur : `backend/app/modules/payroll/application/compensation_semaines.py`
  (`ecarts_par_semaine`, `compenser`, `appliquer`, `appliquer_aux_mois`,
  `mention`, `option_active`), 23 tests dans
  `tests/unit/payroll/test_compensation_semaines.py`.
- Générateur (`payslip_generator.py`, juste après la résolution de la
  fenêtre) : `if option_active(company_data)` → remplace, dans les événements
  de M et M-1 datés dans la fenêtre, les `travail_hs25/50` et
  `absence_injustifiee_*` par les nets datés du dernier jour de la fenêtre ;
  congés, fériés, arrêts et régularisations antérieures ne bougent pas ;
  résumé déposé dans `saisies/MM.json["compensation_semaines"]`.
- Moteur : `payslip_run_heures` → `contexte.compensation_semaines` →
  `bulletin["compensation_semaines"]` (détail par semaine, nets, solde) ;
  `bulletin_view` ajoute une ligne « note » avant le brut, comme l'arbitrage
  CP : « Heures compensées entre semaines (option société) : S27 +1,5 · S30
  −1,0 → 0,5 h à 25 %, 0 h à 50 %. »
- Réglage : `companies.settings.compensation_heures_entre_semaines`, booléen
  déclaré dans `CompanySettingsUpdate` (PATCH `/api/company/settings`, une
  chaîne est refusée). Front : carte `CompensationSemainesSettingsCard`
  (onglet Paie de la société, section « Organisation du temps & compte
  d'heures », case + avertissement + Enregistrer).

**Comment l'activer pour Colorplast** : Société → Paie → « Organisation du
temps & compte d'heures » → carte « Compensation des heures entre semaines »
→ cocher → Enregistrer ; puis régénérer les bulletins du mois. Ou :
`PATCH /api/company/settings {"compensation_heures_entre_semaines": true}`.

**Hors périmètre, dit dans la spec** : le compteur de récupération entre mois
(report d'un solde négatif ou d'heures non payées), les journées « en récup »
et la journée de solidarité que Gaëlle saisit à la main.

**Recette du 21/09 en bac à sable (juillet, rien d'écrit, option simulée en
remplaçant `option_active` dans le module du générateur)** — brut option
désactivée → activée :

| Salarié | Brut OFF | Brut ON | Ce qui change |
|---|---|---|---|
| Bugny | 3 162,97 | 3 162,97 | rien : les 19 h/6,5 h saisies à la main priment ; la compensation calculée (S26 +4,5 · S27 +5,5 · S28 +7 · S29 +3 · S30 +3,5 → 18,5 h/5 h) n'est que dite |
| Cotte | 2 562,87 | 2 576,41 | +13,54 : l'heure manquante du 24/07 n'est plus retenue ; les 8 h saisies priment sur les 2 h calculées (S27 +1,5 · S29 +1,5 · S30 −1), la mention le dit |
| Demory | 3 370,05 | 3 446,42 | +76,37 : les absences des 22 et 24/07 (63,12) ne sont plus retenues, précarité et ICCP suivent ; S30 −5 h, « solde non payé : −5 h » |
| Fuckar | 1 881,22 | 2 014,96 | +133,74 : 5 h à 25 % (76,94 ; S28 +2,5 · S29 +2,5, le travail du 10/07 prévu « absence » compense les manques des 7 et 8/07), plus d'absence injustifiée (49,73) et réduction des HS structurelles moindre (7,07). Restent, option ou pas : « absence non rémunérée » des 15/07 et 20/07 (171,24) — prévues en absence au planning, **à vérifier avec les feuilles** |

Lecture : Cotte et Demory rejoignent Quadra sur les retenues d'absence (les
deux écarts relevés au §5) ; les heures sup restent celles saisies à la main
quand il y en a — l'option ne remplace pas la saisie, elle l'accompagne.
Fuckar montre l'effet de bord attendu : l'écart journalier ignore les jours
non travaillés prévus, là où le compteur hebdomadaire les compte à 0 h (le
manque connu de [[defauts-moteur-paie-revus]]).

**État** : commité le 21/09 (a2c7e6ca backend, ed36a7be front, e7fa1cd0 docs)
et déployé sur le test ; à la demande d'Alexandre, l'option est cochée le
21/09 sur la base test pour toutes les sociétés sauf MAJI et Zone 404 Mars
(Cartol, Colorplast, Comitech, LEWIS, Mont Blanc). Pas touché à la prod, où
le code n'est pas déployé. Suites :
backend 6141 verts (un rouge d'environnement), vitest 592 verts, eslint propre,
tsc avec ses 3 erreurs préexistantes hors périmètre.

### 8. Le PDF imprimait les cumuls de la génération précédente (21/09) — corrigé

Constat sur Cotte, juillet : corps du bulletin à jour (brut 2 576,41, mention
de l'option) mais cumuls d'avant l'option (Bruts 17 030,93 = juin + 2 562,87,
Cumul heures 1 165,10…), alors que `payslip_data.cumuls` en base était juste
(17 044,47). Cause : après l'insertion du bulletin, le générateur fait rendre
un PDF « enrichi » par `payslip_editor.regenerate_pdf_from_data`, qui
**remplaçait les cumuls du bulletin par ceux lus dans `employee_schedules`**
pour le mois — encore ceux de la génération précédente, la ligne n'étant mise
à jour qu'ensuite. Tout bulletin régénéré dont les cumuls changent imprimait
donc des cumuls d'une génération en retard ; la base, elle, était bonne.
Correctif : `cumuls_pour_le_rendu` — les cumuls du bulletin priment, la base
ne sert qu'aux bulletins sans bloc cumuls (mois importés à la reprise) ;
tests `tests/unit/payroll/test_payslip_editor_cumuls.py`. En attendant le
déploiement, régénérer une seconde fois donne un PDF juste (la base a rattrapé).

### 9. Indemnité de CP de fin de contrat : la règle légale, par période (21/09)

Le matin, une option société « salaire rétabli, congés N-1 inclus » avait été
construite pour retomber sur les 940,23 de Demory ; sa décomposition tombait
au centime par coïncidence. L'Excel de Gaëlle (reçu l'après-midi) a montré une
base mensuelle fausse : le 940,23 est une erreur de sa part. L'option est
retirée (code, réglage, carte, docs) et de Colorplast sur le test.

À la place, la règle légale, qui est aussi la deuxième formule de Gaëlle :
pour chaque période de référence, le plus favorable du dixième (10 % de la
rémunération brute de la période, précarité comprise, × restants/droits) et
du maintien (restants × valeur du jour). Les jours déjà pris ne sont pas
repayés. Spec `docs/superpowers/specs/2026-09-21-indemnite-cp-fin-de-contrat-legale-design.md`,
plan `…/plans/2026-09-21-indemnite-cp-fin-de-contrat-legale.md`.

- Pur : `engine/iccp_fin_contrat.py` (13 tests). Moteur :
  `calcul_brut._calculer_iccp_cdd` calcule par période quand le run a posé
  `contexte.cp_fin_de_contrat`, sinon repli sur le dixième global (détail
  `methode: dixieme_global`). Run : `cp_fin_de_contrat` au dernier mois d'un
  CDD ou d'une mission — compteurs du pied de page (droits = pris + solde, pas
  `acquis`), rémunération de la période précédente lue dans les cumuls du
  dernier mois de cette période (mai : 4 171,35), sinon somme des bulletins,
  sinon maintien seul. Bulletin : note par période, `payslip_data.indemnite_cp_fin_contrat`.
- Recette Demory : 2025-2026, 2,78 j sur 3,78 → dixième 306,78 (maintien
  273,77) ; 2026-2027, 4,16 j → 459,61 (maintien 409,68) ; total 766,39 contre
  876,74 (dixième de tout, le jour du 13/07 repayé) et 940,23 chez Gaëlle.
- Reste : l'acquisition du mois de sortie (nos compteurs 4,16 j pour N, Gaëlle
  1,66 pour juillet) est une question des compteurs, pas de l'indemnité.

### 10. Les points à arbitrer ne sont plus des alertes orange (21/09)

Retour d'Alexandre sur le plafond transport d'Espinosa (700 € versés en 2026
pour 600 € exonérables) : « on peut pas être plus discret, au lieu d'une énorme
phrase et plein d'orange ? ». Le contrôle est juste (prime forfaitaire, plafond
URSSAF 600 €, Quadra exonère tout, Girerd est à 2 000 € par an) et il ne parle
qu'une fois par an, mais il sortait comme une alerte.

- Moteur : une alerte peut porter `a_arbitrer=True` (`_alert`) ; le plafond
  transport l'a, avec un message d'une phrase : « Indemnité de transport :
  700,00 € versés en 2026 pour 600,00 € exonérables, excédent 100,00 € à
  arbitrer (bulletin inchangé). » `avertissements_de_generation` renvoie ces
  points en `{code, severity: "info", message}` et les alertes en chaînes comme
  avant ; `extraire_messages_alertes_rh` (listes) en dérive ;
  `payslip_list_meta` sépare `warnings` et `points_a_arbitrer`.
- Front : `splitGenerationWarnings` rend `infos` à part ; le journal de
  génération garde le statut « c'est fait » et ajoute « · à arbitrer : … » en
  gris ; la modale compte « N points à arbitrer » en gris, hors des alertes ;
  la liste des bulletins montre un badge gris « À arbitrer » avec le détail au
  survol. Les alertes non critiques mais à corriger (classification manquante,
  grille vide…) restent en orange.
- Question pour Gaëlle : cette indemnité est-elle un forfait (plafond) ou des
  kilomètres justifiés (pas de plafond) ?

### 11. Gautheron et Girerd, juillet : calendriers complétés, recette (21/09)

- **Girerd** : horaire fixe, pas de pointage ; le réel du 22 au 30/06 manquait
  (fenêtre). Rempli au prévu sur le test. Généré : brut 3 855,98 = Quadra.
- **Gautheron** : le 10/07 manquait (case barrée sur la feuille S28, 0 h).
  Quadra ne retient rien ce jour-là : rempli à 5 h sur le test, **à confirmer
  avec Gaëlle**. Généré : brut 2 203,63 contre 2 089,06, écart 114,57, tout
  sur des absences déclarées que le moteur ignore quand la journée porte aussi
  des heures faites : 09/07 (absence de 7,5 h, 1 h faite) 88,45 + sa part d'HS
  structurelles ; 20/07 (0,26 h) et 23/07 (0,75 h), écritures de Gaëlle pour
  des retards, 12 €. **Ce n'est pas un défaut du moteur** : il retient une
  absence partielle quand le jour porte une quotité (`quotite_absence` < 1,
  posée par le module des absences pour les demi-journées) ; les jours
  importés de Quadra n'en avaient pas, le moteur lisait une absence de journée
  contredite par des heures faites et gardait les heures. Quotités posées sur
  les trois jours (7,5/8,5 ; 0,26/8,5 ; 0,75/8,5) : brut 2 088,90, Quadra
  2 089,06 (16 centimes d'arrondi sur les HS structurelles). Régénéré.
  Limite à noter : l'application ne sait saisir une absence non rémunérée
  partielle qu'en demi-journée, pas en heures (`heures_par_jour` est réservé
  aux repos).
- L'option de compensation mesure désormais l'écart d'un jour d'absence
  déclarée partielle à ce qui restait dû (spec amendée, 4 tests) ; sans cela
  Marion aurait eu 16 h de surplus fantômes. Non commité.

### 12. Les bulletins importés sont intouchables (21/09)

Alexandre pouvait, depuis la démo, supprimer et modifier les bulletins de
janvier à juin repris de Quadra (`origine = importe`) ; seule la régénération
était refusée par le serveur. Désormais : suppression et édition refusées
côté serveur (`commands._refuser_si_importe`, même message que la bascule),
page d'édition verrouillée avec le motif (`period_edit_lock`, sans
contournement admin), et dans la liste un badge « Importé » avec les boutons
Modifier et Supprimer grisés mais visibles, motif au survol — à sa demande,
grisés plutôt que cachés.

### 13. Saisies sur salaire : jamais sur le bulletin, nom absent de la liste (21/09)

Marion Gautheron a une saisie-arrêt (SGC Oyonnax, 46,49 par mois, juillet)
qui n'apparaissait pas sur son bulletin. Cause : dans l'enrichissement du
bulletin, la garde de doublon `get_existing_deduction` lisait `.data` sur le
retour de `maybe_single()`, qui vaut None quand aucune ligne n'existe — donc
dès qu'une saisie était à appliquer pour la première fois, tout
l'enrichissement explosait (exception avalée, `retenues_saisies` jamais posé).
Même défaut sur `get_existing_repayment` (avances). Corrigé, 3 tests. Après
régénération, la ligne « Retenues sur salaire 46,49 » sort et le prélèvement
est historisé. Liste RH des saisies : la réponse construisait `employee_name`
mais le schéma `SalarySeizure` ne le déclarait pas, FastAPI le retirait ; le
front retombait sur l'identifiant. Champ ajouté, 2 tests.

### 14. Rapprochement janvier→juillet avant la paie d'août par Gaëlle (21/09)

Lancé `scripts.backtest.colorplast_lignes` sur les sept mois (JSON dans le
scratchpad). Bilan :

**Le socle est bon.** Les cumuls au 30/06 (brut, heures, heures sup) sont
identiques à Quadra pour les sept salariés : août partira juste.

**Juillet (calculé) est cohérent**, trois écarts connus et assumés : Demory
indemnité de fin de contrat (766,39 contre 940,23, sa base était fausse,
§9) ; Fuckar 12,65 (l'heure manquante du mois qu'elle retient et que l'option
ne retient pas, question 4 bis) ; Gautheron 0,16 (elle tronque la réduction
des HS structurelles à 2,61 h là où la règle arrondit à 2,62).

**Janvier→juin : les bulletins importés ne sont pas des copies fidèles.**
1. **Aucun ne porte ses cumuls** (`payslip_data.cumuls` absent sur les 39) :
   la colonne de droite des PDF de janvier à juin est vide (heures période,
   cumul heures, cumul h. sup, bruts, net imposable cumulé, PAS cumulé, net
   HS exonérées cumulé). Gaëlle le verra au premier coup d'œil.
2. **Des lignes d'heures sup fausses**, surtout mai et juin, avec les
   cotisations qui en découlent : Bugny mai 4 h au lieu de 15 (brut de lignes
   2 755,99 contre 2 952,34 affiché, cotisations calculées sur le mauvais
   brut), Bugny juin 12 h au lieu de 14, Espinosa mai (25 % et 50 % inversés)
   et juin, Fuckar mai et juin, Gautheron avril, Cotte mars (absence
   événement familial). Le **brut affiché** et les **cumuls** restent ceux de
   Quadra : seule la décomposition est fausse.
3. **Des lignes de congés absentes** (Demory, Espinosa, Girerd en mai ;
   Gautheron en juin) et **des lignes en trop** (Gautheron avril : absence,
   complément de retenue, régularisation ; Cotte mai et juin : une ligne
   d'heures sup).

**Fait le 21/09 : l'import littéral copie plus que quatre champs.** Le script
`scripts/reprise_colorplast_import_litteral.py` ne reprenait du PDF que
`salaire_brut`, `net_a_payer`, `cumuls` et les compteurs CP ; le reste venait
du rejeu. Et son bloc `cumuls` était écrit **à plat** alors que tout le code
le lit imbriqué (`payslip_data["cumuls"]["cumuls"]`) : présent mais invisible.
Corrections (9 tests, `tests/unit/scripts/test_reprise_import_lignes.py` et
`…_cotisations.py`) :
- `_cumuls_affiches` rend la forme imbriquée, avec `periode` et `reprise` ;
- `_lignes_du_brut` construit `calcul_du_brut` depuis les lignes du PDF, avec
  nos libellés d'heures sup (l'aval les reconnaît par le libellé : contingent,
  repos compensateur, comparaison N/N-1) ; l'entête « Congés payés : … » est
  écartée, Quadra réimprime le même montant en « ARBITRAGE DES CONGES PAYES » ;
- `_asseoir_les_cotisations` / `_asseoir_la_structure` remettent la base des
  cotisations au brut du PDF et refont **les seules lignes qui sont un produit
  base × taux** — une ligne issue d'une formule (réduction générale) garde ses
  valeurs, la recalculer au taux affiché la fausserait (essai du 21/09 :
  584,81 au lieu de 552,97). Les totaux suivent par delta, pas par somme, pour
  ne pas présumer de leur convention de signe ;
- `_synthese_du_pdf` copie net imposable, net social, net des HS exonérées et
  le prélèvement à la source depuis le PDF.

Puis, dans le même mouvement (Alexandre : « la santé doit être bonne ») :
- `_copier_les_cotisations_du_pdf` : les cotisations dont le montant ne se
  déduit pas du brut sont copiées une à une depuis le PDF, en gardant **notre**
  signe — CSG déductible, les deux lignes de CSG/CRDS non déductible (appariées
  dans l'ordre du document), réduction générale, réduction salariale et
  déduction patronale sur heures sup ;
- `_pied_de_page_du_pdf` : l'allègement du mois et le total versé employeur
  viennent de la colonne de droite, ce sont des agrégats que nos lignes ne
  recomposent pas au même périmètre ;
- `details_absences` et `details_conges` sont **vidés** : leurs lignes sont
  désormais dans `calcul_du_brut`, repris du PDF. Sans cela les absences
  comptaient double (Gautheron avril : vingt lignes d'arrêt maladie du rejeu en
  plus des deux lignes du PDF). À noter : `dsn_export/domain/remuneration_map`
  lit ces deux sections ; les lignes restent disponibles dans `calcul_du_brut`.

**Résultat** (rapprochement rejoué sur les six mois) : écarts de montant de
**662 à 121**, dont **53 au centime près**. Quatre bulletins n'ont plus aucun
écart. Plus aucun bulletin sans cumuls, ni dont les lignes ne font pas le brut.

**Ce qui reste, et pourquoi ce ne sont pas des erreurs de nos données :**
- `TOTAL DES RETENUES` (31 lignes) : Quadra imprime la mutuelle famille
  **après** le net imposable, hors du total ; nous l'y comptons. Différence de
  présentation, vérifiée sur Espinosa janvier (476,68 contre 574,81 = +98,13,
  exactement la mutuelle).
- `net_avant_impot` : ce n'était **pas** une anomalie du PDF, contrairement à
  ce que j'avais d'abord écrit. Bugny a reçu un **acompte de 2 369,63** en
  janvier : Quadra imprime « NET A PAYER AVANT IMPOT » **après** déduction de
  l'acompte (2 508,65 − 2 369,63 = 139,02), là où notre `net_social_avant_impot`
  est le net avant acompte. Nos données portaient déjà l'acompte et le bon net
  à payer (75,58). C'est l'outil d'audit qui comparait deux grandeurs
  différentes : corrigé dans `colorplast_lignes.aplatir`. Les acomptes sont
  aussi repris du PDF par l'import (`_synthese_du_pdf`), janvier et mai en
  portent.
- **L'écart récurrent est 98,13 €, la mutuelle famille** : Quadra l'imprime
  après le net imposable, en négatif (« SMU2 GAN MUTUELLE FAMILLE −98,13 »),
  hors du total des retenues ; nous la comptons dans les retenues salariales.
  Elle explique 27 des écarts restants (10 sur le total des retenues, 17 sur
  le net avant impôt). Le **net à payer final est identique** des deux côtés.
  Différence de présentation, à trancher si on veut l'alignement.
- Restent une quarantaine d'écarts petits : contributions patronales
  regroupées par Quadra, réduction des heures sup structurelles de Gautheron,
  plafond proratisé des mois partiels (défaut connu, §4).

**État au 31/07, socle de la paie d'août** (vérifié salarié par salarié) :

| Salarié | cumul brut nous / Quadra | écart |
|---|---|---|
| Bugny, Cotte, Espinosa, Girerd | identiques | 0,00 |
| Demory | 9 533,83 / 9 707,67 | −173,84 (indemnité de fin de contrat, §9) |
| Fuckar | 7 853,36 / 7 840,71 | +12,65 (semaine courte non retenue, question 4 bis) |
| Gautheron | 13 186,79 / 13 186,95 | −0,16 (arrondi des HS structurelles) |

Heures et heures sup cumulées identiques pour les sept. Une reprise au 31/07
partirait donc d'un état conforme, aux trois écarts assumés près.

**Rappel utile** : le PDF servi pour janvier→juin est la **copie du document
Quadra** découpée par salarié. Ce que Gaëlle ouvre est donc exact ; les écarts
ci-dessus ne concernent que les données internes, lues par le contingent
d'heures sup, la provision comptable des CP et les comparaisons d'un mois à
l'autre.

## Le registre des variables dépendantes du passé

Un recensement exhaustif a été fait sur `backend/app/` : chaque endroit qui lit un
cumul, un mois antérieur, un solde reporté ou un compteur glissant, groupé par
domaine (réduction générale, plafond et tranches Agirc-Arrco, heures sup et plafond
7 500 €, prélèvement à la source, congés payés, maintien et arrêts, ancienneté,
mutuelle et prévoyance, net imposable, compteurs d'heures). Si tu as besoin du détail,
refais-le avec un agent Explore sur `backend/app/` — il n'a pas été écrit dans un
fichier du dépôt.

## Mémoire à lire

`/Users/alex/.claude/projects/-Users-alex-Documents-Alexandre-01-Projets-EYWAI-EYWAI/memory/`
et surtout `MEMORY.md` puis :
`reprise-paie-solde-ouverture.md`, `colorplast-solde-ouverture-30-juin.md`,
`invariant-de-bascule-reprise.md`, `arbitrage-conges-phrase-fausse.md`,
`rapprochement-colorplast-mois-par-mois.md`, `defauts-moteur-paie-revus.md`,
`colorplast-pas-de-cabinet.md`, `regeneration-mois-passes-test.md`,
`shell-local-app-env-test.md`.

## Artefact publié

La page « Colorplast au centime » (un tableau par mois, format Salarié | Ligne |
Nous | Quadra | Écart | nature, avec un « i » par ligne, un bouton copier et les
ajustements notés sous chaque mois) :
https://claude.ai/code/artifact/d7cb8056-1b52-4369-be37-02e156d1b15f
Ne pas changer ce format, c'est une consigne d'Alexandre. Cette page est désormais
un **document d'audit** de la paie de Gaëlle, plus la paie elle-même.
