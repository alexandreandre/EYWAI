# Retours de Gaëlle du 12/09/2026 — diagnostic et traitement

Source : groupe WhatsApp « MARTINE - MISE EN PROD », messages de Gaëlle du
12/09 (matinée, heure de Paris), avec quatre captures d'écran. Références
croisées : base de test (`tlvkjwleahkmuzcegrde`), bulletins Quadra de
Colorplast (`data/colorplast/bulletins/2026-05..07/`), code de la branche
`fix/payslip-edit-state`.

« Marion » et « Gautheron » désignent la même personne (Marion Gautheron,
Colorplast). Les horodatages de l'export WhatsApp sont en heure de New York :
« 02:18 » = 08:18 à Paris, ce que confirment les `updated_at` de la base.

## Vue d'ensemble

| # | Sujet | Verdict | Traitement |
|---|---|---|---|
| 1 | Compteurs CP à 2,08 et non 2,5 | réglage + arrondi du moteur | corrigé, à basculer sur le test |
| 2 | Allègement employeur 256,05 vs 321,37 (Girerd) | comparaison faussée par notre affichage | affichage corrigé ; écart réel 14,49 € non résolu |
| 3 | Absence de Marion : 0,23 × 13,143 ≠ 3,29 | montant non recalculé à l'édition + règle de valorisation fausse pour les journées ≠ 7,8 h | corrigés, moteur et éditeur ; deux absences à vérifier |
| 4 | Fuckar, fin de contrat au 15/09 « non enregistrée » | enregistrée, mais l'API ne renvoyait jamais le champ | modèle de réponse corrigé ; historique des CDD = chantier de fond |
| 5 | Bugny, Cotte, Espinosa : cotisations sans les HS corrigées | corrections jamais enregistrées (aperçu) | éditeur assoupli |
| 6 | Gautheron, saisie sur salaire : écran blanc | décimal en chaîne + aucune limite d'erreur | corrigé à l'API, à l'affichage, et limite d'erreur sur toutes les pages |
| 7 | Demory absent des bulletins de juin et juillet | filtre sur le statut « parti » | corrigé (liste, écran, garde) ; juillet généré, ICCP dans le brut |

## 1. Compteurs CP en jours ouvrés

Les sept sociétés étaient en jours ouvrables, 2,5 j/mois, arrondis à
l'entier supérieur chaque mois : Girerd affichait 5 à fin juillet, Quadra
4,16. Le réglage « jours ouvrés » existait mais ne changeait que l'étiquette :
l'acquisition restait 2,5 en interne.

Fait :

- `LeavePolicySettings` : le taux interne est le taux stocké dans l'unité
  choisie ; en ouvrés, pas d'arrondi mensuel (troncature au centième, 2 mois
  = 4,16, 3 mois = 6,24), arrondi à l'entier supérieur à la clôture de la
  période seulement (25 pour 12 mois, 9 pour 4 mois).
- `update_leave_settings` : changer d'unité pose le taux légal de l'unité
  (2,083 ou 2,5) quand l'écran renvoie l'ancien, et **réexprime les
  compteurs repris d'un bulletin** (`rebaser_reprises_cp`) : ces reprises
  sont stockées en écart par rapport au calcul théorique à leur date de
  référence, le solde du cabinet ne doit pas bouger quand le théorique bouge.
  Vérifié sur Girerd : N-1 écart −3 → +2, N écart −1,76 → 0, soldes repris
  inchangés (12 et 6,24 à fin août).
- `scripts/usines_jours_ouvres.py` : bascule les cinq usines de Gaëlle via
  la commande, lancé par `script-env-test.yml` le 12/09 à 20:31 UTC. MAJI
  et ZONE 404 ne sont pas touchées : à confirmer avec Vanessa (Elsa a
  demandé « toutes les boîtes ? », Gaëlle a répondu « jours ouvrés » pour
  son périmètre).

Les 271 reprises datées des sept sociétés (import des bulletins de mai,
recalage Colorplast fin août) passent par ce recalage automatique.

## 2. Réduction générale (Girerd, juillet)

