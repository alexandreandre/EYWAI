# Base assujettie et cotisations individuelles : renseigner les blocs 78, 79 et 81
Source : https://net-entreprises.custhelp.com/app/answers/detail_dsn/a_id/1265/ — consulté le 29/09/2026

Base de connaissances net-entreprises, fiche n° 1265. « Date de création : 26/01/2017 », « Date de modification : 08/07/2026 11:29 AM ». La fiche décrit la norme P27V01 (2027) et renvoie, pour la norme P26V01 en production, à un tableau Excel non récupéré (https://www.net-entreprises.fr/media/documentation/base-assujettie-et-cotisations-individuelles-p26v01.xlsx).

Extrait intégral utile, copié de net-entreprises (menus, liens et boutons retirés, texte inchangé). Sont reproduits : le contexte et l'exemple 1 (réduction générale). Ne sont pas reproduits : la liste des organismes, les exemples 2 et 3 (exonération CAE, retraite complémentaire) et le point d'attention sur la retraite supplémentaire.

---

Comment procéder à la déclaration des cotisations au niveau de la maille nominative ?

## Le contexte

Dans les messages DSN, le bloc « Base assujettie - S21.G00.78 » est parent des blocs « Composant de base assujettie - S21.G00.79 » et « Cotisation individuelle - S21.G00.81 ».

Les règles de rattachement d’un bloc « Composant de base assujettie - S21.G00.79 » ou d’un bloc « Cotisation individuelle - S21.G00.81 » sous un bloc « Base assujettie - S21.G00.78 » ont, dans la majorité des cas, une justification métier. Ceci signifie que le calcul de la cotisation individuelle repose sur une base assujettie spécifique.

De même, la déclaration d’un composant de base assujettie est liée à la présence d’une base assujettie et/ou d’une cotisation individuelle.

[…]

Si un type de cotisation est à destination de plusieurs organismes il convient de ne le déclarer qu’une seule fois au moyen d’un seul bloc « Cotisation individuelle – S21.G00.81 ». Les règles de filtrage mises en place dans le SI DSN permettent de distribuer la cotisation à tous les organismes destinataires de cette cotisation.

A défaut, si la même cotisation est déclarée au moyen de plusieurs occurrences de blocs « Cotisation individuelle – S21.G00.81 », la cotisation sera prise en compte par l’organisme destinataire autant de fois qu’elle aura été déclarée et sera exigible en conséquence.

## Illustrations : Aide à la lecture du tableau Excel

Exemple 1 : Réduction Générale des cotisations

En cas de déclaration d’une « Réduction générale des cotisations patronales de sécurité sociale », la MSA, l’Urssaf CN et l'Agirc-Arrco attendent la déclaration des éléments suivants en DSN :

-      Un bloc « Base assujettie - S21.G00.78 » dont la rubrique « Code de base assujettie - S21.G00.78.001 » est valorisée à « 03 - Assiette brute déplafonnée ».
-      Un bloc « Composant de base assujettie - S21.G00.79 » dont la rubrique « Type de composant de base assujettie - S21.G00.79.001 » est renseignée à « 01 - Montant du SMIC retenu pour le calcul de la Réduction générale des cotisations patronales de la sécurité sociale ».
-      Deux blocs « Cotisation individuelle - S21.G00.81 » dont la rubrique « Code de cotisation - S21.G00.81.001 » est valorisée à « 018 - Réduction générale des cotisations patronales de sécurité sociale » et à « 106 - Réduction générale des cotisations patronales de retraite complémentaire ».

[…]

\[ATTENTION\] : Les exemples présentés au niveau des fiches de consignes ne reflètent pas l'exhaustivité des cas possibles.
