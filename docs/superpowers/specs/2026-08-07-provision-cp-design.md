# Export « État de provision des congés payés »

**Date** : 2026-08-07
**Point** : `docs/afaire.md` #23
**Statut** : validé

## Constat

Elsa a demandé « un export de calcul de provision des congés payés » et le compte rendu
du 26/07 indiquait « demander fichier exemple à ELSA ». Le fichier exemple **était déjà
là** : elle l'a envoyé deux fois sur WhatsApp, le 21/07/2026 (« à discuter asap ») puis
le 27/07/2026 avec la consigne « doc provision CP à mettre en export »
(`data/_inbox/whatsapp-elsa/_chat.txt:8769` et `:8963-8964`). Les deux envois du 27/07
sont le même fichier au bit près.

Le modèle est un état Cegid **« État de provision des congés payés »**, société CARTOL,
édité le 21/07/2026 par MV, exercice 01/01/2026 → 31/12/2026, 2 pages, **71 salariés**,
total **394 121,22 €**.

Aucun export de ce type n'existe dans EYWAI : les 24 types du module
`backend/app/modules/exports/` couvrent le journal de paie, les charges, les OD, la DSN,
les virements — `conges_absences` est une liste d'absences validées sur un mois, pas une
valorisation.

### Formules du modèle — vérifiées sur 71/71 lignes

| Colonne | Origine |
|---|---|
| Solde jrs N-1 | Solde de congés de la période précédente, en **jours ouvrés** |
| Solde jrs N | Acquis de la période en cours, en jours ouvrés |
| Solde jours | `N-1 + N` — exact sur 71/71 |
| Salaire de référence | Brut mensuel moyen sur la période d'acquisition |
| Taux Ch. soc. | Cotisations patronales ÷ brut, **par salarié** |
| Montant charges sociales | `provision × taux ÷ 100` — exact sur 71/71 |
| Provision | `solde jours × salaire de référence ÷ 22` — exact sur 71/71, diviseur médian 22,0000 |
| Total | `provision + charges` — exact sur 71/71 |

Le solde N vaut 4,16 j pour tout le monde, soit exactement 2 mois × 2,08 j (25 j ouvrés
par an ÷ 12). L'état est donc arrêté au **31/07/2026** sur une période d'acquisition qui
démarre au 1er juin.

### Ce que la rétro-ingénierie a confirmé, et ce qu'elle n'a pas pu confirmer

**Taux de charges sociales — confirmé.** `cotisations patronales ÷ brut` par salarié,
calculé sur nos bulletins 2026 (`payslip_data.cotisations_officielles[].total_patronal`
sur `payslip_data.salaire_brut`), tombe à 0,1–0,25 point du PDF pour les salariés dont
la paie est stable : De Carvalho 32,14 % / 32,12 %, Vignaud 38,38 % / 38,50 %, Veillat
24,70 % / 24,57 %, Tamime 22,48 % / 22,68 %, Picard 33,32 % / 33,53 %. Écart médian sur
les 61 salariés stables : 1,13 point, entièrement imputable à la période de référence
tronquée (voir ci-dessous).

**Salaire de référence — identifié, non prouvé au centime.** C'est le brut mensuel moyen
sur la période d'acquisition. Sur les 61 salariés à paie stable, 24 tombent à ±5 % en
n'utilisant que nos 6 mois de 2026. Les écarts violents sont **exclusivement** des cas
d'absence longue, et ils vont dans les deux sens :

| Salarié | Solde N-1 | Notre moyenne 2026 | PDF | Lecture |
|---|---|---|---|---|
| BOISSINOT | 88,00 j | 2 045 € | 385 € | Absent en 2025, revenu en 2026 |
| QUERAT | 81,00 j | 1 996 € | 1 141 € | Idem |
| LEMAIRE L | 54,00 j | 2 065 € | 1 356 € | Idem |
| DIGUET | 28,00 j | 522 € | 2 915 € | Présent en 2025, absent en 2026 |

C'est la signature d'une période de référence couvrant juin 2025 → mai 2026, dont EYWAI
ne détient que les 5 derniers mois. **La preuve au centime ne sera possible qu'à partir
de juin 2027**, quand EYWAI aura douze mois d'historique de paie.

