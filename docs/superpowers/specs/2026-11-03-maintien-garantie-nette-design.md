# Maintien de la plasturgie : garantie du net

Date : 03/11/2026. Branche : feat/dsn-octobre. Remplace la décision n° 4 de la conception du 24/10 (`2026-10-24-maintien-paliers-convention-design.md`, « Garantie brute, on garde »).

## Pourquoi

Audit du 02/11, n° 7 : Martine garantit le brut et déduit les IJ brutes. Le texte garantit le net :
- non-cadres, avenant du 15/05/1991, art. 13 e : « L'indemnisation est déterminée en fonction de la rémunération nette qu'aurait perçue l'intéressé s'il avait normalement travaillé pendant la période indemnisée » ;
- cadres, accord du 17/12/1992, art. 5 : même phrase.

Les IJ ne supportent que la CSG et la CRDS (6,7 %), le salaire environ 22 %. Garantir le brut et déduire les IJ brutes donne donc au salarié plus que le net garanti : environ IJ × (t − 6,7 %) de net en trop. Exemples de l'audit : S.G. a reçu 555,30 € de trop en lecture nette, et le rappel d'octobre de D.S. (615,53 €) n'est pas dû au titre de la convention.

Règle d'Alexandre du 03/11 : « ce qui est légal pour Martine, rien de plus, rien de moins ». Le 24/10, on avait gardé le brut parce qu'il est plus favorable. Cette raison ne tient plus.

## La règle

Sous un barème à garantie nette, pour l'option de la convention seulement :

- le garanti reste en brut : taux du palier × valeur des jours (`BaseDesJours`), inchangé ;
- les IJ déduites (celles des jours maintenus, mêmes montants et même réglage qu'aujourd'hui) sont comptées **nettes de CSG et CRDS**, puis **ramenées au brut** avec le taux de prélèvements salariaux du salarié :
  `déduction = IJ × (1 − s) / (1 − t)`, avec `s` le taux de CSG et CRDS des IJ (6,7 %, `maladie.csg_ijss`, le même que les lignes du bulletin) et `t` la part salariale d'un euro de salaire ;
- versé = garanti − déduction, plancher à 0 (D1226-5).

Ainsi : versé × (1 − t) + IJ × (1 − s) = garanti × (1 − t). Le salarié reçoit en net le pourcentage garanti du net qu'il aurait perçu.

La règle joue dans les deux sens. D'ordinaire `t` dépasse `s`, et le versé est plus bas que la lecture brute. Pour un salarié presque sans cotisations salariales (un apprenti), `t` est sous `s`, et le versé est plus haut.

**Le taux `t`** est mesuré par le moteur de cotisations lui-même, sur une copie du contexte sans journal de corrections : `t = (S(H) − S(H − A)) / A`, où `S` est le total des cotisations salariales (CSG et CRDS comprises), `A` la valeur des jours maintenus, et `H` le salaire du mois (`BaseDesJours.salaire_du_mois`, au moins `A`). C'est la part salariale de la rémunération perdue, celle que le texte garantit. Elle tient compte de tout ce que le bulletin applique (tranches, prévoyance, exonération d'un apprenti), sans recopier un seul taux.

**Ce qui ne change pas** :
- le maintien légal (D1226-1 : « 90 % de la rémunération brute ») reste sur le brut, IJ brutes déduites (lecture prudente de D1226-5). La comparaison de chaque mois se fait toujours sur le versé ; le légal l'emporte donc plus souvent qu'avant ;
- sans déduction (sans subrogation, réglage « IJSS déduites » éteint), le garanti est versé en entier : c'est un choix de la société, plus favorable ;
- sans barème, rien ne change (`garantie` « brute » par défaut) ;
- le bulletin : une seule ligne « Maintien de salaire employeur », du montant versé.

**Repli** : si la mesure échoue ou rend un taux hors de [0 ; 0,6], le calcul garde la lecture brute (plus favorable au salarié) et le dit dans le détail du maintien. Jamais d'état silencieux.

## Ce qu'on montre

Le détail du maintien (fenêtre du bulletin, aperçu de l'absence) ajoute une phrase sous les paliers :
« Garantie du net : les IJSS (1 029,75 €) sont comptées nettes de CSG et CRDS (6,7 %), puis ramenées au brut avec 21,84 % de cotisations salariales. Maintien réduit de 200,57 €. » (« augmenté » quand la règle donne plus que la lecture brute.)

Le barème lisible (réglages de la société) dit la règle dans ses `regles`.

## Effets attendus

- Seules changent les sociétés réglées sur le barème Plasturgie : en base, Comitech seulement. Filet avant/après sur les quatre sociétés : zéro écart hors des salariés de Comitech en arrêt sous le barème.
- Les rappels déjà saisis en octobre (24/10 : S.G., D.S., D.J. chez Comitech ; M.G. chez Colorplast) sont des montants saisis, que le moteur ne recalcule pas. Les corriger, c'est écrire en base : sur accord d'Alexandre, après un calcul au bac à sable.

## Hors champ

- La déduction de la prévoyance (part employeur) et des indemnités d'un tiers responsable (art. 13 g) : elle attend les décomptes.
- La métallurgie (n° 12) : 100 % du brut, plafonné au net (art. 91.1.3). C'est une autre forme de règle (un plafond, pas une garantie nette), à coder avec son barème.

## Tests (TDD)

- Garantie nette : versé × (1 − t) + IJ × (1 − s) = garanti × (1 − t), au centime ; IJ brutes affichées inchangées.
- Subrogation : même déduction nette.
- Sans subrogation, réglage éteint : garanti en entier, aucune réduction.
- Légal retenu : versé inchangé, lecture brute.
- Sans barème : résultat identique, clé pour clé.
- La mesure du taux ne modifie pas le contexte, et rend `None` sans jours maintenus.
- Les cas de Comitech au centime de Quadra (lecture brute) deviennent des cas au centime de la règle nette.
