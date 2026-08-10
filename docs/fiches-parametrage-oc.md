# Fiches de paramétrage des organismes complémentaires

**10/08/2026, mission B.** 14 fiches récupérées sur net-entreprises pour les
quatre SIREN du compte tiers-déclarant. Rangées en
`data/<societe>/referentiel/fpoc/` (gitignoré).

Ce sont les documents que chaque organisme complémentaire dépose pour dire
comment déclarer ses contrats en DSN. C'est la source qui manquait au bloc
prévoyance de notre export, et elle répond aussi à une question restée en
suspens chez Elsa.

## Ce que chaque société a

| Société | Organismes |
|---|---|
| **Colorplast** | Alptis (×2), MUTEX, AG2R Santé, La Mondiale, baloo |
| **Comitech** | Alptis (×2), MUTEX, AG2R Santé, La Mondiale, baloo |
| Mont Blanc Composite | baloo, prévoyance cadres |
| MAJI | APICIL, prévoyance |

Cartol, LEWIS et Zone 404 n'apparaissent pas : leurs SIREN ne sont pas rattachés
au compte.

## La correspondance est donnée, pas devinée

Les fiches PDF **portent les numéros de rubrique DSN en tête de colonne**, et le
XML les reprend un pour un :

| Champ de la fiche | Rubrique DSN | Ce que c'est |
|---|---|---|
| `Contrat/ReferenceContrat` | `S21.G00.15.001` | Référence du contrat, au niveau établissement |
| `Organisme/CodeOC` | `S21.G00.15.002` | Code organisme |
| `Organisme/CodeDELEG` | `S21.G00.15.003` | Code délégataire |
| `Option/CodeOption` | `S21.G00.70.004` | Option, au niveau de l'affiliation |
| `Population/CodePopulation` | `S21.G00.70.005` | Population — `CA` cadre, etc. |
| `ElementsDeCalculAttendus` | — | Taux tranche A et B, ou montant forfaitaire |

**Deux blocs, pas un.** Le `S21.G00.15` déclare les contrats de l'établissement,
avant les individus ; le `S21.G00.70` rattache chaque salarié à l'un d'eux. Nous
n'émettons ni l'un ni l'autre, d'où la cascade d'anomalies sur les blocs 78, 79
et 81 relevée par DSN-VAL.

**Ce que les fiches ne contiennent pas** : l'identifiant technique d'affiliation
(`S21.G00.70.012`). Il est construit par l'émetteur, pas fourni par l'organisme.
C'est à nous de l'attribuer et de le maintenir stable.

## Une question d'Elsa réglée au passage

Le 05/08, on lui demandait : « sur l'OD Colorplast il y a deux comptes de
prévoyance, 43740000 Mutex et 43741000 Alptis, quelle cotisation va sur
lequel ? » (point #26).

Les fiches tranchent :

- **Alptis** — contrat `PSCACBA0041711`, population `CA`, libellé « Cadre ».
  Cotisation tranche A et B, taux 1,18 % et 1,17 % depuis le 01/01/2025.
- **MUTEX** — contrat `NSI517762`, libellé « salariés ne relevant pas des
  articles 2.1 et 2.2 », c'est-à-dire les **non-cadres**.

Donc : **Mutex pour les non-cadres, Alptis pour les cadres.** Plus besoin de le
demander.

## Ce qu'il reste à faire

Les paramètres sont là, il manque le lien par salarié. `AffiliationBlock`
existe déjà (`builder.py:561`) mais se nourrit de
`specificites_paie.mutuelle`, qui est vide.

1. Charger les paramètres des fiches dans une configuration par société.
2. Rattacher chaque salarié à sa population — le plus souvent déductible de son
   statut cadre / non-cadre, exactement le découpage que portent les fiches
   Colorplast et Comitech.
3. Émettre les blocs 15 et 70, puis attribuer et conserver les identifiants
   techniques d'affiliation.

C'est ce qui lèvera les ~1 000 anomalies de la cascade prévoyance dans
`docs/dsn-val-diagnostic.md`.

## Un défaut à signaler à l'organisme

La fiche baloo de **Colorplast** porte le libellé de contrat de **Comitech**
(« FORMULE COLLECTIVE COMITECH ENSEMBLE DU PERSONNEL »). La référence de contrat
est bien celle de Colorplast (`10000802485169`), seul le libellé est faux. Sans
conséquence pour la DSN, mais à signaler.
