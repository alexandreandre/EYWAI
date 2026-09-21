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
5. **Doublons d'août sur le test** (annulés le 18/09) : Bugny 10 j + 12 j sur les
   mêmes jours, Gautheron 4 j + 10 j, Espinosa 13/07 deux fois — s'assurer que la
   prod ne porte pas les mêmes (la reprise CP y est encore au 31/08, calibrée
   dessus si c'est le cas).

### 4. Défauts connus non traités

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
  jours ; avertissement `jours_hors_fenetre` sinon), revue pré-paie (anomalie
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

Restent les pas 2 (front : dialogue de refus daté, bloc fenêtre dans la
régénération unitaire, « à régénérer » quand la fenêtre change) et 3 (mois de
paie affiché par semaine à l'import).

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
