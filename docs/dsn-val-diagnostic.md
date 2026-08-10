# DSN-VAL — ce que le validateur officiel reproche à notre export

**10/08/2026.** Première passe de nos DSN dans **DSN-VAL 2026.1.0.16**, l'outil
de contrôle de la CNAV distribué par net-entreprises. Il répond à la question du
point #20 : *qu'est-ce qui empêche notre DSN d'être déposable ?*

Jusqu'ici on ne savait que mesurer un **écart** avec le fichier du cabinet
(`dsn_conformance_report.py`). On sait maintenant mesurer une **conformité**.
Ce n'est pas la même chose : sur Colorplast, l'écart au cabinet tenait en
5 rubriques manquantes, quand le validateur en trouve 602 bloquantes.

## Le résultat

| Société | Première passe | Tri des rubriques | + 4 blocs et rubriques | Cabinet |
|---|---|---|---|---|
| Cartol | 7 250 | 1 378 | **1 035** | 0 |
| Mont Blanc Composite | 6 027 | 1 196 | **904** | 0 |
| LEWIS | 3 355 | 632 | **469** | 0 |
| Comitech | 1 502 | 294 | **227** | 0 |
| Colorplast | 628 | 106 | **78** | 0 |
| **Total** | **18 762** | **3 606** | **2 713** | **0** |

Soit **86 % des anomalies levées**, et 34 règles ramenées à 23.

## La cause racine : un ordre, pas un contenu

**15 156 anomalies sur 18 762 venaient d'une seule ligne de code.**

La norme NEODeS impose des rubriques **par numéro croissant** à l'intérieur d'un
bloc. Un lecteur qui rencontre un numéro inférieur au précédent tient le bloc
pour terminé, et déclare absentes toutes les rubriques qui suivent — même
écrites juste en dessous.

Or `_emit_rubriques_dict` émettait « dans l'ordre d'insertion » du dictionnaire.
Notre bloc contrat sortait `.019`, puis `.017`, `.018`, `.020`, `.039`… et
`.016` tout à la fin. D'où 10 575 « absences » de rubriques toutes présentes.

Le fichier du cabinet, lui, est strictement croissant partout.

Détail qui a levé une fausse piste : le cabinet écrit lui aussi
`S21.G00.40.009,'00000'` comme numéro de contrat, et passe à zéro. Les 675
« deux contrats portent le même numéro » ne venaient donc pas de cette valeur
mais du désordre, qui fabriquait des contrats fantômes.

Corrigé dans `domain/writer.py`, verrouillé par deux tests dans
`test_writer_structure.py`.

## Puis quatre manques, tous systématiques

**893 anomalies de plus, levées le 10/08.** Aucune ne demandait quoi que ce soit
au cabinet : les correspondances ont été **dérivées de ses DSN acceptées**, pas
supposées.

| Ajout | Ce que c'est | Règle retenue |
|---|---|---|
| `S21.G00.30.013` | Codification UE | France `01`, UE `02`, EEE et Suisse `03`, reste `04` — vérifié contre les nationalités réelles |
| `S21.G00.40.003` | Statut catégoriel Retraite Complémentaire | cadre → `01`, non-cadre → `04`, sans exception sur 219 contrats |
| `S21.G00.71` | Retraite complémentaire | `RUAA`, le régime unifié AGIRC-ARRCO, seul déclaré par le cabinet sur les sept sociétés |
| `S21.G00.86` | Ancienneté dans l'entreprise | type `07`, en mois révolus depuis l'entrée |

Le bloc 71 avait d'abord été rangé à tort avec la prévoyance : c'est **la
retraite complémentaire**, il ne dépendait donc d'aucune fiche de paramétrage.
Sans lui, le statut catégoriel `40.003` est refusé quelle que soit sa valeur.

Un second piège d'ordre au passage : le bloc ancienneté était émis **avant** le
versement, le cabinet le place après. Le validateur le réclame à cette place.

Les 5 151 tests unitaires passent.

**Le témoin est parfait.** Les cinq fichiers du cabinet, réellement déposés et
acceptés, passent à zéro anomalie. Le validateur ne bruite pas : nos anomalies
sont toutes les nôtres.