### Périmètre du modèle

71 lignes au PDF contre 86 bulletins Cartol en juin 2026 (108 salariés en base). Les
absents du PDF sont tous des salariés **actifs embauchés après le début de la période
d'acquisition** (RENAUD 09/2025, SICAUD 11/2025, BREMENT 12/2025, SEGUIN 04/2026,
ALVES 04/2026, LEGRIP 05/2026…). Cegid les exclut ; nous ne les exclurons pas — ils ont
des droits acquis, donc une dette. Point à signaler à Elsa, pas à reproduire.

## Objet

Un nouvel export `provision_cp` dans le module `exports`, qui produit pour une société et
une date d'arrêté la valorisation en euros de la dette de congés payés, salarié par
salarié, au format du modèle Cegid — plus les colonnes de traçabilité qui manquent au
modèle.

Non couvert : l'écriture comptable de la provision (compte 428/438), la comparaison
d'un arrêté à l'autre, la provision RTT / JTC / CET.

## Architecture

### Nouveau fichier `backend/app/modules/exports/infrastructure/export_provision_cp.py`

Deux fonctions publiques, comme les 23 autres exports :

```
preview_provision_cp(company_id, period, employee_ids=None) -> dict
generate_provision_cp_export(company_id, period, employee_ids=None, file_format="xlsx") -> bytes
```

`period` est au format `AAAA-MM` et vaut arrêté au dernier jour du mois. `preview`
renvoie le contrat commun des 23 autres exports : `employees_count`, `totals`,
`anomalies`, `warnings`, `can_generate`, `details`.

Le calcul pur est isolé dans `backend/app/modules/exports/domain/provision_cp.py` —
fonctions sans accès base, donc testables au centime sans mock.

### Calcul, par salarié

1. **Soldes.** `compute_cp_balances_for_bulletin(hire_date, validated, as_of_date, …)`
   (`app/modules/absences/domain/`), déjà utilisé par le bulletin et le fractionnement,
   renvoie `periode_precedente.solde` et `periode_en_cours.solde` en jours **ouvrables**.
   Conversion en ouvrés par `ouvrables_to_ouvres(solde, ratio)`, le ratio venant des
   réglages congés de la société (25/30 par défaut). Le modèle Cegid est en ouvrés.
2. **Période de référence.** Les 12 mois glissants qui précèdent `as_of_date`, bornés à
   la date d'embauche. Les mois sans bulletin sont ignorés, et leur nombre est reporté
   dans une colonne « Mois retenus ».
3. **Salaire de référence.** Moyenne de `payslip_data.salaire_brut` sur les mois retenus.
   Zéro mois retenu ⇒ repli sur le salaire contractuel, et la ligne est signalée.
4. **Taux de charges.** `Σ total_patronal ÷ Σ salaire_brut × 100` sur les mêmes mois.
   Zéro mois retenu ⇒ repli sur le taux moyen de la société, ligne signalée.
5. **Provision.** `solde jours ouvrés × salaire de référence ÷ diviseur`, arrondi au
   centime. Diviseur = 22 par défaut, réglable par société.
6. **Charges.** `provision × taux ÷ 100`, arrondi au centime. **Total** = somme des deux.

### Périmètre

Salariés **actifs à la date d'arrêté** (`employment_status = 'actif'`, embauche ≤ arrêté,
pas de sortie avant), **solde total > 0**. Les salariés sortis dans la période sont hors
périmètre : leur solde a été soldé en indemnité compensatrice, il n'y a plus de dette.

### Colonnes produites

Celles du modèle — Matricule, Nom, Solde N-1, Solde N, Solde jours, Salaire de référence,
Taux Ch. soc., Montant charges sociales, Provision, Total — plus quatre colonnes que le
modèle Cegid n'a pas et qui évitent de devoir croire l'export sur parole : **Société**,
**Date d'entrée**, **Mois retenus** (ex. « 6/12 »), **Anomalie** (vide, ou « aucun
bulletin », « salaire contractuel utilisé », « taux société utilisé »).

Ligne **Total** en dernier, comme le modèle : somme des soldes, des montants, et taux
moyen pondéré.

