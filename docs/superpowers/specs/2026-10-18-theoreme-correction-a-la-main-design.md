# Le théorème de la correction à la main — conception

18/10/2026. Validée par Alexandre le même jour.

## 1. L'énoncé

> Tout bulletin est calculé par Martine. Toute ligne peut toujours être corrigée à la main,
> vite. Toute correction est enregistrée, rejouée et propagée : cumuls, compteurs, DSN,
> exports, mois suivants.

Le but est double : la gestionnaire de paie finit son mois même quand Martine se trompe ou
qu'un cas sort de l'ordinaire, et une correction ne fausse jamais rien en aval. La souplesse
vient de ce qu'on peut tout corriger. La rigueur vient de ce qu'une correction est une donnée
d'entrée du moteur, jamais une retouche du résultat.

## 2. Ce qui existe, ce qui manque

Existe :

- l'onglet « Corriger » du bulletin : heures sup du mois (par palier, ou retour au planning),
  primes ajoutées, corrigées ou retirées ; chaque correction est écrite en variable du mois
  (`monthly_inputs`), puis le bulletin est recalculé en entier sous le verrou de génération
  (`payslips/application/corrections.py`) ;
- les saisies du mois : un gain ou une retenue, soumis ou non aux cotisations, imposable ou
  non ;
- les corrections à la source : planning, fiche, absences, saisies.

Manque : aucune ligne calculée ne se corrige. Une cotisation, la réduction générale, une
indemnité (congés, sortie, maintien) ou l'impôt ne se corrigent qu'en changeant leurs sources,
et une source ne couvre pas tous les cas. Le théorème est donc faux aujourd'hui.

La retouche libre du bulletin a été retirée le 28/09 : elle enregistrait le bulletin tel que
l'écran l'envoyait, sans recalculer cotisations, net ni cumuls. Ce chantier ne la réintroduit
pas.

## 3. Les règles

1. **Ce qui se corrige.** Toute ligne : gains (salaire, heures sup, absences, congés, primes,
   indemnités, maintien) et cotisations (salariales et patronales, réduction générale
   comprise). Et des lignes de régularisation pour ce qui n'a pas de ligne : un gain, une
   retenue, une cotisation d'un organisme.
2. **Ce qui ne se tape jamais.** Les totaux : brut, net imposable, net social, net à payer,
   coût employeur. Ils restent la somme des lignes.
3. **Une ligne avec une base et un taux se corrige par sa base ou son taux.** Le montant suit,
   avec le même arrondi que le moteur (`round(base × taux, 2)`). Une ligne en heures ou en
   jours garde ainsi ses quantités liées à son montant. Le montant seul ne se corrige que sur
   une ligne au forfait (une mutuelle en euros, une prime fixe) ou sans base (réduction
   générale). Raison : un montant différent de base × taux est rejeté aux contrôles de la
   DSN, et les heures alimentent les cumuls, la réduction générale et le contingent. Même
   règle pour une régularisation de cotisation : elle porte une base (positive ou négative)
   et le taux de la ligne qu'elle régularise ; l'écran convertit l'écart saisi en euros en
   base, et montre le montant arrondi qui en résulte. Le montant libre ne vaut que pour une
   cotisation au forfait.
4. **Une correction est une variable du mois.** Elle porte la ligne visée, les valeurs voulues
   et un motif obligatoire. Elle ne vaut que pour son mois et ne se reporte jamais seule sur
   le suivant.
5. **Elle est rejouée à chaque recalcul**, jusqu'à ce que la gestionnaire la retire.
6. **Elle se voit.** La ligne porte « corrigée à la main », avec la valeur que Martine avait
   calculée, à l'écran et sur le PDF. L'historique la garde ; restaurer une version la
   restaure.
7. **Elle n'est jamais perdue en silence.** Si la ligne visée par une correction n'existe plus
   après un changement à la source, la correction reste enregistrée, le bulletin est marqué
   « correction en attente » et ne peut pas être validé tant que la gestionnaire n'a pas réglé
   ce cas (retirer la correction ou la reporter sur une autre ligne). Une régularisation, elle,
   ne vise pas une ligne mais un organisme : elle reste valable même si la ligne de cet
   organisme disparaît.
8. **Elle sert de capteur.** Une même ligne corrigée deux mois de suite, ou chez plusieurs
   salariés, signale un défaut probable du moteur : on corrige alors le moteur, pas les
   bulletins.
9. **Bornes.** Un mois repris de l'ancien logiciel reste verrouillé. Corriger un bulletin
   validé le repasse en brouillon (comportement actuel). Un mois suivant validé n'est jamais
   recalculé seul : Martine le signale.

## 4. Les données

