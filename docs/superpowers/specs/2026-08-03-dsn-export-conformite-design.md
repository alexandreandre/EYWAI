# Conformité complète de la sortie DSN

Date : 2026-08-03
Sujet : `docs/afaire.md` #20
Statut : lots 1 et 2 livrés, lots 3 à 6 à faire (voir §9)

## 1. Objectif

Rendre le fichier DSN produit par EYWAI déposable tel quel sur net-entreprises,
en remplacement de celui du cabinet, volet paiement inclus.

`afaire.md` :

> #20. Numéro NIR bons ELSA. Sortie DSN de chez nous à checker MOI

Le volet NIR est traité et documenté séparément (§7). Le présent document ne
couvre que la sortie DSN.

## 2. État constaté le 2026-08-03

Généré la DSN mensuelle EYWAI de mai 2026 pour trois sociétés et comparé au
fichier réellement déposé par le cabinet le même mois :

| Société | Rubriques EYWAI | Rubriques cabinet | Manquantes | En trop |
| --- | --- | --- | --- | --- |
| Colorplast | 75 | 175 | 100 | 0 |
| Comitech | 75 | 179 | 104 | 0 |
| Cartol | 75 | 195 | 120 | 0 |

Aucune rubrique en trop : notre sortie est un sous-ensemble strict. Les défauts
tombent en cinq familles.

**Structure.** Le bloc `S90.G00.90` (total du fichier) n'est écrit nulle part —
ni le writer ni le parser ne le connaissent. Un fichier sans ce bloc est rejeté
au contrôle de structure. Manquent aussi le contact émetteur (`S10.G00.01`) et
le contact déclaration (`S20.G00.07`).

**Individu et contrat.** Le bloc contrat sort sans IDCC (`40.017`), sans
dispositif public (`40.003`), sans statut conventionnel (`40.018`) ni lieu de
travail (`S21.G00.85`). Le bloc individu sort sans département ni pays de
naissance (`30.014`, `30.015`).

**Cotisations individuelles.** Les parts salariale et patronale d'une même ligne
sont émises en deux blocs `S21.G00.81` de même code, même assiette, même taux et
même montant, donc indistinguables pour le récepteur. Sur un cas mesuré, le
cabinet déclare une ligne 059 de 22,74 € là où nous en produisons deux de
11,37 €. Les codes 071, 072, 102, 106 et 907 ne sont jamais produits.

**Agrégés URSSAF.** Les blocs `S21.G00.23` (cotisations agrégées), `S21.G00.22`
(bordereau) et `S21.G00.20` (versement) sont entièrement absents. C'est le volet
qui porte le paiement.

**Prévoyance et événements.** Absents également : adhésion prévoyance
(`S21.G00.15`), affiliations (`44`, `70`), fin de contrat (`62`), arrêt de
travail (`65`), ancienneté (`86`), bases assujetties `58` et `79`, autres
revenus `54`, `60`, `71`.

Point aggravant : cet export est exposé aux utilisateurs dans Exports →
« DSN mensuelle », sans avertissement.

## 3. Ce qui existe déjà et qu'on ne réécrit pas

`dsn_export/domain/writer.py` sait déjà sérialiser presque tous les blocs
manquants : `AffiliationBlock`, `VersementOrganismeBlock`, `BordereauBlock`,
`CotisationAgregeeBlock`, `ArretTravailBlock`, `FinContratBlock`,
`OrganismePscBlock`, `AncienneteBlock`. Le modèle vient de `dsn_import`, dont le
parser lit déjà 46 rubriques des blocs 20, 22, 23, 70, 15, 44, 62 et 65.

Le défaut n'est donc pas dans la sérialisation mais dans
`dsn_export/application/builder.py`, qui n'alimente pas ces blocs. Le chantier
consiste à les remplir, pas à les créer. Seul `S90.G00.90` est à ajouter au
writer (et au parser, pour que la relecture le voie).

## 4. Méthode de validation

Deux oracles, décidés avec Alexandre.

**Les DSN réelles du cabinet, oracle de contenu.** On dispose de plus de 40
fichiers couvrant les 7 sociétés, tous acceptés par net-entreprises. Pour un
mois et une société donnés, on génère notre fichier, on parse les deux, on les
normalise en arbre de blocs et on diffe. Un écart non justifié est un bug.

**DSN-VAL, filet structurel.** L'outil officiel de net-entreprises couvre les
contrôles que nos fichiers d'exemple ne rencontrent pas. Il est branché en fin
de chaque lot, hors CI (il demande Java et une installation locale).