### Paramètres

Le diviseur (22) et la fenêtre de référence (12 mois) restent des **constantes du
domaine**, exposées comme arguments par défaut de la fonction de calcul pour être
testables. Pas de réglage par société en v1, pas de migration : nous avons un seul
modèle et une seule convention de cabinet. Si une autre société suit une autre règle, on
les remontera dans `company_leave_settings` à ce moment-là.

### Câblage (six points, identiques à tout export existant)

1. `domain/value_objects.py` — `provision_cp` dans `EXPORT_TYPES_PREVIEW` et `EXPORT_TYPES_GENERATE`
2. `schemas/requests.py` — le littéral de type d'export
3. `application/queries.py` — branche `preview`
4. `application/service.py` — branche `generate` + `_generate_provision_cp`
5. `infrastructure/providers.py` — les deux ré-exports
6. Frontend — `ExportCommonModel.tsx`, `ExportHistory.tsx`, et l'onglet RH `ExportsRhTab.tsx`

### Écran

L'export reprend le sélecteur de période mensuelle commun aux 23 autres : la période
`AAAA-MM` est interprétée comme un **arrêté au dernier jour du mois**. Aucun composant
frontend nouveau, aucun changement du contrat d'API.

Un avertissement renvoyé par la prévisualisation tant que l'historique est incomplet :
« Salaire de référence calculé sur N mois sur 12 — EYWAI ne contient de la paie que
depuis janvier 2026. »

## Traitement des erreurs

- **Aucun bulletin sur la période** : ligne produite avec le salaire contractuel, colonne
  Anomalie remplie. Jamais d'exclusion silencieuse.
