# Prime transport paramétrable et plafonds de frais professionnels

Date : 2026-08-02
Sujet : `docs/afaire.md` #15
Statut : conception validée, implémentation à planifier

## 1. Objectif

Permettre à la RH de définir une fois la prime de transport d'un salarié, puis
de la retrouver chaque mois dans les primes, déjà calculée et modifiable.

Demande d'Alexandre, formulée dans `afaire.md` :

> #15. Prime transport réglable dans les primes via l'interface (pas forcément
> tous les mois donc pouvoir paramétrer manuellement)

Réponses d'Elsa, le 2026-08-01 :

> Pour colorplast c est sur les contrat trajet boulot domicile
> C est un montant défini par Michaël, il y a des avenants signé
> Idem pour mbc
> La liste est complète pour mbc
> Pour la question 6 si absent tous les mois on enlève
> Question 7 prorata
> Question 4 toujours même montant

Cinq contraintes en découlent :

1. C'est du **trajet domicile-travail**, pas du frais de déplacement
   professionnel. Le régime d'exonération applicable est celui des frais de
   transport domicile-travail, plafonné et annuel.
2. Le montant est **contractuel** : défini par avenant signé. Sa place est la
   fiche salarié, pas une saisie mensuelle retapée.
3. Le montant est **stable** pour un salarié donné.
4. Absence sur tout le mois : **on ne verse pas**.
5. Entrée ou sortie en cours de mois : **prorata**.

L'instruction de périmètre d'Alexandre, après mesure d'impact, est de traiter
les quatre blocs dans #15, y compris les plafonds.

## 2. Hors périmètre

- Le remboursement à 50 % de l'abonnement de transport public
  (`transport.abonnement_mensuel_total`), obligation légale distincte, qui
  fonctionne et concerne 2 salariés de Mont Blanc Composite à 36 €. On n'y
  touche pas, mais le bloc 4 doit tenir compte de son cumul avec la prime.
- Le forfait mobilités durables comme dispositif à part entière (déclaration,
  justificatifs, modes de transport éligibles). On n'implémente que le plafond.
- Le code de rubrique comptable des saisies : `export_code` est vide sur les
  1 000 saisies de la base. Sujet réel, mais qui relève de #26 (interfaçage
  compta). Elsa doit encore répondre sur ce point.
- La liste des bénéficiaires chez Colorplast. Elsa a confirmé la complétude
  pour Mont Blanc Composite uniquement (§ 8.1).
- Le versement mobilité (`taux_vmrr`), cotisation patronale sans rapport malgré
  la proximité de vocabulaire.

## 3. État des lieux

Constats établis par lecture de la base de production le 2026-08-02.

### 3.1 Trois mécanismes concurrents, aucun satisfaisant

| Mécanisme | Emplacement | Comportement | Usage réel |
|---|---|---|---|
| `transport.abonnement_mensuel_total` | Fiche salarié | 50 % automatique, tous les mois | 2 salariés MBC à 36 € |
| `transport.indemnite_mensuelle_nette` | Fiche salarié | Montant net fixe, tous les mois | **0 salarié** |
| Saisie mensuelle en texte libre | Saisies > Primes | Ce que la RH tape | 7 salariés, 3 sociétés |

Le champ contractuel `indemnite_mensuelle_nette` fait déjà exactement ce que
#15 demande sur le principe — il est lu par
`backend/app/modules/payroll/engine/calcul_net.py:460-469` et ajouté au net à
payer. Mais il est invisible dans les primes, non proratisé, insensible aux
absences, et **personne ne s'en sert**. La RH lui préfère la saisie manuelle,
qui a le mérite d'être visible.

Le fait que 0 salarié l'utilise est structurant : on peut en changer le
comportement sans aucun risque de régression en production.

### 3.2 La réalité de la saisie manuelle