Une colonne nullable `correction_ligne jsonb` sur `monthly_inputs`. Une correction est une
ligne de saisie du mois dont cette colonne est remplie ; `amount` porte le montant de la
correction (pour les régularisations) ou zéro.

```json
{
  "type": "regularisation_cotisation" | "correction",
  "ligne": "<code stable de la ligne visée>",
  "coti_id": "<organisme, pour une régularisation de cotisation>",
  "base": 151.67,
  "taux_salarial": 0.0035, "taux_patronal": 0.0070,
  "montant": 12.40,
  "motif": "texte saisi par la gestionnaire"
}
```

Seuls les champs que la règle 3 permet pour la ligne visée sont remplis ; les autres restent
absents. La valeur que Martine aurait calculée n'est pas stockée dans la correction (elle
serait périmée au premier recalcul) : le moteur la pose sur la ligne corrigée, à chaque calcul,
dans un champ `valeur_calculee`.

Le gain et la retenue de régularisation sont des saisies du mois ordinaires (nom, montant
signé, soumis, imposable, sur le net) : ce sont les « primes ajoutées » que l'onglet
« Corriger » sait déjà créer, corriger, retirer et restaurer. Leur traitement comptable est
celui des primes et des retenues existantes ; le test du théorème vérifie que le net se
reconstruit avec elles.

Le choix de `monthly_inputs` est imposé par l'existant : c'est la seule table que lisent
l'empreinte « À recalculer » (`SAISIE_COLONNES`, à étendre à `correction_ligne`), le bac à
sable (`saisies_en_plus`), le verrou de génération et la cascade des mois suivants. La
restauration d'une version (`corrections_pour_revenir`) doit reprendre ces saisies, sinon elle
les efface.

## 5. Où la correction s'applique dans le moteur

Un module unique, `engine/corrections_manuelles.py`, appelé aux mêmes étapes des deux copies
du pipeline (`documents/payslip_run_heures.py` pour le mensuel, `payslip_run_forfait.py` pour
le forfait jours). Le bulletin de sortie et le bac à sable passent par ces pipelines. Un test
de contrat vérifie que les deux pipelines appellent le module aux mêmes étapes.

Toujours **avant l'assemblage** du bulletin (`engine/bulletin.py`, `creer_bulletin_final` et
`creer_bulletin_sortie`) : après l'assemblage, les copies stockées divergent
(`structure_cotisations`, `cotisations_officielles`, `synthese_net`, pied de page), et le
contrôle comptable, la validation et le PDF cassent.

| Ce qui est corrigé | Où | Ce qui suit |
|---|---|---|
| Ligne de gain | à l'endroit qui produit la ligne, avant les grandeurs dérivées (rémunération et heures HS, précarité, indemnité de congés du mois) ; pour les lignes ajoutées après le brut (nuit, pause, maintien), à leur création ; puis brut re-sommé | assiettes, plafond, tranches Agirc-Arrco, CSG, réduction générale, net, coût, cumuls |
| Cotisation | dans le calcul de la ligne (`_calculer_une_ligne`, `calcul_cotisations.py`), pour que le total salarial, la réduction HS plafonnée et la ligne restent d'accord | net social, net imposable, montant net social, impôt, net, coût |
| Régularisation de cotisation | ajoutée au bloc des cotisations avec le `coti_id` de l'organisme, comptée dans le total salarial ou patronal | idem |
| Réduction générale | dans `calcul_reduction_generale.py`, sur le montant du mois | coût employeur, cumul (§ 6) |
| Impôt (taux du mois) | dans `calculer_net_et_impot`, avant le calcul du montant | net à payer, cumul impôt |

Les règles qui reconnaissent une ligne par son libellé (CSG non déductible dans le net
imposable, heures sup, indemnité de congés au solde de tout compte, contingent, regroupement
par organisme) restent valables : une correction ne change jamais le libellé. La mention
« corrigée à la main » est un champ à part sur la ligne. Une régularisation hérite de la nature
de la ligne qu'elle régularise : elle porte son `coti_id`, et son libellé est celui de la ligne
d'origine précédé de « Régularisation – ». Les règles qui lisent le `coti_id` (mutuelle, DSN,
comptabilité) comme celles qui lisent un libellé (CSG non déductible dans le net imposable) la
classent donc comme la ligne d'origine ; un test le vérifie pour chacune.

Les retenues posées après le moteur (prêts, saisies sur salaire, report d'un net négatif)
restent où elles sont ; la garantie « totaux = somme des lignes » les inclut.

## 6. Cumuls et mois suivants

Règle : **un cumul enregistre ce qui a réellement été payé et déclaré.** Les cumuls sont
écrits depuis les valeurs du moteur (`documents/payslip_run_common.py`) ; une correction
appliquée dans le moteur y passe donc d'elle-même, à trois exceptions près :

- **Réduction générale.** Elle se régularise sur l'année (dû depuis janvier moins déjà
  appliqué). Le cumul `reduction_generale_patronale` enregistre le montant réellement appliqué
  ce mois, correction comprise. Conséquence voulue : une réduction baissée à la main en octobre
  est rattrapée en novembre, comme le veut la loi. Pour changer le montant dû pour de bon, la
  gestionnaire corrige ce qui le détermine (heures, brut).