### Écarts volontaires

L'oracle contient des erreurs : le contrôle des NIR a montré que le cabinet
déclare 8 salariés avec un sexe contredit par leur propre NIR. Se conformer
aveuglément reviendrait à recopier ses fautes.

Le harnais porte donc une liste d'écarts délibérés, chacun avec sa
justification, son périmètre et sa date. Un écart non déclaré fait échouer le
test ; un écart déclaré est affiché dans le rapport, jamais silencieux.

Premier écart inscrit : le sexe déclaré (`S21.G00.30.005`) est déduit du NIR
quand celui-ci le contredit, et non recopié du champ `sexe` de la fiche.

## 5. Architecture

Trois composants nouveaux, chacun testable isolément.

### 5.1 Paramétrage société — `company_dsn_settings`

Porte ce qui ne vient pas de la paie : organismes de protection sociale et
identifiants d'adhésion, contacts émetteur et déclaration, références bancaires
et mode de paiement du versement URSSAF, options d'affiliation.

Alimenté par reprise automatique depuis la dernière DSN du cabinet importée,
puis éditable. Chaque champ conserve sa source (`reprise_dsn` ou `saisie`) et sa
date d'origine, pour qu'on sache toujours ce qui est vérifié et ce qui est
hérité.

Exposé par `dsn_export/domain/settings.py`. Le builder ne lit jamais la table
directement.

### 5.2 Agrégats URSSAF — `dsn_export/application/aggregates.py`

Calcule les blocs 23, 22 et 20 depuis les bulletins du mois : regroupement des
cotisations individuelles par code de cotisation agrégée et par organisme,
bordereau par organisme, versement rattaché.

Séparé du builder individuel : il travaille sur l'établissement, pas sur le
salarié, et c'est le seul composant qui touche au paiement.

### 5.3 Harnais de conformité — `backend/tests/dsn/conformance/`

Trois pièces :

- un normaliseur, qui transforme un fichier DSN en arbre de blocs comparable
  (ordre des rubriques neutralisé, montants comparés au centime) ;
- un différentiel, qui produit un rapport lisible : rubriques manquantes, en
  trop, valeurs divergentes, regroupées par bloc ;
- les cas de test, un par société et par mois disponible.

**Les fixtures ne vont pas dans le dépôt.** Il est public, et les entrées
contiennent l'état civil et la paie de 289 personnes. Elles vivent sous
`data/_dsn_conformance/<societe>/<mois>/`, gitignoré comme le reste de `data/`,
et sont produites par `backend/scripts/dsn_conformance_snapshot.py` depuis la
base. Les tests se marquent `skipped` si les fixtures sont absentes : la CI
reste verte, l'exécution locale reste complète.

## 6. Découpage

Six lots, chacun clos par un diff vert sur les sociétés couvertes.

1. **Structure** — `S90.G00.90` (writer et parser), contacts `S10.G00.01` et
   `S20.G00.07`, complément des en-têtes `S10`, `S20.G00.05`, `S21.G00.06` et
   `S21.G00.11`.
2. **Individu et contrat** — état civil complet, IDCC, dispositif, statut
   conventionnel, lieu de travail `S21.G00.85`, sexe recoupé au NIR.
3. **Cotisations individuelles** — fin des doublons salarial/patronal, codes
   manquants, bases `58` et `79`.
4. **Agrégés URSSAF** — blocs `23`, `22`, `20`.
5. **Prévoyance** — adhésions `15`, affiliations `44` et `70`.
6. **Événements** — fin de contrat `62`, arrêt de travail `65`, ancienneté `86`,
   autres revenus `54`, `60`, `71`.

Tant que le lot 6 n'est pas clos, l'export reste marqué non déposable dans
l'interface : un fichier incomplet qui se présente comme valide est plus
dangereux qu'un export absent.

## 7. Contrôle des NIR (volet Elsa)

Vérifié le 2026-08-03 sur les 240 salariés actifs : aucun NIR vide, clé de
contrôle correcte partout, un seul NIR à 13 chiffres (légitime en DSN). Comparés
aux 275 individus des DSN du cabinet de mai 2026, 274 correspondent au chiffre
près.

Trois anomalies, toutes venant du cabinet et recopiées par notre import :

- 8 salariés déclarés avec un sexe que leur propre NIR contredit ;
- 2 salariés dont le mois de naissance diverge du NIR ;
- 1 salarié déclaré chez Cartol sur les cinq DSN de 2026 et absent d'EYWAI.