| Société | Libellé | Salariés | Montant | Rythme |
|---|---|---|---|---|
| Colorplast | `Indemnite de transport` / `Indemnité de transport` | ESPINOSA Anthony, GIRERD Fabrice | 100 € / 250 € | Tous les mois, jan→juin |
| Mont Blanc Composite | `Indemnité forfaitaire dep.` | MEUNIER Cyril, SALAUN Ronan, CHAABANE Sihem, GUELAI Mackael | 100 € / 150 € | Intermittent |
| Comitech Composite | `Indemnité de transport` | GARCIA Mickael (parti) | 125 € | Février seulement |

Trois défauts se cumulent :

- Le libellé est retapé chaque mois, avec deux orthographes qui coexistent chez
  Colorplast (`Indemnite` / `Indemnité`) selon le mois.
- Le libellé Mont Blanc Composite (`dep.` pour déplacement) **désigne mal** ce
  qu'il contient : Elsa confirme que c'est du trajet domicile-travail, comme
  chez Colorplast.
- Toutes ces lignes sont posées non soumises à cotisations et non imposables,
  sans aucun contrôle de plafond.

Les montants Colorplast sont ancrés sur les bulletins Cegid réels
(`backend/scripts/backtest/colorplast_setup.py:42-52`), établis pendant le
backtest à partir des bulletins et de la DSN. Ils sont donc fiables, et
confirment la stabilité annoncée par Elsa.

### 3.3 Le moteur de règles existe et n'est pas utilisé

`backend/app/modules/payroll_variables/` implémente un générateur de variables
mensuelles : des règles par entreprise produisent des `monthly_inputs`, via le
bouton « Préparer variables du mois » de Saisies > Primes et la carte « Règles
variables paie » de Entreprise > Paie.

Il comporte déjà un type `fixed_monthly` (« Montant fixe mensuel ») et un mode
`suggest` (« Suggestion uniquement (aperçu) ») qui n'écrit rien.

**Zéro règle existe en production.** La raison est visible dans
`backend/app/modules/payroll_variables/domain/rules.py:49-68` :
`employee_matches_conditions` ne sait filtrer que sur `statuts` et
`exclude_statuts`, c'est-à-dire Cadre / Non-Cadre. Il est impossible de viser
deux salariés nommés avec deux montants différents — exactement notre cas.

Le catalogue `company_bonus_types` est également quasi vide : 2 lignes, toutes
deux liées aux médailles du travail chez Comitech.

### 3.4 Les plafonds d'exonération ne sont jamais appliqués

Constat vérifié en exécutant la fonction du moteur sur la configuration
réellement active :

```
type frais_pro vu par le moteur : dict | clés: ['FRAIS_PRO']
exoneration_repas(...) -> None
  indemnite_de_transport   montant=250.0 -> exonéré=250.0  réintégré=0.0  plafond=None
  panier_repas             montant= 20.0 -> exonéré= 20.0  réintégré=0.0  plafond=None
```

`backend/app/modules/payroll/engine/calcul_frais.py:20` lit
`frais_pro["sections"]["repas"]`. Or aucune version stockée de `payroll_config`
n'a jamais eu de clé `sections` au premier niveau :

| Version | Date | Forme de `config_data` |
|---|---|---|
| 1 | 2025-10-31 | sections à la racine (`repas`, `mobilite_durable`, …) |
| 2 | 2025-11-03 | `{"FRAIS_PRO": [{"id", "libelle", "sections"}]}` |
| 3 | 2026-05-29 | idem v2 |
| 4 (active) | 2026-06-02 | idem v2 |

La fonction lit une forme qui n'existe pas. Conséquence : `plafond = None` dans
tous les cas, donc `reintegration_exces` renvoie 0, et toute la branche
« Réintégration NDF » de
`backend/app/modules/payroll/documents/payslip_run_heures.py:392-403` est du
code mort.

Cela n'a jamais été détecté parce que les montants saisis ont été calés sur les
sorties Cegid pendant les backtests. EYWAI reproduit le bon résultat sans
faire le contrôle : il recopie, il ne vérifie pas.

