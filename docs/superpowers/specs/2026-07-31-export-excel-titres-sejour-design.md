# Export Excel des titres de séjour

Date : 2026-07-31
Sujet : `docs/afaire.md` #7
Statut : conception validée, implémentation à planifier

## 1. Objectif

Ajouter un bouton d'export Excel sur la page RH « Titres de séjour »
(`/residence-permits`), produisant une fiche de suivi exploitable telle quelle :
relancer un salarié dont le titre arrive à échéance, et transmettre à Elsa la
liste des situations à régulariser sans avoir à recroiser une seconde
extraction.

Le fichier produit reflète exactement ce que l'utilisateur voit à l'écran,
filtres et recherche compris.

## 2. Hors périmètre

- Envoi automatique périodique du fichier. Le design le rend possible sans
  réécriture (§ 4.1), mais ne l'implémente pas.
- Saisie du type de titre, aujourd'hui vide pour tous les salariés (§ 3.3).
- Correction du détournement du champ `residence_permit_type` par l'import
  d'export paie (§ 3.4).
- Modification du seuil d'anticipation, des règles de statut, ou de la liste
  affichée à l'écran.
- Export multi-sociétés. L'export porte sur l'entreprise active, comme la page.

## 3. État des lieux

Constats établis par lecture de la base de production le 2026-07-31.

### 3.1 Population concernée

43 salariés sont soumis au titre de séjour avec un statut d'emploi `actif` ou
`en_sortie`, répartis sur six sociétés :

| Société | Salariés soumis |
|---|---|
| Mont Blanc Composite | 34 |
| Cartol Industrie | 3 |
| LEWIS | 2 |
| Zone 404 Mars | 2 |
| Comitech Composite | 1 |
| MAJI | 1 |

Le volume est donc faible et le restera : 34 lignes au maximum pour une
entreprise. Aucune contrainte de pagination ou de streaming ne s'applique.

### 3.2 Les colonnes enrichies sont toutes exploitables

Taux de remplissage sur ces 43 salariés :

| Champ | Rempli |
|---|---|
| `matricule` | 43/43 |
| `job_title` | 43/43 |
| `hire_date` | 43/43 |
| `nationalite` | 43/43 |
| `residence_permit_number` | 43/43 |
| `residence_permit_expiry_date` | 41/43 |
| `residence_permit_type` | 0/43 |
| `time_tracking_id` | 0/43 |

Deux points d'attention :

- la colonne s'appelle **`nationalite`**, en français, et non `nationality` ;
- `time_tracking_id` est vide partout : le matricule vient de `matricule` seul,
  sans repli.

Les deux dates d'expiration manquantes sont ASKARI (Mont Blanc Composite) et
BLA (MAJI), déjà identifiées lors du traitement de `#6`.

### 3.3 Le type de titre n'est renseigné pour personne

`residence_permit_type` vaut `NULL` pour les 43 salariés. La colonne « Type » du
tableau affiche donc « — » sur toutes les lignes depuis la mise en service.

Ce n'est pas un défaut d'interface : le champ est saisissable, à la création
(`CreateEmployeeForm.tsx:1111`) comme sur la fiche
(`EmployeeProfileEditForm.tsx:761`). Il n'a simplement jamais été renseigné, et
aucun import ne l'alimente.

**Décision** : la colonne est conservée dans l'export, vide. Elle rend le trou
visible pour Elsa, qui peut le combler par la saisie existante, et rien ne sera
à modifier le jour où les types seront renseignés.

### 3.4 Défaut latent dans l'import d'export paie

`payroll_export_parser.py:331` écrit une **date** dans le champ **type** :

```python
if rp_from:
    patch["residence_permit_type"] = f"Valide depuis {rp_from}"
```

Le champ « type de titre » est détourné pour stocker une date de début de
validité, faute d'une colonne dédiée. Si un import arrivait avec la colonne
`residence_permit_from` mappée, la colonne « Type » afficherait
« Valide depuis 2024-03-01 » au lieu d'un type de titre — et l'export
propagerait cette valeur.