Les 321,37 € lus par Gaëlle sont notre bloc « Allègement cotis. employeur »,
qui additionnait aussi la **réduction salariale** sur heures sup (50,84 €).
Quadra n'y met que le patronal : 256,05 = 230,05 (réduction générale) +
26,00 (déduction forfaitaire). Notre patronal vaut 244,54 + 25,99 = 270,53.

Fait : le pied de bulletin porte `total_allegements_patronaux` (patronal
seul) et le bloc l'affiche ; les bulletins déjà générés retombent sur
l'ancien total.

Non résolu : l'écart de réduction générale proprement dite.

| Mois | Quadra | EYWAI | Écart |
|---|---|---|---|
| Mai | 244,99 | 244,99 | 0,00 |
| Juin | 263,27 | 244,95 | +18,32 |
| Juillet | 230,05 | 244,54 | −14,49 |

Même brut (3 855,98), mêmes heures (169), mêmes cumuls. Mai est exact au
centime, donc formule et paramètres (RGDU 2026, T 0,3781, p 1,75, SMIC de
référence 12,02) sont les bons. Juin et juillet se compensent presque
(+3,83 € sur les deux mois) : c'est le rythme de la régularisation annuelle
qui diffère, pas la règle. Aucune formule mensuelle avec un SMIC de 11,88,
12,02 ou 12,31 ne donne 230,05. À suivre sur août et sur la DSN annuelle
plutôt qu'à corriger maintenant.

## 3. Valorisation des absences non rémunérées (Marion, juillet)

Deux choses dans ce retour.

**L'éditeur.** 3,29 = 0,25 h × 13,143, le montant d'origine : changer la
base d'une ligne d'absence ne recalcule pas son montant, seules les lignes
heures sup relancent le moteur. Ses corrections n'étaient de toute façon pas
enregistrées (bulletin sans édition manuelle en base). Le bandeau de
l'éditeur le dit maintenant (§ 5).

**La règle.** Bulletin Quadra de juillet, lignes « Abs aut nonpayé » :

| Jour | Heures planifiées | Quadra base | Quadra HS 25 % | EYWAI base | EYWAI HS |
|---|---|---|---|---|---|
| 07/07 | 8,5 | 7,63 | 0,87 | 7,00 | 0,80 |
| 08/07 | 8,5 | 7,63 | 0,87 | 7,00 | 0,80 |
| 09/07 | 7,5 | 6,73 | 0,77 | 7,00 | 0,80 |
| 20/07 | 0,25 | 0,23 | — | 0,25 | — |
| 23/07 | 0,75 | 0,67 | — | 0,75 | — |

Quadra retient les **heures planifiées du jour**, réparties 35/39 au taux de
base et 4/39 au taux majoré (ligne « H. supp majorées à 25 % » 2,61 = 25,5 h
× 4/39). EYWAI retient 7 h au taux de base par jour (journée légale) plus une
« Réduction HS structurelles » de 0,8 h par jour, et met les fractions
entièrement en base. Écart sur le brut de juillet : 6,88 € (2 082,18 chez
nous, 2 089,06 chez Quadra). Les congés payés, eux, sont valorisés pareil des
deux côtés (7 h + 0,8 h par jour).