Le détail nominatif est hors dépôt (dépôt public). À remonter à Elsa.

## 8. Hors périmètre

- La DSN événementielle (arrêt de travail signalé hors cycle mensuel, fin de
  contrat unitaire). Seul le mensuel est visé.
- La télétransmission automatique vers net-entreprises. Le module
  `net_entreprises` existe et n'est pas touché ici.
- La correction des données du cabinet listées au §7 : c'est une décision
  d'Elsa, pas un changement de code.

## 9. État au 2026-08-03

### Livré

**Harnais de conformité.** `dsn_export/domain/conformance.py` compare notre
fichier à celui du cabinet rubrique par rubrique, avec périmètre par lot et
écarts délibérés déclarés. Piloté par `scripts/dsn_conformance_report.py`,
vérifié par `tests/unit/dsn_export/test_conformance_reelle.py` sur cinq
sociétés (Cartol, Colorplast, Comitech, LEWIS, Mont Blanc Composite), mai 2026.
MAJI et Zone 404 n'ont pas de bulletin sur ce mois en base.

**Paramétrage société.** Table `company_dsn_settings`, reprise automatique
depuis la dernière DSN du cabinet par `scripts/dsn_settings_reprise.py`. Les
sept sociétés sont reprises et complètes. La migration n'est pas encore
appliquée : la lecture retombe sur un paramétrage vide sans faire échouer la
génération.

**Lot 1 — structure.** Bloc total `S90.G00.90`, fins de ligne CRLF, apostrophe
non doublée, émetteur et contacts, NAF sans séparateur, IDCC d'établissement.

**Lot 2 — individu et contrat.** Zéro valeur divergente sur les cinq sociétés.
Corrigés au passage : le numéro de contrat qui portait le nom du salarié, la
quotité figée à 151,67 h quelle que soit la durée réelle, le forfait annuel en
jours déclaré en heures, l'apprentissage déclaré comme une nature de contrat
propre au lieu d'un CDD porteur du dispositif 65.

**Garde-fou.** `dsn_export/domain/etat_conformite.py` : tant que `DEPOSABLE`
est faux, le fichier sort suffixé `_NON_DEPOSABLE` et la vérification
pré-export porte une anomalie bloquante qui liste ce qui manque.

### Reste à faire

**Lot 3 — cotisations individuelles.** Bloqué, et c'est le point à trancher.
Nous émettons les parts salariale et patronale en deux blocs `S21.G00.81`
identiques là où le cabinet en émet un seul, et nous ne produisons pas les
codes 071, 072, 102, 106 et 907. Aligner demande la nomenclature officielle des
codes de cotisation DSN : sans elle, on déclarerait des cotisations fausses à
l'URSSAF. Il faut soit le cahier technique P26V01, soit l'arbitrage d'Elsa ou
du cabinet sur la correspondance entre nos lignes de bulletin et ces codes.

**Lots 4 à 6.** Agrégés URSSAF, prévoyance, événements. Ils dépendent du lot 3
pour les montants et de données absentes de la base (organismes de prévoyance,
coordonnées bancaires du versement).

**Rubriques à documenter.** `S21.G00.30.013`, `.017`, `.025`, `.029`,
`S21.G00.40.003`, `.010`, `.021`, `.072`. Le cabinet les déclare, nous ne
savons pas ce qu'elles portent. Elles sont listées dans le test plutôt
qu'inventées.

## 10. Écarts de données relevés

Trouvés en comparant notre base aux DSN du cabinet. Aucun n'est un défaut du
générateur ; tous demandent un arbitrage.

- **12 salariés au forfait annuel en jours ne sont pas marqués comme tels**
  (5 Cartol, 7 LEWIS). Le cabinet en déclare 31, notre base en connaît 19.
  L'effet dépasse la DSN : RTT, décompte du temps, congés.
- **19 contrats Cartol dépendent d'un autre SIRET** (798 171 096 00034) que
  celui de la société. Le rattachement multi-établissement n'est pas modélisé.
- **32 salariés sortis** sont encore déclarés par le cabinet le mois de leur
  solde de tout compte et absents de notre DSN.
- **1 salarié déclaré chez Cartol sur les cinq DSN de 2026 n'existe pas dans
  EYWAI.**
- **Mont Blanc Composite** : une date de début de contrat, trois libellés
  d'emploi et deux niveaux conventionnels divergent entre nos fiches et celles
  du cabinet.
- **Code NAF de Colorplast** : `25.61Z` en base, `2229A` déclaré par le
  cabinet. C'est le second qui est cohérent avec la plasturgie.
