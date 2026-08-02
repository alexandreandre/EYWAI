# Case « aménagement » sur le suivi médical

Date : 2026-08-02
Sujet : `docs/afaire.md` #10
Statut : conception validée, implémentation à planifier

## 1. Objectif

Permettre à la RH d'enregistrer qu'une visite médicale a débouché sur un
aménagement de poste, et de voir sur la fiche d'un salarié s'il en a un en
cours.

Demande d'Elsa, formulée le 2026-08-02 :

> Les deux et modifiable uniquement sur la note de visite.
> Et juste visualisable sur fiche salarié — uniquement case ça suffit.

Trois contraintes en découlent, et elles structurent tout le design :

1. La visite porte la donnée. C'est le seul endroit où on la saisit.
2. La fiche salarié l'affiche en lecture seule.
3. Une case, rien d'autre. Ni texte libre, ni date de fin.

## 2. Hors périmètre

- Motif, préconisation, restrictions écrites, date de fin d'aménagement.
  Explicitement écartés par Elsa (« uniquement case ça suffit »).
- Colonne « aménagement » dans les exports CSV et le rapport de conformité.
- Filtre ou KPI « salariés en aménagement » sur la page de pilotage.
- Alerte ou relance liée à un aménagement.
- Lien avec la RQTH, absente de la base (§ 3.3).
- Couverture du suivi médical, aujourd'hui à 23 salariés sur 240 (§ 3.2).
  Sujet distinct, à porter dans `afaire.md`.

## 3. État des lieux

Constats établis par lecture de la base de production le 2026-08-02.

### 3.1 Rien n'existe

`aménagement` n'apparaît nulle part dans le dépôt. La table
`medical_follow_up_obligations` compte 18 colonnes et aucune ne porte l'avis
du médecin du travail :

```
id, company_id, employee_id, visit_type, trigger_type, due_date, priority,
status, justification, planned_date, completed_date, document_storage_path,
rule_source, collective_agreement_idcc, request_motif, request_date,
created_at, updated_at
```

`justification` sert de commentaire libre pour les trois opérations
(planifiée, réalisée, annulation automatique). Il n'est pas réutilisable.

Côté `employees` (53 colonnes), aucun champ de santé ou de restriction.
Le seul voisin thématique est `is_poste_sir`.

### 3.2 Le module est branché mais quasiment vide

| Société | Obligations |
|---|---|
| MAJI | 6 |
| Cartol Industrie | 5 |
| LEWIS | 4 |
| Mont Blanc Composite | 4 |
| Zone 404 Mars | 3 |
| Comitech Composite | 3 |
| Colorplast | 2 |
| **Total** | **27** |

Deux faits comptent pour ce chantier :

- **Les 27 obligations sont au statut `a_faire`. Aucune n'a jamais été
  marquée réalisée.** La case ne se cochant qu'à l'enregistrement d'une
  visite faite, elle sera vide partout au lendemain de la mise en
  production. C'est le comportement attendu, pas un bug, mais Elsa doit en
  être prévenue.
- **23 salariés sont couverts, sur 240 actifs.** Les obligations existantes
  sont uniquement des VIP (22) et des mi-carrière (5). Cet écart de
  couverture est hors périmètre ici, mais il limite mécaniquement la portée
  de la case tant qu'il n'est pas traité.

### 3.3 Aucune donnée existante à reprendre

Pas de reprise, pas de rétro-remplissage, pas de script de migration de
données : il n'y a rien à reprendre. La colonne naît vide et le restera
jusqu'à la première visite saisie.

### 3.4 Une visite réalisée est aujourd'hui définitivement figée

Les deux écrans masquent les actions dès que `status === "realisee"` :

- `frontend/src/pages/rh/MedicalFollowUp.tsx:1353` — le menu disparaît.
- `frontend/src/components/employee-detail/EmployeeDetailMedicalTab.tsx:427`
  — les boutons disparaissent.

Le backend, lui, ne verrouille rien : `update_obligation_completed`
(`infrastructure/queries.py`) est un `UPDATE` simple, rejouable sans
condition sur le statut. Le gel est purement une décision d'affichage.

Conséquence directe sur cette demande : si la case ne peut être cochée qu'à
l'instant précis où l'on marque la visite réalisée, elle devient un champ en
écriture unique. Une erreur de saisie serait irrattrapable, et un
aménagement notifié après coup ne pourrait jamais être enregistré. C'est
pourquoi § 4.3 fait partie du périmètre.