Ce n'est pas une différence de cabinet : les cinq usines sont sur le même
logiciel (Cegid Quadra), et MBC montre la même règle avec des journées de
7,8 h (7,8 × 35/39 = 7,00 + 0,80, d'où les « 7,00 » de ses bulletins).
Notre règle du 07/09 (journée plafonnée à 7 h + quote-part d'heures sup par
journée légale) n'était juste que pour des journées de 7,8 h.

Corrigé le 13/09 au moteur, sans réglage par société : pour un contrat
> 35 h, chaque heure d'absence non rémunérée est retirée 35/39 au taux de
base et 4/39 sur les heures sup structurelles, sur les heures planifiées du
jour, quelle que soit sa position dans la semaine. L'arrêt maladie garde la
journée légale. Régénéré sur le test : 07/07 et 08/07 à 7,63 h (100,28),
09/07 à 6,73 h (88,45), 23/07 à 0,67 h (8,81), identiques à Quadra ; 20/07 à
0,22 h contre 0,23 (0,13 €, arrondi du cabinet). Brut 2 072,17 contre
2 089,06 : les 16,89 € d'écart sont exactement les deux absences que Quadra
n'a pas, le 17/07 (0,25 h) et le 31/07 (1 h). À vérifier par Gaëlle dans
son calendrier.

L'éditeur, lui, recalcule maintenant le montant d'une ligne d'absence ou de
congé quand on change sa base ou son taux, comme sur les lignes du brut.

## 4. Fuckar

La base porte bien la fin de contrat au 15/09/2026, enregistrée à 08:42
(Paris), une minute avant son message. Mais la capture montrant le champ
vide n'était pas un défaut de rafraîchissement : **la fiche ne pouvait
jamais relire cette date**. L'API qui renvoie un salarié seul, en lecture
comme après modification, passe par le modèle `FullEmployee`, qui ne
déclarait pas `contract_end_date` ni treize autres colonnes de la table
(`date_debut_execution`, `date_conclusion_contrat`, `sexe`, `matricule`…) ;
Pydantic ignore les champs inconnus. Le champ existait depuis le 4 juin dans
les requêtes et la liste allégée, jamais dans ce modèle : depuis trois mois,
la fin d'un CDD se saisissait sans se relire, et recharger la page n'y
changeait rien.

Corrigé le 13/09 : les quatorze colonnes sont dans `FullEmployee`, un test
compare le modèle aux colonnes de la table ; la fiche est en plus relue
après chaque enregistrement.

Sa demande de voir « toutes les dates des CDD et renouvellements » suppose un
historique de contrats : aujourd'hui une fiche n'a qu'une date d'entrée et
une date de fin. Chantier de fond (modèle, fiche, prime de précarité sur
renouvellement, DSN), à planifier.

## 5. Heures sup corrigées au bulletin (Bugny, Cotte, Espinosa)

Aucune des corrections n'est en base : Bugny est à 12 h + 3,5 h, Cotte et
Espinosa n'ont aucune édition manuelle, aucune « HS corrigée au bulletin »
dans les saisies du mois. La capture le prouve : 2 973,76 est exactement le
brut avec 12 h + 3,5 h, 3 162,97 le brut recalculé à l'écran avec 19 h +
6,5 h. L'éditeur recalcule le brut en direct mais pas les cotisations tant
qu'on n'a pas enregistré, et l'enregistrement était refusé d'un simple
toast quand le « résumé des modifications » était vide.

Fait : le résumé est facultatif (écrit automatiquement : « Correction des
heures supplémentaires : 15,5 h → 25,5 h »), et le bandeau orange dit que
les cotisations et le net affichés sont ceux d'origine tant qu'on n'a pas
enregistré. Le circuit de recalcul lui-même fonctionne (suite e2e du 08/09).

À noter : l'historique de Bugny porte une édition « QA Playwright » du 08/09
(12 h → 13 h, deux régénérations) — une version antérieure de la suite e2e
touchait un vrai bulletin. Le spec actuel intercepte les appels et ne
modifie rien en base.

Découvert à l'audit du 13/09 au soir : l'éditeur s'ouvrait déjà « modifié »
avant toute saisie (barre d'enregistrement affichée dès l'ouverture sur
Bugny juillet). Deux sections recalculaient au chargement — le net
(2 973,61 − 65,66 donne 2 907,9500000000003 en JavaScript, pas 2 907,95) et
les totaux de cotisations — et poussaient le résultat comme une saisie. Plus
grave, la formule de l'écran ignorait titres-restaurant, acompte et primes
non soumises : sur trois bulletins Zone 404 avec abonnement transport
(Agoumbi janvier, février, avril), ouvrir l'éditeur réécrivait un net à payer
faux de +36,50 €, prêt à être enregistré. Corrigé (ed0b0c82) : le net
enregistré reste la référence et ne bouge que de ce que la RH saisit ; les
totaux se recalculent dans les gestionnaires, jamais au chargement. Aucun
bulletin en base n'a été touché (ces trois-là n'ont jamais été édités).