- **Impôt.** Le cumul `impot_preleve_a_la_source` enregistre le montant réellement prélevé.
- **Quantités.** Les cumuls d'heures (`heures_remunerees`, `heures_supplementaires_remunerees`)
  suivent la base corrigée d'une ligne en heures (règle 3).

Les compteurs de congés, de CET et de modulation sont en jours et en heures et viennent de
leurs sources : une correction de montant ne les touche pas.

La cascade existe déjà : une correction change les cumuls du mois, l'empreinte des cumuls
signale le mois suivant « À recalculer ».

## 7. Ce qui lit le bulletin ensuite

`payslips` n'a aucune colonne de montant : tout est dans `payslip_data`. Un bulletin recalculé
et enregistré normalement suit donc partout, sauf ici :

- **DSN.** La maladie et les allocations familiales au-delà du taux socle, la CSG/CRDS et le net
  versé recalculent base × taux (`dsn_export/domain/cotisation_mapping.py`, `builder.py`).
  Une régularisation exprimée en base au taux de la ligne (règle 3) est donc recalculée juste,
  à l'arrondi près, comme la ligne d'origine ; seule la fusion des lignes de même code est à
  corriger (ci-dessous). Une ligne sans `coti_id` connu est ignorée : une régularisation porte
  toujours un `coti_id`. La DSN lit le SMIC de référence sur la ligne d'origine de la réduction
  générale, que la régularisation ne remplace pas. À vérifier au premier dépôt réel : la
  cohérence entre les assiettes des cotisations (bloc 81) et les bases assujetties (bloc 78)
  quand une régularisation change une assiette.
- **Comptabilité.** Une ligne sans organisme est sautée et l'écriture se déséquilibre
  (`exports/infrastructure/payroll_ledger.py`) : même règle du `coti_id`. Le gain et la retenue
  de régularisation ont leur famille comptable.
- **PDF.** Le gabarit n'affiche aucune mention par ligne (`documents/bulletin_view.py`,
  `templates/template_bulletin.html`) : ajouter le champ et la mention (astérisque et note
  « Ligne corrigée à la main : motif »).
- **Écran.** L'info-bulle par ligne existe (`explication`) ; celle de la réduction générale ne
  doit plus dire « régularisation depuis janvier » sur une ligne corrigée.
- **Contrôle « validé = recalculé ».** Il compare une liste de blocs figée
  (`payroll/domain/empreinte_entrees.py`) : tout nouveau bloc y entre.
- **Comparaison au mois précédent.** Les alertes « nouvelle ligne » et « ligne disparue »
  (R07, R06) ne lisent que les lignes de brut : une régularisation de cotisation ne les
  déclenche pas ; un gain de régularisation les déclenche comme toute prime nouvelle.
- **Fusion des lignes dans la DSN.** La DSN fusionne les lignes d'un même code en additionnant
  leurs taux (`_cumuler`) : une régularisation fusionnée doit ajouter son montant (et son
  assiette, puisqu'elle est une base), jamais son taux.

## 8. L'écran

Dans l'onglet « Corriger », même mécanique qu'aujourd'hui (barre « Corrections non
enregistrées », puis « Enregistrer et recalculer ») :

- carte « Ajouter une ligne de régularisation » : gain, retenue ou cotisation ; pour un gain
  ou une retenue, montant, soumis et imposable ; pour une cotisation, l'organisme se choisit
  parmi les cotisations du bulletin (le taux est repris, l'écart saisi en euros est converti en
  base, règle 3), ou dans le catalogue des cotisations si la ligne manque (la gestionnaire
  saisit alors base et taux) ; motif obligatoire ;
- carte « Corriger une ligne » (étape 2) : les lignes du bulletin avec leur base, leur taux et
  leur montant ; le champ modifiable dépend de la règle 3 ; motif obligatoire ;
- chaque correction listée avec sa valeur calculée, sa valeur imposée, son motif et un bouton
  « Retirer ».

Sur l'onglet « Bulletin », une ligne corrigée porte la mention et, au survol, la valeur
calculée et le motif. La liste de contrôle du mois compte les lignes corrigées à la main (non
bloquant) et signale une ligne corrigée deux mois de suite ; une correction en attente bloque
l'étape de validation.

## 9. Les garanties et le test du théorème

1. Sans correction, chaque bulletin est identique au centime (filet avant/après sur
   Colorplast, Comitech et MAJI).
