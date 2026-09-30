# Rappels sur les grands principes déclaratifs du SMIC servant au calcul de la la RGDU (Réduction Générale Dégressive Unique) en bloc « Composant de base assujettie - S21.G00.79 »
Source : https://net-entreprises.custhelp.com/app/answers/detail_dsn/a_id/2522/ — consulté le 29/09/2026

Base de connaissances net-entreprises, fiche n° 2522. « Date de création : 08/09/2021 », « Date de modification : 09/06/2026 06:13 PM ».

Texte intégral de la fiche, copié de net-entreprises (menus, liens et boutons retirés ; texte inchangé, y compris « la la RGDU » et les espaces manquantes de la page d'origine).

---

Quels sont les grands principes pour déclarer le SMIC servant au calcul de la RGDU en DSN ?

## Le contexte

Cette fiche vise à rappeler les grands principes de déclaration du SMIC utilisé pour le calcul de la réduction générale dégressive unique (RGDU) porté en DSN. Ce montant permet aussi de déterminer l'éligibilité du contrat pour lequel l'employeur bénéficie du dispositif.

Cela concerne le bloc « Composant de base assujettie - S21.G00.79 » de type 01, à savoir :

•    « Type de composant de base assujettie - S21.G00.79.001 » : 01 - Montant du SMIC retenu pour le calcul de la Réduction générale des cotisations patronales de sécurité sociale, de retraite complémentaire, d'assurance chômage et de la réduction de cotisation Allocations familiales

•    « Montant de composant de base assujettie - S21.G00.79.004 » : Montant à positionner par le déclarant.

## Déclarer le SMIC pour le calcul de la RGDU pour un contrat

Il est déclaré au niveau du bloc« Composant de base assujettie - S21.G00.79 » de type «01 » :

- « Type de composant de base assujettie - S21.G00.79.001 » : 01 - Montant du SMIC retenu pour le calcul de la Réduction générale des cotisations patronales de sécurité sociale, de retraite complémentaires et d’assurance chômagepour un contrat.

Dans le cas d’un salarié éligible à la réduction générale dégressive uniquedes cotisations patronales (RGDU) et titulaire de plusieurs contrats de travail surle même mois et le même établissement, le calcul du SMIC doit se faire pour chacun des contrats (les numéros de contrats devant être renseignésdans chaque Bloc bloc « Base assujettie - S21.G00.78 » sauf si lescontrats de l’individu salarié obéissent aux mêmes règles pour le calcul des cotisations).Pour un contrat en CDD, renouvelé ou  transformé en CDI sur une même année, il sera nécessaire de calculer la RGDU sur l’ensemble de la période§1080 du BOSS.

Le SMICRGDU doit être rattachémensuellementà chaque période sur laquelle le dispositif de réduction est appliquéet nonen cumul annuel.

Le SMIC doit être rattaché au bloc « Base assujettie - S21.G00.78 » de type « 03 - Assiette brute déplafonnée »

## Proratisation du SMIC pour le calcul de la RGDU

Le SMIC RGDU doit être proratisé en fonction du temps de travail (temps partiel, durée de travail inférieure à la durée légale), et en cas d’absence (les consignes attendues pour la calcul de la RGDU en cas d’absence sont détaillées dans la Fiche Consigne 2681 Réduction générale et absence : Quels sont les grands principes pour proratiser le SMIC ?)

En cas d’absence du salarié, la valeur corrigée du SMIC RGDU  doit tenir compte des heures supplémentaires structurelles résultant d’une durée collective de travail ou d’une convention de forfait supérieures à la durée légale.

## Heures supplémentaires et complémentaires

Le montant du SMIC (calculé pour un an sur la base de la durée légale du travail) est augmenté du nombre d’heures supplémentaires ou complémentaires effectuées et exonérées socialement (rémunérées au moins comme une heure normale, réalisées au-delà de la durée légale de 35h hebdomadaires et respectant les règles légales et conventionnellesrelatives à la durée de travail).

Ainsi,les heures supplémentaires et complémentaires sont déclarées dans le bloc « Rémunération - S21.G00.51 »pour le type« 017 - Heures supplémentaires ou complémentaires aléatoires ».

Pour considérer au plus juste les heures supplémentaires et complémentaires qui comptent dans le calcul du SMIC RGDU, certaines heures doivent êtreexcluesnotamment :

-     Les heures supplémentaires qui dépassent légalement le seuil légal en cas de situation d’urgence, de convention ou d’accord ouqui bénéficient d’une dérogationde l’inspection du travail,
-      Les heures supplémentaires inférieures à la durée de temps de travail légal à temps plein,
-      Les heures complémentaires effectuéesau-delà de la limite légale ou conventionnelle.

Ces heures particulières doivent être déclarées isolément au niveau du bloc « Rémunération - S21.G00.51 » de type « 036 - Heures supplémentaires ou complémentaires aléatoires à exclure du calcul d'un dispositif de réduction ou d'exonération de cotisations de Sécurité sociale ».

Point d’attention : Les heures supplémentaires récupérées sous la forme de repos compensateur ne sont pas attendues en DSN puisqu’elles ne conduisent pas à rémunération.

## Salariés avec majoration pour horaires particuliers

Certains salariés doivent rester à la disposition de leur employeur sans que cela ne représente un travail effectif. Ils peuvent percevoir à ce titre une rémunération supplémentaire dont le SMIC doit tenir compte. Ces cas particuliers concernent les conducteurs courtes ou longues distances relevant du secteur de transport routiers de marchandises ou de voyageurs.

•    Salariés relevant du secteur de transport des voyageurs (heures de « coupure » et de pause, garantie mensuelle minimale d'amplitude)

Il est admis que la valeur du SMIC servant au calcul de la réduction générale dégressive unique peut être majorée pour tenir compte des temps de coupures / pause rémunérés et des temps au-delà de l’amplitude de 12 heures (garantie mensuelle d'amplitude), qui ne constituent pas du temps de travail effectif. Elles sont considérées au même titre que les heures supplémentaires pour le calcul et l'application de la réduction.

Ainsi, la rémunération de ces temps est convertie en heures. Ces heures doivent être indiquées dans le bloc « Rémunération - S21.G00.51 » type « 013 - Heures d’habillage, déshabillage, pause ».

Exemple : un salarié roulant « voyageur » dont la durée de travail effectif est de 35 heures hebdomadaire. Il bénéficie de 4 heures de temps de coupure rémunérées chacune à 50 % d’une heure de travail et effectue 3 heures supplémentaires, le SMIC est alors majoré de 2 heures de temps de coupures (4 heures à 50 %) et de 3 heures supplémentaires.

-    Salariés relevant du secteur de transport de marchandises (heures d’équivalence)

Lorsque le salarié est soumis à un régime d’heures d'équivalences payées à un taux majoré en application d’une convention ou d’un accord collectif étendu, le SMIC est corrigé du rapport 45/35 pour les conducteurs routiers longue distance et du rapport 40/35 pour les conducteurs routiers courte distance.

Cette correction s’applique pour la réduction générale dégressive unique des cotisations et contributions patronales à la valeur du SMIC figurant au numérateur avant la prise en compte des heures supplémentaires et complémentaires.

Point d’attention : La majoration appliquée aux salariés intérimaires et aux salariés relevant de professions dans lesquelles le paiement des congés payés est mutualisé entre les employeurs affiliés aux caisses de compensation, ne doit pas être prise en compte dans le calcul du SMIC RGDU mais dans le calcul final du coefficient de réduction générale dégressive unique.

-      Salariés sans horaire au contrat

Le montant du SMIC RGDU est déterminé à partir du nombre de jours travaillé par le salarié, converti en heure sur la base de 7 heures par jour. Ce montant ne peut jamais résulter de la prise en compte d’une durée supérieure à la durée légale du travail ou à la durée collective applicable dans l’établissement où est employé le salarié.

Lorsque la détermination du nombre de jours travaillés n’est pas possible, la valeur du SMIC RGDU est prise en compte sur la base de la durée légale du travail ou par la durée collective applicable dans l’établissement où est employé le salarié.

## La réglementation (Textes de lois, BOSS, etc.)

Allègements généraux - Boss.gouv.fr

BOSS, Allègements généraux.

S’agissant des heures supplémentaires structurelles à réintégrer au calcul du SMIC RGDU : points 5.5, 6.2 et 6.3 de la circulaire DSS SD5B du 1er janvier 2015

Les consignes visant le rattachement des éléments de rémunération sont alignées sur les règles énoncées par la Direction de la Sécurité sociale pour l'interprétation du fait générateur en conformité avec la mise à jour du BOSS publiée en juin 2025. Les règles seront opposables à partir du 1er Janvier 2027 après une phase transitoire sur l'année 2026.