### 3.5 `payroll_quantity` porte deux sémantiques opposées

Mesure sur les 114 saisies panier non soumises de la base :

| Libellé | Lignes | `payroll_quantity` | Signification réelle | Valeur unitaire |
|---|---|---|---|---|
| `Paniers Jours non soumis` (J majuscule) | 62 | 7.5 systématiquement | **valeur** unitaire | 7,50 € |
| `Paniers jours non soumis` (j minuscule) | 39 | 1, 2, 4, 5, 6, 8… | **nombre** de paniers | 7,40 € |
| `Paniers nuits non soumis` | 8 | 1, 4, 7, 8, 9, 12… | **nombre** de paniers | 7,40 € |
| `Paniers repas chauffeur` | 4 | 10, 13, 20, 29 | **nombre** de repas | 15,00 € |
| `Indemnité de panier` | 1 | 4 | **nombre** de paniers | 5,00 € |

Soit 114 lignes au total : 62 portent une valeur unitaire, 52 portent un
nombre. Deux conventions inverses, dont la principale se distingue par une
seule majuscule. Le moteur calcule `unit = montant / quantity` sans
distinction, ce qui produit des valeurs unitaires fausses (jusqu'à 22 € au lieu
de 7,50 €) sur les 62 lignes Mont Blanc Composite.

Conséquence pour le bloc 4 : **réparer le plafond sans corriger d'abord cette
sémantique réintégrerait à tort sur 62 lignes.** L'ordre des blocs 3 puis 4
n'est pas négociable.

Une fois les quantités interprétées correctement, les valeurs unitaires réelles
sont 5,00 €, 7,40 €, 7,50 € et 15,00 €. Toutes sont inférieures ou égales au
plafond le plus élevé du barème actif (21,40 €, hors locaux avec restaurant).
La réparation du plafond ne déplace donc **aucun euro** sur les paniers, à
condition de ne pas durcir le plafond retenu en même temps (§ 7.2).

### 3.6 Le plafond transport est annuel, le moteur ne sait pas cumuler

Le barème actif porte, dans `mobilite_durable.employeurs_prives` :

| Plafond | Valeur |
|---|---|
| `limite_base` | 600 €/an |
| `limite_cumul_transport_public` | 900 €/an |
| `limite_cumul_carburant_total` | 600 €/an |
| `limite_cumul_carburant_part_carburant` | 300 €/an |

Ces valeurs sont scrapées depuis l'URSSAF, stockées, affichées dans « Suivi des
taux » — et **jamais lues par `backend/app/`**. Aucune occurrence de
`mobilite_durable` ni de `limite_cumul_*` hors de `backend/scraping/`.

Le montant de la prime, lui, n'est pas scrapé : 100 €, 250 €, 125 € et 150 € ne
correspondent à aucun barème. Ce sont des décisions de l'employeur, conformes à
ce qu'annonce Elsa (avenants signés par Michaël).

Toute la mécanique d'exonération existante raisonne **ligne par ligne et mois
par mois**. Le plafond transport est **annuel et cumulatif par salarié**. Il
n'existe aucun cumul année-à-date exploitable dans le moteur. C'est la pièce la
plus lourde du lot.

Montants annuels constatés, à rapprocher d'un plafond de 600 à 900 € :

| Salarié | Société | Mensuel | Annualisé |
|---|---|---|---|
| GIRERD Fabrice | Colorplast | 250 € | 3 000 € |
| ESPINOSA Anthony | Colorplast | 100 € | 1 200 € |
| MEUNIER Cyril | Mont Blanc Composite | 100 € | 1 200 € |

## 4. Bloc 1 — Le montant contractuel

On réutilise `specificites_paie.transport.indemnite_mensuelle_nette`, déjà
présent sur la fiche salarié sous le libellé « Indemnité transport
contractuelle (€ net/mois) », déjà câblé au moteur, et utilisé par personne.

Ajouts :