2. Les totaux sont la somme des lignes ; les copies stockées d'un bulletin sont égales entre
   elles ; le contrôle comptable passe.
3. Tout ce qui dépend de la ligne corrigée suit (tableau du § 5).
4. Les cumuls enregistrent ce qui a été payé et déclaré ; le mois suivant part de là.
5. Quantités et montants restent liés.
6. La correction est rejouée à chaque recalcul, restaurée avec sa version, jamais perdue :
   orpheline, elle bloque la validation.
7. La DSN est égale au bulletin au centime, par organisme ; l'écriture comptable est
   équilibrée ; le solde de tout compte, les attestations, les virements et les exports
   « à refaire » suivent.
8. La correction est tracée : motif, auteur, date, valeur calculée, valeur imposée.
9. Les bornes de la règle 9 tiennent.
10. Le comportement est le même au mensuel, au forfait jours, à la sortie et au bac à sable.

**Le test du théorème** tourne au bac à sable, sans rien écrire : pour chaque société, sur un
mois récent, pour chaque bulletin et chaque type de ligne présent, il injecte une correction
(en mémoire, par `saisies_en_plus`), recalcule, puis vérifie les garanties 2 à 7 et 10 : la
ligne porte la valeur voulue, les totaux et les copies concordent, les cumuls du mois sont ceux
du mois d'avant plus ce mois, le mois suivant recalculé part de ces cumuls, la DSN produite et
l'écriture comptable concordent avec le bulletin. Il échoue si un type de ligne produit par le
moteur n'est pas couvert : un nouveau type de ligne ne peut pas entrer sans sa correction.

## 10. Livraison en deux étapes

**Étape 1 — le théorème devient vrai.**

- régularisation de cotisation (nouveau), gain et retenue de régularisation depuis l'onglet
  « Corriger » ;
- colonne `correction_ligne`, empreinte, bac à sable, restauration (la « correction en
  attente » n'existe qu'à l'étape 2 : une régularisation ne devient jamais orpheline) ;
- application dans les deux pipelines, cumuls (§ 6) ; une régularisation de la réduction
  générale entre dans son cumul ;
- DSN dont la fusion additionne le montant et l'assiette d'une régularisation, jamais son
  taux ; mention sur le PDF et à l'écran ;
- liste de contrôle et capteur ;
- test du théorème (chaque montant du bulletin se corrige par une régularisation de même
  nature ou à la source ; l'impôt se corrige par son taux, sur la fiche).

**Étape 2 — corriger directement sur la ligne.**

- un code stable sur chaque ligne (environ 45 producteurs de lignes de gain ; un
  discriminant pour les `coti_id` non uniques : CSG non déductible, forfait social, mutuelle ;
  participation, PPV et IJSS qui n'ont pas de `coti_id`) ;
- correction par base, taux ou montant selon la règle 3, aux points du § 5 ;
- taux d'impôt du mois ;
- carte « Corriger une ligne » ;
- test du théorème étendu à la correction directe.

Chaque étape a son plan d'exécution, son filet au centime et son déploiement sur accord
d'Alexandre. Le travail moteur se fait en Opus.

## 11. Hors périmètre

- Report automatique d'une correction sur le mois suivant (règle 4).
- Correction d'un mois repris de l'ancien logiciel.
- Défauts relevés pendant l'inventaire, à traiter à part : indicateurs de cotisations du
  tableau de bord toujours à zéro sur les bulletins récents (ils lisent une clé que le moteur
  n'écrit plus) ; attestation de salaire maladie qui affiche toujours zéro prime (`total_primes`
  jamais écrite) ; deux formules de coût employeur (bulletin normal et bulletin de sortie) à
  aligner.

## 12. Risques

- Le pipeline existe en deux copies : chaque point d'application se pose deux fois. Le test de
  contrat et le test du théorème couvrent les deux.
- Les repérages par libellé sont nombreux : une régularisation doit être reconnue par son
  `coti_id` partout où une règle lit un libellé, sinon elle échappe au net imposable ou au
  contingent.
- La DSN n'est pas encore déposée par Martine : sa correction est vérifiée par le test, pas
  encore par un dépôt réel.
- Non vérifiés pendant l'inventaire : la comparaison aux DSN et aux bulletins de l'ancien
  logiciel (une ligne corrigée y apparaîtra comme un écart, à libeller), l'espace salarié, le
  détail des compteurs de CET et de modulation.

## 13. Après ce chantier

Les vidéos de formation disent aujourd'hui « jamais le PDF » (A.1 scènes 9 et 10, J.1). Elles
seront réécrites une fois l'étape 1 déployée : « vous corrigez à la main depuis le bulletin, et
la correction passe dans les cumuls ».