Le cas ne s'est jamais produit (0/43). Consigné ici, hors périmètre de `#7`.

### 3.5 Situations à régulariser

Au 2026-07-31, sept salariés de Mont Blanc Composite ont un titre **expiré** :

| Salarié | Expiré depuis | Nationalité |
|---|---|---|
| LANKOKO MVUKI Dieu Merci | 184 jours | Congolaise |
| AVAHOUIN William | 170 jours | Béninoise |
| NUHU ALI Abdala | 156 jours | Ghanéenne |
| BEHIRY Mohamed | 149 jours | Égyptienne |
| SHAHABI Zabi | 121 jours | Afghane |
| CHAABANE Sihem | 110 jours | Tunisienne |
| ARAB Sadiqullah | 102 jours | Afghane |

Ces situations exposent l'employeur pénalement. Elles relèvent d'une remontée à
Elsa, indépendante de ce chantier — l'export en est le support naturel.

Deux titres chez Cartol Industrie expirent dans les trois mois. Le seuil
d'anticipation de l'application étant de 30 jours
(`ANTICIPATION_THRESHOLD_DAYS`, `domain/rules.py:18`), ils ne sont pas
nécessairement signalés « à renouveler » à l'écran aujourd'hui.

### 3.6 Le statut n'est pas une colonne

`residence_permit_status` est **calculé** après lecture, par
`calculate_residence_permit_status` (`domain/rules.py`), à partir de la date
d'expiration et du statut d'emploi. Il n'existe pas en base.

Conséquence directe sur le design : aucun filtrage par statut n'est possible en
SQL. C'est ce constat qui écarte l'idée d'un endpoint d'export qui refiltrerait
lui-même (§ 4.2).

`residence_permit_days_remaining` est **négatif** pour un titre expiré : −184
pour LANKOKO MVUKI. L'export restitue cette valeur telle quelle.

## 4. Conception

### 4.1 Le fichier est fabriqué par le serveur

La génération est faite côté backend, et non dans le navigateur.

Le critère retenu : *ce fichier devra-t-il un jour être produit sans humain
devant l'écran ?* Ici la réponse est déjà écrite dans le dépôt :

- `notifications/application/hr_deadline_reminders.py:34` lit **déjà**
  `is_subject_to_residence_permit` et `residence_permit_expiry_date` : un
  traitement planifié surveille ces échéances, sans écran ;
- `exports/application/notifications.py:139` (`notify_export_recipients`) sait
  **déjà** attacher des octets `.xlsx` à un e-mail.

Un générateur vivant dans `ResidencePermits.tsx` serait injoignable depuis ce
traitement planifié, et devrait être réécrit le jour où l'on voudra envoyer la
liste à Elsa tous les mois. La génération serveur est par ailleurs testable en
CI sur les octets produits, ce que la génération navigateur n'est pas sans
simuler un navigateur.

Le dépôt confirme cette lecture : les exports serveur sont ceux dont le contenu
est calculé (écritures comptables, charges sociales, virements) ; les exports
navigateur sont ceux d'une vue déjà affichée (analytics équipe, gestion,
dashboard groupe). Un export de liste RH filtrée relève de la première famille
dès lors qu'un automatisme le convoitera.

### 4.2 Le navigateur désigne les lignes, le serveur ne filtre pas

Le filtre par statut et la recherche par nom sont appliqués en mémoire côté
front (`ResidencePermits.tsx:122-139`). Faire refiltrer le serveur créerait deux
implémentations de la même règle — d'autant plus fragile que le statut est
calculé et non stocké (§ 3.6).

**Le navigateur envoie donc la liste des identifiants à exporter**, pas les
critères de filtrage. Le serveur ne filtre rien : il fabrique le fichier pour
les salariés qu'on lui désigne.

Conséquences :

- la règle de filtrage n'existe qu'à un seul endroit, l'écran ;
- le fichier correspond à l'écran **par construction**, y compris l'ordre de tri
  (§ 4.5), et non par une cohérence à maintenir entre deux implémentations ;
