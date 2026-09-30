# Cahier technique DSN CT2026.1.2 — blocs S21.G00.79 et S21.G00.81 (réduction générale)
Source : https://www.net-entreprises.fr/media/documentation/dsn-cahier-technique-2026.1.pdf — consulté le 29/09/2026 (copie locale : `docs/audit-maji-2026/sources/dsn-cahier-technique-2026.1.pdf` et `.txt`, version « CT2026.1.2 », datée du 24/12/2025)

Le PDF n'a pas été téléchargé à nouveau le 29/09/2026 : le texte ci-dessous est extrait de la copie déjà présente dans le dépôt (dossier de l'audit MAJI), dont l'adresse d'origine figure dans `docs/audit-maji-2026/sources/consultations-web-completes.json`. La date « consulté le » est celle de la relecture de cette copie.

Extraits intégraux utiles, recopiés du texte brut de la copie locale, page par page ; seuls les retours à la ligne, l'indentation et les en-têtes ou pieds de page du PDF ont été retirés. « […] » marque un passage omis (autres organismes, prévoyance).

---

## Principes de constitution des messages (p. 47)

« - Les composants de base assujettie constituant des parties de bases assujetties autres que des éléments de revenu brut (par exemple, le montant du SMIC retenu pour le calcul de la Réduction générale des cotisations patronales de sécurité sociale et d'assurance chômage)

- Les montants d’assiettes cotisées, exonérées ou éligibles à réduction

La norme NEODeS n’offre plus de possibilité de bordereaux annuels au titre des cotisations de Sécurité Sociale. Cette disposition traduit l’abandon de régularisation annuelle au profit systématique de la régularisation progressive. »

## Bloc S21.G00.79 « Composant de base assujettie » (p. 298-300)

« Composant de base assujettie — S21.G00.79

Composante de la base assujettie déterminée selon des règles différentes de celles utilisées pour l'établissement d'éléments de revenu brut.

Pour les organismes autres que Prévoyance, ce bloc n'est à renseigner que dans le cas où les éléments de revenu brut sont insuffisants pour constituer la base assujettie. Ce cas peut notamment se présenter lorsqu'une base assujettie est composée, d'une part, d'éléments de revenu brut et, d'autre part, de composants ne donnant pas lieu à versement au salarié.

[…]

Type de composant de base assujettie — S21.G00.79.001 (BaseComposant.Type)

Le type de composant de base assujettie constitue son identifiant. Il permet de donner une signification au montant de composant de base assujettie.

Modalité de valorisation :
- AGIRC-ARRCO : "01", "03"
[…]
- France Travail : "01"
- Urssaf : "01", "02", "03", "04", "05", '06", "07", "22"
[…]

CCH-14 : Si la rubrique "Type de composant de base assujettie - S21.G00.79.001" est renseignée avec la valeur "01 - Montant du SMIC retenu pour le calcul de la Réduction générale des cotisations patronales de sécurité sociale, de retraite complémentaire, d'assurance chômage et de la réduction de cotisation Allocations familiales", alors elle doit être rattachée à un bloc "Base assujettie - S21.G00.78" dont la rubrique "Code de base assujettie - S21.G00.78.001" est de type "03 - Assiette brute déplafonnée" ou de type "19 - Assiette CRPCEN".

[…]

01 - Montant du SMIC retenu pour le calcul de la Réduction générale des cotisations patronales de sécurité sociale, de retraite complémentaire et d'assurance chômage
02 - Montant du SMIC retenu pour le calcul du crédit d'impôt compétitivité-emploi
[…]

Montant de composant de base assujettie — S21.G00.79.004 (BaseComposant.Montant)

Le montant porte la valeur telle que prise en compte pour l'établissement des bases assujetties constituées pour partie par un composant de base assujettie.

Modalité de valorisation :
- AGIRC-ARRCO : montant
[…]
- France Travail : montant
- Urssaf : montant
[…] »

## Bloc S21.G00.81 « Cotisation individuelle » (p. 301-308)

« Cotisation individuelle — S21.G00.81

Une cotisation individuelle est un dispositif de contribution à la protection sociale dont le montant est fixé soit proportionnellement à la base assujettie, soit de manière forfaitaire. […] La cotisation individuelle est toujours rattachée à une base assujettie. Ainsi, la cotisation individuelle est toujours valorisée au titre de la période de rattachement de la base assujettie. […]

Le bloc s'applique également aux exonérations et réductions de cotisations individuelles.

Code de cotisation — S21.G00.81.001 (CotisationIndividuelle.CodeCotisation)

Code identifiant la nature de la donnée attendue par l'organisme au titre de la période de rattachement concernée.

Modalité de valorisation :
- AGIRC-ARRCO : "105" (pour régularisation des périodes antérieures à 2025), "106", "109", "110", "111", "112", "113", "131", "132", "915"
[…]
- Urssaf : "001", "002", "003", […] "017" ,"018", "019", […]

[…]

CCH-16 : Si la rubrique "Code de cotisation - S21.G00.81.001" est renseignée avec la valeur "018 - Réduction générale des cotisations patronales et d'assurance chômage" ou "106 - Réduction générale des cotisations patronales de retraite complémentaire", alors les rubriques "Montant d'assiette - S21.G00.81.003" et "Montant de cotisation - S21.G00.81.004" doivent être renseignées.

CCH-17 : Si la rubrique "Code de cotisation - S21.G00.81.001" est renseignée avec la valeur "018 - Réduction générale des cotisations patronales et d'assurance chômage" ou "106 - Réduction générale des cotisations patronales de retraite complémentaire", alors un bloc "Composant de base assujettie - S21.G00.79" de type "01 - Montant du SMIC retenu pour le calcul de la Réduction générale des cotisations patronales de sécurité sociale, de retraite complémentaire, d'assurance chômage et de la réduction de cotisation Allocations familiales" doit obligatoirement être rattaché au même bloc "Base assujettie - S21.G00.78" parent portant la rubrique "Code de base assujettie - S21.G00.78.001" renseignée avec la valeur "03 - Assiette brute déplafonnée".

Ce contrôle vise à ce qu'une réduction générale des cotisations patronales ou une réduction générale des cotisations patronales de retraite complémentaire et le montant du SMIC retenu pour le calcul de la Réduction générale des cotisations patronales de sécurité sociale, de retraite complémentaire, d'assurance chômage et de la réduction de cotisation Allocations familiales soient déclarés sous un même bloc parent "Base assujettie - S21.G00.78" de type "03 - Assiette brute déplafonnée".

[…]

018 - Réduction générale des cotisations patronales de sécurité sociale et d'assurance chômage
[…]
106 - Réduction générale des cotisations patronales de retraite complémentaire
[…]

Montant d'assiette — S21.G00.81.003 (CotisationIndividuelle.MontantAssiette)

Montant total des sommes éligibles à cotisation individuelle, exonération ou réduction de cotisation individuelle.

Modalité de valorisation :
- AGIRC-ARRCO : à renseigner pour une réduction, exonération
[…]
- Urssaf : à renseigner pour une cotisation, exonération, réduction
[…]

Montant de cotisation — S21.G00.81.004 (CotisationIndividuelle.MontantRéductionExonération)

Montant de la cotisation individuelle, réduction de cotisation individuelle ou exonération de cotisation individuelle pour la période de rattachement.

Modalité de valorisation :
- AGIRC-ARRCO : à renseigner pour une cotisation, réduction
[…]
- Urssaf : à renseigner pour une cotisation, réduction
[…] »

---

Notes de lecture (pas du texte officiel) :
- le cahier technique dit où déclarer le SMIC retenu (bloc 79, type 01, sous la base 78 de type 03) et les deux montants de réduction (bloc 81, code 018 pour l'Urssaf, code 106 pour l'Agirc-Arrco) ; il ne dit pas comment répartir la réduction entre 018 et 106 : cette règle est à l'article D. 241-7, VI (`css-d241-7.md`), au § 1160 du BOSS (`boss-rgdu.md`) et dans la fiche Urssaf (`urssaf-rgdu.md`) ;
- la fiche net-entreprises 2522 précise que le SMIC du bloc 79 est déclaré mois par mois, pas en cumul (`netentreprises-fiche-2522.md`) ;
- la note différentielle CT2026.1 → CT2027.1 (https://www.net-entreprises.fr/media/documentation/dsn-P27V01-note-differentielle-CT2026.1-CT2027.1.pdf) n'a pas été récupérée ; un résultat de recherche du 29/09/2026 indique seulement qu'elle renomme les libellés 018 et 106 en « Réduction générale dégressive unique… » pour 2027.
