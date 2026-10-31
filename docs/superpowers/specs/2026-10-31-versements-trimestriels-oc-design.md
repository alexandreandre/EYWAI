# Versements trimestriels de prévoyance et de mutuelle en DSN

Date : 31/10/2026. Feuille de route du 30/10, chantier 1, étape 3 : « décembre si (DSN due le 15/01/2027) : à coder avant ».

## Ce que disent les sources

- FAQ DSN Organismes complémentaires, net-entreprises, V4 d'octobre 2023, p. 47-48 (téléchargée le 31/10) : pour une échéance trimestrielle à terme échu, chaque DSN mensuelle déclare les cotisations individuelles (blocs 78, 79, 81). La DSN du **dernier mois du trimestre** porte en plus un bloc 20 et ses blocs 55 « pour le montant des cotisations dues du trimestre » ; la somme des 55 égale le 20.005 ; 55.004 = `AAAATnn` (« solution préférée »). Les modalités de paiement (mode, périodicité, date) « ne doivent pas être modifiées unilatéralement ».
- Même FAQ : le type de population (55.002) ne se renseigne que si l'organisme le demande, avec ses propres codes.
- Description des rubriques (reprise par payrooll.com) : pour un organisme complémentaire, 20.006 et 20.007 sont une « donnée non exploitée, à renseigner au 01012000 » ; 20.011 est la date du prélèvement SEPA.

## Ce que faisait Quadra (DSN de mars et juin des deux sociétés)

- Mars et juin seulement : un bloc 20 par organisme (AGGEEV, prévoyance ; ALMRS1, mutuelle), 20.006 et 20.007 à 01012000, 20.008 = délégataire, mode 05, 20.011 = le 25 du mois qui suit le trimestre.
- Un bloc 55 par contrat de l'organisme, même à 0,00 : montant, type de population de la fiche de l'organisme (« 00 », « NON CADRE », « CADRE », « 11 »), référence du contrat, `2026T01` ou `2026T02`.
- Le montant est la somme des cotisations individuelles 059 du contrat sur les trois mois : au centime chez Comitech au deuxième trimestre (4 457,79, 1 008,74, 1 017,43 €). Les écarts relevés tiennent à des mois de démarrage (contrats déclarés à partir de mars) et à un appel forfaitaire de l'organisme chez Colorplast en avril-mai.

## Ce que fait Martine aujourd'hui

Les cotisations individuelles sont déclarées chaque mois. Aucun bloc 20 n'est produit pour un organisme complémentaire, avec un avertissement chaque mois.

## La règle

- Au dernier mois d'un trimestre civil, pour chaque organisme complémentaire du paramétrage des versements : un bloc 20 (montant = somme des 55 ; 20.006 et 20.007 à 01012000 ; délégataire, IBAN, BIC et mode repris ; 20.011 le jour de paiement repris du cabinet, du mois qui suit) et un bloc 55 par contrat de l'organisme (bloc 15), même à zéro, avec le type de population s'il est paramétré.
- Montant d'un contrat : ses cotisations individuelles de base 31 sur les trois mois du trimestre (via 78.005 → bloc 70 → 70.013 → ordre du contrat). Les deux mois précédents sont recalculés comme leur DSN, depuis leurs bulletins.
- Si un mois du trimestre est antérieur à la bascule (payé par l'ancien logiciel), le versement n'est pas produit et l'export le dit : il se déclare à la main ce trimestre-là.
- Hors fin de trimestre : rien, et plus d'avertissement.
- Reprise du cabinet : le jour de paiement (20.011) et le type de population de chaque contrat (55.002) sont désormais lus dans la DSN du cabinet ; un script porte ceux de juin dans le paramétrage de Colorplast et Comitech (écriture sur accord).

## Tests

- Domaine : fin de trimestre, période d'affectation, date de paiement, somme par contrat (base 31 seulement, autres affiliations ignorées), bloc 20 et ses 55, contrat à zéro, type de population absent ou présent.
- Écriture : les 55 suivent leur 20, rubriques croissantes.
- Constructeur : décembre produit les versements ; novembre n'en produit pas et n'avertit plus ; trimestre qui touche la bascule : pas de versement, avertissement.
- Preuve : DSN-VAL sur un fichier de fin de trimestre.