## 6. Saisie sur salaire (Gautheron)

La saisie est en base (46,49 €, SGC Oyonnax, juillet, active). Cause exacte
de l'écran blanc : le montant est un `Decimal` dans le schéma de réponse,
que Pydantic sérialise en chaîne (« "46.49" ») ; le type TypeScript le
déclare `number`, la page appelait `toFixed` dessus, l'exception de rendu
remontait jusqu'à la racine faute de limite d'erreur autour des pages, et
React démontait tout. La saisie de Gautheron était la première jamais créée
sur le test : la ligne fautive n'avait jamais été rendue. Un onglet jumeau,
non branché, convertissait déjà depuis le premier commit.

Corrigé le 13/09, aux trois niveaux : les montants des saisies et avances
sortent en nombre dans le JSON (type partagé `Montant`) ; chaque page des
deux espaces est sous une limite d'erreur avec un bouton « Recharger la
page » ; les deux onglets jumeaux non branchés sont supprimés. « Rien dans
le bulletin » est attendu : la saisie est lue à la génération, il faut
régénérer juillet.

## 7. Demory (sorti le 24/07)

Statut « parti », sortie archivée, bulletins de mars à juin en brouillon,
aucun bulletin de juillet. Le correctif du 07/09 pour le voir sur ses mois de
présence n'était branché que sur le calendrier ; la liste paie (`status=
payroll`) excluait les partis, et la génération refusait « Ce collaborateur
n'est pas actif ».

Fait :

- liste paie : les partis restent, avec `exit_last_working_day`, et
  seulement s'ils ont une sortie datée ; l'éligibilité d'un parti se juge sur
  sa fiche seule ;
- écrans Paie et Bulletins : un parti n'apparaît que sur les mois où il
  était présent (toute l'année en vue salarié, le mois choisi en vue mois et
  au lancement) ;
- génération : un parti dont la sortie tombe dans le mois demandé ou après
  passe la garde de statut ; la garde de période refuse toujours les mois
  suivants.

Son bulletin de juillet a été généré sur le test par la commande réelle
(`scripts/demory_juillet_test.py`, puis `demory_fin_cdd_test.py`). Trois
choses sont apparues en le comparant à Quadra (du 01/07 au 24/07, brut
3 509,91) :

- **Le dossier de départ était typé « licenciement »**, validé et archivé la
  même seconde le 28/08, sans indemnités calculées. C'est un CDD arrivé à
  son terme : retypé `fin_cdd`, indemnités calculées par le module Départs.
- **L'indemnité compensatrice de congés payés manquait.** Un dossier sans
  indemnités calculées bloquait celle du moteur ; et une fois calculée par
  le module Départs, elle était ajoutée *après* les cotisations (net
  supérieur au brut). Corrigé en deux temps : en fin de CDD, l'ICCP est
  portée par le brut au dixième, cotisée, comme la prime de précarité
  (940,36 contre 940,23 chez Quadra) ; puis, le 13/09, pour tous les types
  de départ, préavis et ICCP du dossier entrent dans le brut avant
  cotisations (`engine.indemnites_sortie_brut`), et le bulletin de sortie
  n'ajoute après cotisations que les indemnités exonérées.
- **Un « rappel de salaire juin » de 16,69 € fantôme.** L'évolution de
  salaire du 01/06 (SMIC, 1 850,37 → 1 867,06) déclenchait un rappel sur
  chaque bulletin postérieur tant qu'elle n'était pas marquée « déjà
  versé », alors que juin avait été payé au nouveau taux. Trois cas sur le
  test (Alves chez Cartol, Demory et Fuckar chez Colorplast) marqués à la
  main le 12/09. Corrigé au moteur le 13/09 : le rappel relit le salaire de
  base sur lequel chaque bulletin antérieur a été établi (champ mémorisé
  `parametres.salaire_base_mensuel`, sinon ligne « Salaire de base » × heures
  mensuelles) et ne rappelle que ce qui manque ; un mois sans bulletin EYWAI
  n'est pas rappelé, il se saisit à la main.

Bulletin final : base 126 h et heures sup 14,40 h au centime, congé du 13/07
au centime, ICCP 940,36. Brut 3 567,87 contre 3 509,91 : l'écart de 57,96
est la prime de précarité (854,87 contre 797,04), c'est-à-dire 10 % du brut
de mai, où les absences de Demory ne sont pas saisies sur le test (Quadra :
1 529,05 avec 0,8 h de HS ; EYWAI : 2 114,65 sans absence). À saisir par
Gaëlle, puis régénérer mai et juillet.

## Retours du 14/09 et état au soir du 14/09

Gaëlle a comparé ses bulletins Quadra de juillet aux nôtres, ligne à ligne
(Espinosa, Fuckar, Marion). Bases, taux, valorisation 35/39 : identiques.
Deux règles expliquaient tout l'écart de brut, spécifiées dans
`docs/superpowers/specs/2026-09-14-fenetre-variables-et-bilan-hebdo-design.md`
et corrigées (d0dd4b08, 139476c4) :

- **Fenêtre des variables** : elle était affichée mais ne bornait que les
  heures sup ; les absences suivaient le mois civil, la semaine du 27 au 31
  juillet était retenue sur juillet puis reprise sur août. Les absences non
  rémunérées suivent désormais la fenêtre ; congés, fériés et arrêts restent
  au mois civil (à confirmer avec Gaëlle). Le compteur « cumul heures » se
  calcule sur les événements retenus par la fenêtre.
- **Bilan par semaine** : les absences étaient retenues jour par jour, sans
  compensation par les heures faites plus tard dans la semaine (Fuckar,
  semaine du 6 juillet : 5,5 h retenues pour 2,5 h de manque). Une semaine
  se solde maintenant en bloc, comme le fait Gaëlle à la main.

Vérifié sur le test (fenêtre 22/06 → 26/07) : Fuckar 1 906,45 et Espinosa
3 191,76 au centime ; Marion 2 085,64 avec son vendredi 17/07 pointé 4 h 45,
puis 2 089,03 une fois ce jour remis à 5 h comme sa feuille (Quadra 2 089,06 :
3 centimes, le quart d'heure du 20/07 vaut 0,22 h chez nous et 0,23 chez eux). Août porte la semaine du
27 au 31 juillet une seule fois. MAJI et ZONE 404 rejoués : résultat identique
au relevé du 11/09 sur les 81 bulletins.

Chaîne des cumuls, rectificatif du 14/09 tard le soir : le diagnostic
« 87 € manquants sur janvier à mars » était faux. Les bulletins Quadra relus
montrent que le cabinet n'a réintégré la part patronale de mutuelle dans le
net imposable qu'à partir d'avril (Girerd : 2 600,18 de janvier à mars,
2 629,13 en avril). Le cumul que Gaëlle lisait sur notre juillet, 18 435,65,
était à deux centimes du cumul Quadra, 18 435,67. L'écart qu'elle signale sur
« le cumul net imposable » n'est donc pas celui-là : lui demander le chiffre
Quadra qu'elle compare. Entre-temps, une regénération de janvier à juin puis
un retour aux bulletins du 27/08 avaient décalé la chaîne de + 87 € ; le
maillon de juin de chaque salarié a été réaligné sur le cumul Quadra à fin
juin (`colorplast_liens_juin_quadra_test.py`) et juillet regénéré : Bugny,
Cotte, Espinosa, Fuckar au centime de Quadra, Girerd à 0,02. Gautheron et
Demory sur la meilleure valeur connue (PDF illisible / cumul de juin Quadra).
Règle à retenir : sur une reprise en cours d'année, la chaîne suit le cabinet,
c'est-à-dire ce qui a été déclaré, pas notre recalcul ; et un mois passé ne se
regénère qu'avec le setup mensuel du backtest.

Point cumuls de juillet, EYWAI contre Quadra (écart = EYWAI − Quadra), après
reprise des maillons de juin sur le net imposable et le PAS Quadra
(`colorplast_reprise_cumuls_juin_test.py` puis `_retour_test.py` : brut,
heures et réduction générale cumulés restent les nôtres, ils forment le trio
de la régularisation progressive et ne se reprennent pas séparément) :

| Salarié | Net imposable | PAS | Cumul heures | Cumul h. sup | Bruts |
|---|---|---|---|---|---|
| Bugny | 0,00 | 0,00 | −126,0 | +84,00 | +1 539,79 |
| Cotte | 0,00 | 0,00 | +16,9 | +2,76 | 0,00 |
| Demory | −63,15 | 0,00 | +548,2 | +41,13 | +341,42 |
| Espinosa | 0,00 | 0,00 | −130,0 | 0,00 | 0,00 |
| Fuckar | 0,00 | 0,00 | +55,0 | +2,80 | −0,01 |
| Gautheron | −27,77 | −0,45 | +265,9 | +29,97 | +1 938,11 |
| Girerd | −0,02 | 0,00 | 0,0 | 0,00 | +0,04 |

Lecture : net imposable et PAS au centime pour cinq salariés ; Demory et
Gautheron portent l'écart de leur mois de juillet (Demory : brut 3 420,37
contre 3 509,91, absences de mai non saisies ; Gautheron : net imposable de
juillet 1 473,40 contre 1 501,17, à creuser). « Cumul heures » : Quadra compte
la base au prorata d'entrée, moins les absences, plus les heures sup
conjoncturelles ; nous comptons la base mensuelle moins les absences, sans
prorata d'entrée (Fuckar +55 sur avril) ni heures sup (Bugny −126, Espinosa
−130). Cumul heures sup et bruts : l'historique de janvier à juin de Bugny,
Demory et Gautheron ne reproduit pas Quadra (participation, arrêts maladie,
absences de mai), ces trois cumuls se corrigeront par une reprise complète du
backtest de ces mois, pas à la main.

Janvier 2026 rejoué depuis les feuilles de pointage (15/09, 0 h 40) : les
27 feuilles de janvier à juin ont été remises en paysage
(`data/colorplast/pointages/`), les quatre de janvier lues à la main avec la
règle annotée par Gaëlle sur S03 (fin − début − 0,5 h de pause au-delà de
6 h). Script `colorplast_janvier_feuilles_test.py` : état de janvier posé par
le setup du backtest, absences et heures sup venant des feuilles et non des
bulletins, génération, comparaison, puis fiches remises comme avant (juillet
et la chaîne à partir de février non touchés).

| Salarié | EYWAI | Quadra | Écart | Lecture |
|---|---|---|---|---|
| Cotte | 2 351,89 | 2 351,89 | 0,00 | absence du 21/01 (3,14 + 0,36) retrouvée par le bilan hebdo |
| Gautheron | 2 252,28 | 2 252,28 | 0,00 | absences 13/01 (2,24) et 14/01 (7,63), réduction HS 1,13 identiques |
| Girerd | 3 799,07 | 3 799,06 | +0,01 | arrondi |
| Bugny | 3 023,40 | 3 023,40 | 0,00 | après relecture du vendredi 23/01 (16 h, pas 16 h 30, « 8,5 » annoté par Gaëlle) |
| Espinosa | 3 046,68 | 3 046,68 | 0,00 | après alignement de la semaine du 5/01 sur la saisie Quadra (45 h ; la feuille donne 44, S03 et S04 sont annotées 44 par Gaëlle : question à lui poser) |

La fenêtre s'est bien posée du 22/12/2025 au 25/01/2026, la semaine S05
partant en février. Cinq salariés sur cinq au centime, dont un aligné sur
la saisie Quadra pour une heure que la feuille ne montre pas. Le moteur a
retrouvé au centime les absences et leur répartition 35/39. À noter : un
avertissement « indemnité trajet au-delà du plafond annuel » apparaît sur une
regénération de janvier parce que le cumul additionne toute l'année déjà
saisie, à borner au mois généré.

Janvier ligne à ligne (15/09, 1 h) : cotisations principales salariales et
patronales identiques au centime pour les cinq ; nets après impôt : Bugny
75,58, Espinosa 74,06, Girerd 47,93 au centime, Cotte à 0,03, Gautheron à
0,10 (arrondis de base d'heures sup après absence). Trois écarts restent, tous
identifiés :
- réduction générale avec absences non rémunérées : exacte pour Bugny,
  Espinosa, Girerd ; Cotte −643,01 contre −609,61, Gautheron −689,65 contre
  −582,21. Notre SMIC de référence ne se réduit pas comme celui de Quadra en
  présence d'heures non payées. Sujet moteur, probable origine des écarts de
  juin et juillet sur Marion ;
- « autres contributions » employeur : Quadra applique la formation à 0,55 %
  (moins de 11 salariés) et un forfait social de 8 % sur prévoyance plus
  mutuelle patronale ; nous prenons 1 % et pas de forfait social. Bugny :
  63,36 contre 53,22. Réglages d'effectif à trancher ;
- cumul heures : Quadra ajoute les heures sup conjoncturelles (Bugny 189,5
  contre 169), convention déjà notée.
Le doublon de mutuelle famille (retenue mensuelle du setup en plus de la
cotisation de la fiche) est retiré du setup pour tous les mois.

Reste pour le 15/09 (appel 17h30) : congés et arrêts dans la fenêtre ou au
mois civil ; les 2 h de surplus de Fuckar la semaine du 27/07, payées en
heures sup chez nous, rien chez Quadra ; compteurs CP N-1 (Bugny 40/0/40
attendu, Marion 15/2/13) ; cumul réduction générale Quadra à fin juillet
(le nôtre : 1 745,03) ; mails de Gaëlle (Bugny, Cotte, Girerd annotés) et de
Vanessa (janvier) ; CP en jours ouvrés pour MAJI et ZONE 404 ; titres-restaurant
à retirer sur tout le groupe (Elsa).

Suite e2e du test, remise au vert le 14/09 au soir (38 scénarios) :
- la page Exports plantait sur un 500 du statut d'envoi quand l'OD globale
  refusait de s'équilibrer (Colorplast juillet : PPV et remboursement de
  fournitures sans compte comptable). Le refus est désormais une anomalie
  bloquante affichée sur la carte, avec le message (b0485091) ; le
  paramétrage des comptes reste à faire par Gaëlle dans Exports > Comptes
  comptables ;
- le workflow e2e jouait les specs de main contre le frontend de la branche
  déployée. Il joue maintenant celles du commit déployé (621fd1cb) ; pour
  les déclenchements automatiques, effet après fusion sur main.

## État au soir du 13/09

- Versement mobilité : plus d'alerte quand rien ne change la paie
  (effectif < 11, commune hors barème) ; 81 bulletins MAJI / ZONE 404
  rejoués sans avertissement, écarts Quadra identiques au 11/09.
- Éditeur de bulletin : ne s'ouvre plus « modifié » (§ 5).
- Audit de quatre écrans (saisies sur salaire, fiche Fuckar, paie de juillet
  avec Demory, éditeur Bugny) : à rejouer après le déploiement ed0b0c82.

## État au soir du 12/09

- Branche `fix/payslip-edit-state` déployée sur le test (révision backend
  00262, 20:51 UTC).
- Cinq usines en jours ouvrés, 2,083 j/mois ; 245 compteurs repris
  réexprimés. Contrôle Girerd par le domaine : 27,00 et 4,16 à fin juillet,
  12,00 et 6,24 à fin août, identiques à Quadra.
- Bulletin de juillet de Demory en place. Les autres bulletins n'ont pas été
  régénérés : c'est à Gaëlle de le faire, comme d'habitude.

## Reste à faire

- Périmètre de l'unité ouvrée pour MAJI / ZONE 404 (Vanessa).
- Marion : les absences du 17/07 et du 31/07, absentes chez Quadra, à
  confirmer ou retirer du calendrier de test.
- Historique des contrats (§ 4) : à planifier.
- Suivre la réduction générale sur août (§ 2).