### 3.5 Le moteur d'obligations ne touche jamais aux visites réalisées

`_reconcile_obsolete_active_obligations`
(`infrastructure/obligation_engine.py:266`) ne modifie que les obligations
dont le statut est actif (`a_faire`, `planifiee`), pour les passer à
`annulee`. Les visites réalisées ne sont lues que pour calculer les
échéances suivantes.

Une case portée par une visite réalisée est donc stable : aucun recalcul du
moteur ne peut l'effacer.

## 4. Conception

### 4.1 Stockage

Une colonne booléenne sur `medical_follow_up_obligations` :

```sql
ALTER TABLE medical_follow_up_obligations
  ADD COLUMN IF NOT EXISTS amenagement_poste BOOLEAN NOT NULL DEFAULT FALSE;
```

`NOT NULL DEFAULT FALSE` : les 27 lignes existantes deviennent « pas
d'aménagement », ce qui est exact. Pas de troisième état « inconnu » — la
demande porte sur une case, qui est cochée ou ne l'est pas.

Le nom retient le vocabulaire d'Elsa en le précisant : « aménagement » seul
serait ambigu en base (aménagement du temps de travail, d'horaires).

Cette colonne n'est pas modifiée par le moteur d'obligations. Elle n'est
écrite que par l'opération « marquer réalisée » (§ 4.2).

L'index unique partiel posé par
`20260609140000_medical_follow_up_dedupe_obligations.sql` porte sur
`status IN ('a_faire','planifiee')` : il n'est pas affecté.

### 4.2 Saisie : la note de visite

La case est ajoutée au dialogue « Marquer comme réalisée », sous la date et
le commentaire :

```
Date réelle              [ 02/08/2026 ]
Commentaire (optionnel)  [                    ]
[x] Aménagement de poste
```

Ce dialogue existe en double, dans les deux écrans cités en § 3.4. Les deux
reçoivent la case, avec le même libellé et le même comportement. Ce n'est
pas une entorse à « modifiable uniquement sur la note de visite » : dans les
deux cas c'est bien la note de visite qu'on ouvre. Ce que la contrainte
d'Elsa interdit, c'est de rendre la case cliquable ailleurs — sur la
synthèse de la fiche, dans une liste, en édition directe.

L'onglet « Suivi médical » de la fiche salarié conserve ses boutons
« Planifier » et « Marquer réalisée ». Les retirer serait une régression que
personne n'a demandée.

Chaîne à étendre, de bout en bout :

| Couche | Fichier | Modification |
|---|---|---|
| Migration | `supabase/migrations/<horodatage>_medical_amenagement_poste.sql` | La colonne |
| Requête | `infrastructure/queries.py` | `update_obligation_completed` écrit le champ |
| Repository | `infrastructure/repository.py` | `mark_completed` passe le paramètre |
| Port | `domain/interfaces.py` | Signature de `mark_completed` |
| Commande | `application/commands.py` | Transmet le champ du corps |
| Requête HTTP | `schemas/requests.py` | `MarkCompletedBody.amenagement_poste: bool = False` |
| Réponse HTTP | `schemas/responses.py` | `ObligationListItem.amenagement_poste: bool = False` |
| DTO | `application/dto.py`, `api/router.py` (`_to_list_item`) | Propagation |
| Entité | `domain/entities.py`, `infrastructure/mappers.py` | Propagation |
| Client | `frontend/src/api/medicalFollowUp.ts` | Types `MarkCompletedBody` et `ObligationListItem` |
| Écrans | `MedicalFollowUp.tsx`, `EmployeeDetailMedicalTab.tsx` | La case dans le dialogue |

Le défaut `False` côté schéma de requête préserve la compatibilité : un
appel qui ignore le champ se comporte comme aujourd'hui.

`mark_planified` n'est pas touchée. Un aménagement est le résultat d'une
visite, pas d'une intention de visite.

### 4.3 Corriger une case mal cochée

Les visites réalisées redeviennent modifiables. Sur les deux écrans, une
entrée « Modifier la visite » remplace l'absence d'action pour
`status === "realisee"` :

- `MedicalFollowUp.tsx` — le menu déroulant réapparaît, avec cette seule
  entrée.
- `EmployeeDetailMedicalTab.tsx` — un bouton « Modifier » à la place des
  deux boutons masqués.

Elle rouvre le dialogue de § 4.2, prérempli avec la date, le commentaire et
la case enregistrés, et rejoue `PATCH .../completed`. Les visites `annulee`
restent figées.

Aucune modification backend : l'endpoint accepte déjà d'être rejoué (§ 3.4).
Le seul changement est de cesser de le cacher.

### 4.4 Lecture : la fiche salarié

Un badge en lecture seule dans la rangée de badges de synthèse en tête de
l'onglet « Suivi médical »
(`EmployeeDetailMedicalTab.tsx:297`), aux côtés de « n en retard », « n à
traiter », « n réalisées » :

```
[3 à traiter] [1 réalisée] [Aménagement de poste]
```

Rien n'est affiché en l'absence d'aménagement. Pas de badge « aucun
aménagement » : l'écran ne doit rien affirmer sur la santé d'un salarié dont
on ne sait rien.

**Règle de dérivation.** Le badge s'affiche si la visite réalisée la plus
récente — celle dont `completed_date` est la plus grande, parmi les
obligations de statut `realisee` — a `amenagement_poste = true`.

C'est la dernière visite qui fait foi, pas l'historique cumulé : un
aménagement se lève, et une règle « au moins une visite cochée » afficherait
à vie un aménagement terminé depuis des années.

Deux cas limites, à trancher explicitement :

- `completed_date` ex æquo entre plusieurs visites réalisées le même jour :
  l'aménagement l'emporte. Une visite cochée ce jour-là suffit à afficher le
  badge. Mieux vaut signaler un aménagement levé que d'en masquer un actif.
- Aucune visite réalisée : pas de badge.

La règle est implémentée comme fonction pure dans
`frontend/src/lib/medicalFollowUpLabels.ts`, à côté de `getNextObligation` et
`countMedicalObligations`, sous le nom `hasCurrentWorkplaceAccommodation`.
Elle est ainsi testable sans monter de composant.

Le badge n'est pas ajouté à la page de pilotage RH : Elsa a demandé la fiche
salarié.

### 4.5 Visibilité de la donnée

L'accès aux obligations est déjà restreint : `_company_id_rh`
(`api/router.py:241`) exige que le module soit activé pour l'entreprise et
que l'utilisateur ait un accès RH. La case hérite de cette restriction sans
travail supplémentaire.

Une exception à connaître : `GET /me` (`api/router.py:418`) renvoie à chaque
salarié ses propres obligations. Le champ y sera donc présent. Il s'agit de
sa propre donnée, ce qui est légitime, mais il faut le savoir avant la mise
en production.

Sur le fond, l'arbitrage d'Elsa est le bon : une case sans motif enregistre
une contrainte d'organisation du travail que l'employeur doit connaître et
mettre en œuvre, sans consigner d'élément de diagnostic. Ajouter le champ
texte écarté au § 2 ferait entrer un document RH dans le domaine des données
de santé, avec les obligations qui vont avec.

## 5. Tests

Backend, dans `backend/tests/unit/medical_follow_up/` :

- `test_commands.py` — `mark_completed` transmet `amenagement_poste` au
  repository ; l'omission du champ vaut `False`.
- `test_queries.py` — `update_obligation_completed` inclut la colonne dans
  la charge utile de l'`UPDATE`.
- Un appel rejoué sur une obligation déjà `realisee` met bien la case à jour
  (garantie de § 4.3, aujourd'hui non couverte).

Frontend : aucun test n'existe pour ce module. On en ajoute pour la seule
fonction qui porte une règle métier, `hasCurrentWorkplaceAccommodation` :
aucune visite réalisée, une seule cochée, une seule non cochée, plusieurs
visites dont la plus récente lève l'aménagement, ex æquo de dates.

Ne pas juger le résultat sur la suite d'intégration complète : 51 échecs y
sont pré-existants (`schedules`, `saisies_avances`). La CI ne bloque que sur
`tests/unit`.

## 6. Mise en production

- Horodatage de migration à choisir au moment de l'implémentation et à
  vérifier contre `supabase/migrations/` : d'autres sessions travaillent sur
  la même branche, et la CLI Supabase rejette les collisions. Le dernier
  horodatage connu au 2026-08-02 est `20260722150000`.
- Les migrations s'appliquent automatiquement en production depuis le
  2026-07-31. L'environnement de test n'en applique aucune : la colonne doit
  y être ajoutée à la main avant toute recette.
- Prévenir Elsa que la case restera vide jusqu'à la première visite
  enregistrée (§ 3.2), pour qu'elle ne conclue pas à un défaut.