**Et elles se comptent en règles, pas en lignes** : 34 au départ, 25 après le
tri, les mêmes sur les cinq sociétés. Ce n'est jamais un chantier de plusieurs
milliers de corrections.

## Ce que la question #17 à Elsa devient

Le point #20 demandait au cabinet « la nomenclature officielle des codes de
cotisation, sans elle notre DSN reste non déposable ». **Le validateur donne le
diagnostic sans elle.** Il nomme chaque rubrique manquante et chaque règle
violée, avec le libellé officiel.

C'est le même schéma que le fichier BIC et la provision CP : la réponse était de
notre côté. La question peut être retirée, ou réduite à ce qui restera après
correction.

## Ce qui reste : 2 713 anomalies, 23 règles

Le détail vit dans `data/_dsn_conformance/_rapports_dsnval/` (gitignoré, il
contient des NIR). Presque toutes tombent à **une par salarié** — 225 salariés
sur les cinq sociétés — c'est-à-dire un élément systématiquement absent, jamais
un cas particulier.

### En attente de la mission B — la prévoyance, ~1 050 anomalies

Quatre règles liées, une seule cause : **le bloc S21.G00.70 / 71** (affiliation
prévoyance et sa période) n'est pas émis. Le code existe pourtant
(`builder.py:561`) ; il ne produit rien parce que les affiliations ne sont pas
reliées — la même cause racine que le backtest Comitech.

Ce qu'il faudra : identifiant technique d'affiliation sur les bases de type 31,
cohérence entre l'affiliation et le contrat, un composant par base de type 31,
et une cotisation « 059 » et une seule. Les **fiches de paramétrage OC**
apportent ces références.

### Corrigeable sans rien attendre — ~2 550 anomalies

| Règle | Occ. | Ce qu'il manque |
|---|---|---|
| `S21.G00.81.001/CCH-17` | 450 | Le **montant du SMIC retenu** pour la réduction générale, sous la base de type 03 |
| `S21.G00.81.002/CCH-11` | 411 | Identifiant OPS renseigné à tort quand une cotisation « 059 » est déclarée |
| `CST-03 S21.G00.30.013` | 349 | Rubrique jamais émise du bloc individu |
| `S21.G00.53.001/CCH-12` | 225 | Le bloc activité « 40 - jours calendaires » est rattaché à une rémunération qui n'est pas la brute non plafonnée |
| `S21.G00.50.008/CCH-11` | 225 | Le taux PAS n'est admis que si le type vaut « 01 — transmis par la DGFiP » |
| `S21.G00.50.001/CCH-14` | 225 | **Bloc S21.G00.58 type 03, le montant net social** — obligatoire depuis 2023 |
| `S21.G00.86.001/CCH-14` | 225 | **Bloc ancienneté**, type 07 « dans l'entreprise » |
| `CST-03 S21.G00.40.003` | 225 | Rubrique jamais émise du bloc contrat |

Le montant net social est déjà calculé par la paie (`builder.py:136`) : c'est
la sérialisation qui manque, pas la donnée. L'ancienneté se déduit des dates
d'entrée.

### Avertissements, non bloquants

Taux AT/MP à renseigner dès que le code risque ≠ 999ZZ, nombre d'heures absent
sur les rémunérations de type heures supplémentaires, motif de recours absent
sur un CDD.

## Rejouer le diagnostic

```bash
cd backend
venv/bin/python scripts/dsn_generer_pour_validation.py   # écrit les 5 sociétés
venv/bin/python scripts/dsn_valider.py --tout            # valide et dépouille
venv/bin/python scripts/dsn_valider.py --rapports-seuls  # redépouille seulement
```

L'installation de DSN-VAL et le contournement macOS sont documentés en tête de
`backend/scripts/dsn_valider.py`. L'outil pèse 110 Mo, il vit dans
`data/_outils/dsnval/` et n'est pas versionné.

**Aucune donnée n'est sortie du poste** : DSN-VAL est une application locale, la
validation ne fait aucun appel réseau.

## Ce que ça vaut comme jalon

Un compteur d'anomalies par société, qui doit tomber à zéro. C'est la première
mesure de conformité DSN qu'on ait qui ne dépende ni du cabinet, ni d'un dépôt
réel.