- **Solde négatif** (congés pris d'avance) : provision négative, conservée telle quelle —
  c'est une créance, elle réduit la dette. Signalée en Anomalie.
- **Salarié sans date d'embauche** : exclu, et compté dans un avertissement d'en-tête.
- Aucune exception avalée : le défaut corrigé sur les exports CSE (#12) venait exactement
  de là.

## Tests

- Les quatre formules, sur les valeurs réelles de trois lignes du PDF (BERTAUD, BLIN,
  FAUCHER), au centime.
- Conversion ouvrables → ouvrés avec un ratio non standard.
- Salarié sans bulletin : repli contractuel + Anomalie.
- Salarié embauché en cours de période : « 3/12 » en Mois retenus.
- Solde nul : hors périmètre. Solde négatif : dans le périmètre, provision négative.
- Ligne Total : somme exacte, taux moyen pondéré.
- Test de non-régression sur le fichier CARTOL : les 71 lignes du PDF se rapprochent, et
  l'écart total est mesuré et consigné — pas asserté, tant que 2025 manque.

## Réserves

1. **La preuve au centime attendra juin 2027.** Sans les bulletins 2025, le salaire de
   référence des salariés à absence longue restera faux. À signaler à Elsa plutôt qu'à
   masquer : la colonne « Mois retenus » est là pour ça.
2. **Le diviseur 22 est une convention Cegid**, pas une règle légale. La règle légale est
   le maximum entre le maintien de salaire et le 1/10e de la rémunération de la période de
   référence. Nous reproduisons le modèle du cabinet parce que c'est ce qu'Elsa a demandé,
   pas parce que c'est la seule méthode.
3. **Le périmètre diffère volontairement du modèle** : Cegid omet les embauches récentes,
   nous les incluons. L'écart sur Cartol serait d'une quinzaine de lignes.
4. Un seul modèle, une seule société, une seule date : rien ne garantit que le cabinet
   édite le même état pour les six autres sociétés.

## Mesure du 07/08/2026 contre le modèle Cegid

Script : `backend/scripts/provision_cp_comparer_modele.py`, société Cartol, période
2026-07, modèle `00000595-PROVISION CP.pdf`.

| | Modèle Cegid | EYWAI |
|---|---|---|
| Lignes | 71 | 87 |
| Rapprochées | — | 64 |
| Total valorisé (lignes rapprochées) | 362 080,89 € | 247 827,98 € |

Écart : **−114 252,91 €, soit −31,6 %**.

| Champ | Écart médian | Écart max |
|---|---|---|
| Solde jours | 6,19 j | 66,36 j |
| Salaire de référence | 268,12 € | 6 100,48 € |
| Taux de charges | 1,13 pt | 25,12 pt |
| Provision | 1 038,69 € | 10 524,70 € |

**Deux causes, toutes deux des trous de données, aucune un défaut du calcul.**

1. **Le solde de la période précédente n'est pas repris.** C'est la cause principale.
   Notre N-1 vaut 20,8 à 22,5 jours pour tout le monde — un droit théorique d'année
   pleine recalculé — quand le modèle va de 3 à 88 jours. EYWAI ne contient aucun congé
   antérieur à janvier 2026, donc aucun report réel. Même trou que les soldes de départ
   du JTC (point #8).
2. **Le salaire de référence est calculé sur 6 mois au lieu de 12** (constat 4 de la
   spec), ce qui décale surtout les salariés qui ont eu une absence longue en 2025.

Le solde de la période **en cours** est juste : 4,17 j chez nous contre 4,16 j au modèle,
soit un pur arrondi de la conversion ouvrables → ouvrés. Le taux de charges est juste
lui aussi à 1,13 point près, écart imputable à la même fenêtre tronquée.

Conséquence : l'export porte un avertissement permanent sur les reports non repris. Il
sera exact quand les soldes de report auront été chargés une fois, et le salaire de
référence le sera à partir de juin 2027.

## Reprise des reports depuis l'état du cabinet

L'état de provision porte lui-même le solde de report, salarié par salarié, en jours
ouvrés. Il n'y a donc rien à demander à Elsa pour Cartol : la donnée manquante est dans
le fichier qu'elle a déjà envoyé.

`backend/scripts/reprise_soldes_cp_cabinet.py` la charge dans
`employee_leave_adjustments`. Trois points de conception :

1. **On enregistre un écart, pas un report brut.** Le moteur fait
   `n1 = acquis − pris + cp_n1_opening_balance` ([rules.py:555](backend/app/modules/absences/domain/rules.py#L555)) :
   l'ajustement s'ajoute au solde théorique. Écrire le report brut le compterait deux
   fois. Le script écrit `report réel − théorique`, le théorique étant recalculé
   ajustement neutralisé — donc **relancer le script ne cumule rien**.
2. **Lecture en colonnes fixes.** Le numéro de collaborateur occupe les 18 premières
   colonnes et porte parfois une lettre de désambiguïsation (« COUTANT D »,
   « LEMAIRE JN », « LEMAIRE L »). Un découpage par espaces la prend pour un prénom et
   casse le rapprochement : c'est ce qui laissait 7 lignes sur 71 non rapprochées.
   Couvert par `backend/tests/unit/exports/test_reprise_soldes_cp.py`.
3. **Tout ou rien.** Le script refuse d'écrire si une seule ligne n'est pas rapprochée.
   Simulation par défaut, `--apply` pour écrire.

Simulation du 07/08/2026 sur Cartol : **71 lignes sur 71 rapprochées, aucun refus**, y
compris Marie-Noëlle ENOND retrouvée par son nom d'usage DEPLANNE. Le théorique vaut
25,00 j ouvrables pour les 71, ce qui confirme le diagnostic. Écarts extrêmes :
BOISSINOT +75,60 j, QUERAT +67,20 j, PENAUD −12,00 j.

### Effet mesuré, à vide

| | Solde jours, écart médian | Exacts | Total EYWAI | Écart au cabinet |
|---|---|---|---|---|
| Avant reprise | 6,19 j | 0/64 | 247 827,98 € | −114 252,91 € (−31,6 %) |
| Après reprise | **0,01 j** | **51/64** | 318 099,26 € | −43 981,63 € (−12,1 %) |

Le résidu de 0,01 j est l'arrondi de conversion ouvrables → ouvrés (4,17 contre 4,16).
Les −12,1 % restants sont le salaire de référence calculé sur 6 mois au lieu de 12 :
c'est la part qui ne se réglera qu'en juin 2027.

**Rien n'a été écrit en production.** Les six autres sociétés n'ont pas d'état de
provision : leurs reports restent à demander à Elsa.