- Une date d'effet, qui matérialise l'avenant. Sans elle, un changement de
  montant réécrirait rétroactivement les mois déjà produits — le même piège que
  le SMIC non daté déjà identifié sur la base.
- Le champ devient la source de vérité unique du montant. On ne duplique pas
  vers le catalogue de primes.

Le libellé de l'écran doit dire « trajet domicile-travail » plutôt que
« transport », pour couper court à la confusion avec les frais de déplacement
professionnel qu'entretient le libellé actuel de Mont Blanc Composite.

## 5. Bloc 2 — La ligne mensuelle générée

« Préparer variables du mois » génère une ligne « Indemnité de transport » par
salarié dont le champ du bloc 1 est renseigné et dont la date d'effet est
atteinte.

Montant généré :

- Montant contractuel par défaut.
- **Zéro** si le salarié est absent sur tout le mois (règle d'Elsa).
- **Prorata** sur les jours du mois en cas d'entrée ou de sortie en cours de
  mois (règle d'Elsa). La base de prorata doit suivre la convention déjà
  retenue ailleurs dans le moteur, à vérifier au moment du plan plutôt que
  décidée ici.

La ligne apparaît dans Saisies > Primes. Elsa la modifie ou la supprime pour un
mois donné : c'est le « pas forcément tous les mois » de la demande. Le mois
suivant, la génération repart du montant contractuel.

En contrepartie, on **retire l'ajout silencieux** de
`calcul_net.py:460-469`. Sans cela, la prime serait comptée deux fois : une
fois par la ligne générée, une fois par le moteur. Cette suppression est sans
risque puisque aucun salarié n'utilise le champ aujourd'hui (§ 3.1).

Prérequis technique : étendre `employee_matches_conditions` au ciblage par
salarié (§ 3.3). Aujourd'hui limité à Cadre / Non-Cadre.

La génération doit rester **idempotente** : relancer « Préparer variables du
mois » ne doit pas empiler les lignes ni écraser une correction manuelle
d'Elsa. Le mécanisme `upsert_monthly_input` existant sert de base, mais la
règle de préservation d'une saisie modifiée à la main est à concevoir
explicitement — c'est le point le plus délicat du bloc.

## 6. Bloc 3 — Assainir la sémantique des quantités

Prérequis du bloc 4 (§ 3.5).

- Rendre explicite ce que porte `payroll_quantity` : un nombre d'unités, ou une
  valeur unitaire. Le champ actuel ne le dit pas et les deux conventions
  coexistent.
- Reprendre les 62 lignes `Paniers Jours non soumis` de Mont Blanc Composite
  pour les aligner sur la convention retenue.
- Normaliser les libellés divergents (`Indemnite` / `Indemnité`,
  `Paniers jours` / `Paniers Jours`), qui sont la cause première de la
  divergence de sémantique.

Contrainte : cette reprise ne doit **déplacer aucun euro** sur les bulletins
existants. Elle change la façon dont la quantité est interprétée, pas le
montant versé. C'est vérifiable par backtest avant/après.

## 7. Bloc 4 — Les plafonds

### 7.1 Réparer la lecture du barème

Corriger `exoneration_repas` pour lire la forme réellement stockée
(`config_data["FRAIS_PRO"][0]["sections"]`), tout en restant tolérant à la
forme historique v1. Un test doit figer la forme réelle de la base, faute de
quoi le prochain changement de forme du scraping recassera silencieusement la
fonction — c'est précisément ce qui s'est produit (§ 3.4).

### 7.2 Choisir le bon plafond repas

`exoneration_repas` retient aujourd'hui `max(vals)`, soit 21,40 € — le plafond
le plus généreux des trois (sur lieu de travail 7,50 €, hors locaux sans
restaurant 10,40 €, hors locaux avec restaurant 21,40 €). Prendre le maximum
par défaut est un défaut de conception : le logiciel choisit silencieusement
l'interprétation la plus favorable.

La situation réelle du salarié n'est portée par aucune donnée aujourd'hui. La
décision retenue est donc en deux temps :

1. **Rendre la situation déclarable** sur le type de prime (lieu de travail /
   hors locaux sans restaurant / hors locaux avec restaurant), et appliquer le
   plafond correspondant lorsqu'elle est renseignée.
2. **Conserver 21,40 € comme repli** tant qu'elle ne l'est pas.

Ce repli n'est pas un choix de confort : durcir le plafond sans la déclaration
réintégrerait à tort les paniers chauffeur à 15 €, qui sont légitimement des
repas hors locaux. Le repli garantit zéro euro déplacé (§ 3.5) tout en
rétablissant un contrôle qui attrape les dépassements grossiers. Le durcissement
viendra de la déclaration, entreprise par entreprise, sous le contrôle d'Elsa.

### 7.3 Cumul annuel transport

La pièce neuve. Pour chaque salarié et chaque année civile, cumuler les
indemnités de transport versées et comparer au plafond applicable :

- `limite_base` seule si pas d'autre dispositif ;
- `limite_cumul_transport_public` si le salarié bénéficie aussi du
  remboursement 50 % d'abonnement (§ 2) ;
- `limite_cumul_carburant_total` et sa sous-limite `part_carburant` selon la
  nature de la prise en charge.

### 7.4 Alerter, ne pas réintégrer automatiquement

Au dépassement, EYWAI **prévient** — il ne modifie pas le bulletin.

Motif : une réintégration automatique modifierait des bulletins qui convergent
aujourd'hui avec ceux du cabinet, sans qu'Elsa l'ait décidé. Le dépassement
constaté (§ 3.6) porte sur la paie produite aujourd'hui par le cabinet, pas sur
une erreur d'EYWAI. Le rôle du logiciel est de le rendre visible ; la décision
de régulariser appartient à Elsa et au cabinet.

L'alerte doit être non bloquante et rattachée au salarié concerné, sur le
modèle des advisories déjà en place.

## 8. Points ouverts

### 8.1 Complétude de la liste Colorplast

Elsa a répondu « la liste est complète pour mbc ». Elle n'a rien dit de
Colorplast, où seuls ESPINOSA et GIRERD sont servis. À reposer.

L'enjeu n'est pas théorique : la saisie manuelle mensuelle est pénible, et
c'est exactement le type de tâche où des oublis s'accumulent. Le croisement du
drapeau titre de séjour avec la nationalité et le NIR avait révélé 8 personnes
non suivies selon le même mécanisme.

### 8.2 Code comptable

Elsa doit répondre. Les 1 000 saisies de la base ont `export_code = None`.
Alimente #26 plutôt que #15.

### 8.3 Régime exact applicable

Le dépassement du § 3.6 suppose que le plafond du forfait mobilités durables
s'applique à une indemnité forfaitaire de trajet prévue par avenant. C'est
l'hypothèse la plus probable, mais elle mérite confirmation par Elsa auprès du
cabinet avant qu'EYWAI n'affiche une alerte de conformité. Le bloc 4 est
implémentable sans cette réponse ; le libellé de l'alerte en dépend.

## 9. Vérification

- Aucun euro déplacé sur les bulletins existants par les blocs 1 à 3. Backtest
  avant/après sur les sociétés déjà convergées (Colorplast 7/7, MBC, Comitech,
  Cartol, Lewis).
- Bloc 4 : backtest complet obligatoire avant merge, puisqu'il rétablit un
  contrôle inactif depuis l'origine. L'attente mesurée est zéro écart sur les
  paniers (§ 3.5), ce qui en fait un bon test de non-régression.
- La suite `tests/unit` doit rester verte. Les 51 échecs d'intégration
  (`schedules`, `saisies_avances`) sont pré-existants et ne jugent pas ce
  changement.
- Répétition sur l'environnement de test avant toute reprise de données du
  bloc 3, après resynchronisation (le test porte des données du 29 juillet).
