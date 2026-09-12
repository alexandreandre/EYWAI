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
| 3 | Absence de Marion : 0,23 × 13,143 ≠ 3,29 | aperçu non recalculé + règle de valorisation différente de Quadra | règle à trancher (voir § 3) |
| 4 | Fuckar, fin de contrat au 15/09 « non enregistrée » | enregistrée en base | rien à corriger ; demande d'historique des CDD = chantier de fond |
| 5 | Bugny, Cotte, Espinosa : cotisations sans les HS corrigées | corrections jamais enregistrées (aperçu) | éditeur assoupli |
| 6 | Gautheron, saisie sur salaire : écran blanc | plantage d'affichage | corrigé |
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

Notre règle actuelle vient du retour du 07/09 sur ce même bulletin et
s'aligne sur Cegid (MBC, cas OSMANI2 : arrêt maladie retenu 7 h et non
7,5 h). Les deux cabinets ne font donc pas pareil. Le moteur reste
généraliste : il faut un **réglage par société** (« journée légale + quote-
part HS » ou « heures planifiées au prorata base/HS »), pas une exception
Colorplast dans le code. À trancher avec Alexandre avant d'écrire. Non fait.

EYWAI porte aussi deux absences que Quadra n'a pas (17/07 0,25 h et 31/07
1 h en HS) : elles viennent du calendrier de test, à vérifier avec Gaëlle.

## 4. Fuckar

La fiche porte bien la fin de contrat au 15/09/2026, enregistrée à 08:42
(Paris), une minute avant son message. La capture montre le champ vide :
affichage non rafraîchi, pas d'échec d'enregistrement. À faire recharger.

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

## 6. Saisie sur salaire (Gautheron)

La saisie est en base (46,49 €, SGC Oyonnax, juillet, active). L'écran
blanc venait de `seizure.amount.toFixed(2)` sur un montant reçu en chaîne :
la page `/salary-seizures` plantait dès qu'une saisie existait. L'onglet
équivalent de « Saisies et avances » faisait la conversion. Fait : un
formateur commun, testé. « Rien dans le bulletin » est attendu : la saisie
est lue à la génération, il faut régénérer juillet.

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
  supérieur au brut). Corrigé : en fin de CDD, l'ICCP est portée par le
  brut au dixième, cotisée, comme la prime de précarité ; le dossier ne
  l'ajoute plus une seconde fois. Résultat 940,36 contre 940,23 chez Quadra.
  Le même défaut (indemnités « soumises » ajoutées après cotisations)
  subsiste pour les autres types de départ, préavis compris : à traiter.
- **Un « rappel de salaire juin » de 16,69 € fantôme.** L'évolution de
  salaire du 01/06 (SMIC, 1 850,37 → 1 867,06) déclenche un rappel sur
  chaque bulletin postérieur tant qu'elle n'est pas marquée « déjà versé »,
  alors que juin a été payé au nouveau taux. Trois cas sur le test (Alves
  chez Cartol, Demory et Fuckar chez Colorplast) marqués à la main, comme le
  backtest MAJI l'avait fait. Le moteur devrait vérifier ce que le bulletin
  du mois a réellement payé : défaut à corriger.

Bulletin final : base 126 h et heures sup 14,40 h au centime, congé du 13/07
au centime, ICCP 940,36. Brut 3 567,87 contre 3 509,91 : l'écart de 57,96
est la prime de précarité (854,87 contre 797,04), c'est-à-dire 10 % du brut
de mai, où les absences de Demory ne sont pas saisies sur le test (Quadra :
1 529,05 avec 0,8 h de HS ; EYWAI : 2 114,65 sans absence). À saisir par
Gaëlle, puis régénérer mai et juillet.

## État au soir du 12/09

- Branche `fix/payslip-edit-state` déployée sur le test (révision backend
  00262, 20:51 UTC).
- Cinq usines en jours ouvrés, 2,083 j/mois ; 245 compteurs repris
  réexprimés. Contrôle Girerd par le domaine : 27,00 et 4,16 à fin juillet,
  12,00 et 6,24 à fin août, identiques à Quadra.
- Bulletin de juillet de Demory en place. Les autres bulletins n'ont pas été
  régénérés : c'est à Gaëlle de le faire, comme d'habitude.

## Reste à faire

- Trancher la règle d'absence (§ 3) et le périmètre de l'unité ouvrée pour
  MAJI / ZONE 404.
- Bulletin de sortie : intégrer les indemnités soumises dans le brut avant
  cotisations pour tous les types de départ (§ 7).
- Rappel de salaire : ne rappeler que les mois réellement payés à l'ancien
  taux (§ 7).
- Historique des contrats (§ 4) : à planifier.
- Suivre la réduction générale sur août (§ 2).