- l'envoi automatique futur n'est pas gêné : il choisit ses propres lignes
  — « tous ceux qui expirent sous 30 jours » — et appelle la même fonction de
  fabrication. C'est de toute façon un critère différent de celui de l'écran ;
- la page n'a **aucun** champ supplémentaire à charger. Les données enrichies
  (matricule, poste, date d'entrée, nationalité) ne transitent que dans le
  fichier, et jamais dans le payload de la page. `ResidencePermitListItem` reste
  inchangé.

### 4.3 Découpage

Une fonction fabrique le fichier, deux appelants possibles.

```
api/router.py
  POST /api/residence-permits/export
        │  vérifie l'accès RH sur l'entreprise active
        ▼
application/exports.py
  export_residence_permits(company_id, company_name, employee_ids)
        │  lit les lignes (bornées à l'entreprise), calcule les statuts,
        │  restaure l'ordre demandé
        ▼
infrastructure/export_xlsx.py
  build_residence_permits_xlsx(rows, company_name) -> bytes
        │  mise en forme des valeurs, appel de generate_xlsx
        ▼
shared/utils/export.py::generate_xlsx   (existant, inchangé)
```

`build_residence_permits_xlsx` ne connaît ni HTTP, ni entreprise active, ni
provenance des lignes. C'est le point de réutilisation pour un futur envoi
planifié.

`application/commands.py` du module porte aujourd'hui un commentaire
« réservé pour évolution ». L'export étant une lecture, il va dans un
`application/exports.py` dédié plutôt que dans `queries.py`, qui reste centré
sur la liste.

### 4.4 Contrat de l'endpoint

`POST /api/residence-permits/export`

```json
{ "employee_ids": ["uuid", "uuid", "..."] }
```

Réponse `200` : octets XLSX,
`media_type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`,
`Content-Disposition: attachment; filename="..."`.

**POST et non GET** : la liste d'identifiants est de longueur variable. En GET
elle passerait dans l'URL, dont la longueur est bornée par les navigateurs et
les proxys. 34 identifiants tiennent aujourd'hui, mais la limite deviendrait un
défaut latent si la population grandissait.

Contrôle d'accès : `_require_rh_company_context(current_user)`, déjà en place
sur la route liste, inchangé.

Codes d'erreur :

| Situation | Réponse |
|---|---|
| Aucune entreprise active | `400` (existant) |
| Pas d'accès RH sur l'entreprise | `403` (existant) |
| `employee_ids` vide | `400` « Aucun salarié à exporter » |
| Plus de 1000 identifiants | `400` (garde-fou) |
| Aucun identifiant ne correspond | `400` « Aucun salarié à exporter » |

### 4.5 Sécurité : le périmètre est imposé par le serveur

Le serveur ne fait jamais confiance aux identifiants reçus. La requête applique,
en plus du `IN (employee_ids)`, **exactement les mêmes bornes que la route
liste** :

```
company_id = <entreprise active>
is_subject_to_residence_permit = true
employment_status IN ('actif', 'en_sortie')
```

Sans le filtre sur `company_id`, un utilisateur pourrait exporter des salariés
d'une autre société en modifiant la requête. C'est la garantie centrale de cet
endpoint.

Les identifiants ne correspondant à rien sont **ignorés silencieusement**, sans
erreur : ce cas se produit légitimement lorsqu'un salarié change de statut entre
l'affichage de la page et le clic sur le bouton. Seul un résultat entièrement
vide déclenche une erreur.

L'ordre des lignes du fichier reprend l'ordre des identifiants reçus. La base ne
garantit aucun ordre sur un `IN`, l'ordre est donc restauré en mémoire par
position dans la liste demandée. C'est ce qui fait correspondre le fichier au
tri par urgence affiché à l'écran.

### 4.6 Contenu du fichier

Une feuille, treize colonnes, une ligne d'en-tête mise en forme par
`generate_xlsx` (fond bleu, texte blanc, largeurs ajustées).

| # | Colonne | Source | Vide si |
|---|---|---|---|
| 1 | Nom | `last_name` | — |
| 2 | Prénom | `first_name` | — |
| 3 | Matricule | `matricule` | — |
| 4 | Société | entreprise active | — |
| 5 | Poste | `job_title` | non renseigné |
| 6 | Date d'entrée | `hire_date` | non renseignée |
| 7 | Nationalité | `nationalite` | non renseignée |
| 8 | Statut d'emploi | `employment_status` | — |
| 9 | Statut du titre | calculé | — |
| 10 | Type de titre | `residence_permit_type` | **toujours, aujourd'hui** |
| 11 | Numéro de titre | `residence_permit_number` | non renseigné |
| 12 | Date d'expiration | `residence_permit_expiry_date` | non renseignée |
| 13 | Jours restants | calculé | date d'expiration absente |

Mise en forme des valeurs :

- **dates** au format `JJ/MM/AAAA`, cellule vide si absente ;
- **jours restants** en nombre entier, négatif pour un titre expiré (§ 3.6) ;
- **statut du titre** en toutes lettres : `expired` → « Expiré », `to_renew` →
  « À renouveler », `to_complete` → « À compléter », `valid` → « Valide », et
  « À compléter » lorsque le statut est absent ;
- **statut d'emploi** : `actif` → « Actif », `en_sortie` → « En sortie » ;
- toute valeur absente devient une cellule vide, jamais « — » ni « None ».

Nom du fichier :
`titres-de-sejour_<societe>_<AAAA-MM-JJ>.xlsx`, le nom de société étant réduit
aux caractères sûrs (minuscules, tirets).

### 4.7 Interface

Un bouton « Exporter en Excel », icône `Download`, placé dans l'en-tête de carte
à droite du filtre par statut, sur la ligne existante des contrôles.

- désactivé tant que la liste filtrée est vide, ou pendant le chargement ;
- état d'attente pendant la requête, le bouton restant désactivé ;
- en cas d'échec, un toast destructif reprenant le message du serveur, selon le
  motif `loadErrorMessage` déjà présent dans la page ;
- le téléchargement passe par `downloadBlob` (`lib/downloadBlob.ts`), le nom de
  fichier étant lu dans l'en-tête `Content-Disposition` avec repli.

Aucune modification de la requête de liste, du tri, des filtres ni du tableau.

## 5. Tests

### Backend

Sur `build_residence_permits_xlsx`, à partir de lignes construites en mémoire,
en relisant le classeur produit :

- les treize en-têtes sont présents, dans l'ordre ;
- une ligne complète est restituée avec les bonnes valeurs ;
- les dates sortent en `JJ/MM/AAAA` ;
- les statuts sortent en toutes lettres, y compris « À compléter » quand le
  statut est absent ;
- un `residence_permit_type` à `NULL` donne une cellule vide, pas « None » ;
- un titre expiré donne un nombre de jours négatif.

Sur `export_residence_permits`, avec un lecteur simulé :

- **un identifiant appartenant à une autre société est exclu du fichier** ;
- un identifiant inconnu est ignoré sans erreur ;
- l'ordre des lignes du fichier suit l'ordre des identifiants demandés, et non
  celui renvoyé par la base ;
- une liste vide, ou dont aucun identifiant ne correspond, lève une erreur.

Sur la route, via le client de test FastAPI :

- absence d'accès RH sur l'entreprise active → `403` ;
- au-delà de 1000 identifiants → `400` ;
- cas nominal → `200`, bon `media_type`, `Content-Disposition` présent.

### Frontend

- le bouton est désactivé quand la liste filtrée est vide ;
- un clic envoie exactement les identifiants des lignes filtrées affichées, dans
  l'ordre d'affichage.

## 6. Ce que ce design ne résout pas

- Le type de titre reste vide tant qu'il n'est pas saisi (§ 3.3). L'export rend
  le trou visible, il ne le comble pas.
- Les sept titres expirés (§ 3.5) appellent une action métier, pas un
  développement.
- L'export reste mono-société. Une vue consolidée sur les sept entreprises
  demanderait un chemin de lecture multi-entreprises qui n'existe pas
  aujourd'hui sur cette page.
- Le détournement du champ type par l'import d'export paie (§ 3.4) subsiste.
