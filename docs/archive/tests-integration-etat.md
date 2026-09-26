# Tests d'intégration — état et diagnostic

Date : 2026-07-31

## Résumé

Le job `Backend integration (info)` de la CI échoue depuis longtemps. Il est
**non bloquant par conception** (`continue-on-error: true`), ce qui l'a rendu
invisible au quotidien.

- En CI : **51 échecs / 1309 réussis**
- En local, avec des identifiants factices : **71 échecs / 1289 réussis**

L'écart de vingt tests est le point important : **ils ne passaient en CI que
parce qu'ils atteignaient la vraie base de production**. Le job y est désormais
débranché — il tourne sur la base de test.

Au 2026-08-02, le nombre de réussites a suivi les tests ajoutés depuis
(**51 échecs / 1316 réussis** en CI). C'est le **nombre d'échecs** qui sert de
référence : il n'a pas bougé, et tout écart signale une régression du jour.
C'est ainsi qu'un passage à 52 a révélé une signature de repository non
répercutée dans `tests/integration/medical_follow_up/`, que `tests/unit` seul
ne voyait pas. Ne pas lire la consigne « 51 échecs pré-existants » comme une
autorisation d'ignorer cette suite : elle dit de ne pas *juger* un changement
dessus, pas de s'en passer.

## Trois familles de causes

Aucune n'est un défaut de l'application : ce sont des tests devenus faux à
mesure que le code a évolué.

### 1. `401 Unauthorized` — utilisateur non injecté (~14 tests)

`tests/integration/schedules/test_api.py`, `test_wiring.py`

Ces tests appellent des routes protégées sans surcharger `get_current_user`.
Le fichier l'assume d'ailleurs dans un commentaire : « peuvent ne pas exiger
d'auth selon le projet ». Les routes l'exigent désormais.

**Correctif** : ajouter la surcharge, sur le modèle de
`TestGetEmployeeCalendarData::test_get_calendar_data_returns_200_with_mock`,
qui la fait correctement dans le même fichier.

### 2. `500` — appels réseau non mockés (~24 tests)

`tests/integration/saisies_avances/`, `tests/integration/legacy/`

Ces tests traversent jusqu'à une vraie connexion Supabase. Ils réussissaient en
CI contre la production, échouent dès que l'hôte est factice.

**Correctif** : mocker le dépôt ou la requête concernée, comme le font déjà les
tests voisins qui passent.

### 3. `403 Forbidden` — permissions durcies (~16 tests)

`tests/integration/participation/`, `tests/integration/rates/`,
`tests/integration/expenses/`

L'utilisateur de test ne porte pas les permissions désormais exigées.
Vraisemblablement lié à la migration `user_permission_scopes` (périmètres
entreprise / équipes et exceptions individuelles).

**Correctif** : doter l'utilisateur de test des permissions attendues.

## Ordre conseillé

La famille 1 est la plus simple et la plus mécanique — commencer par là pour
retrouver un décompte lisible. La famille 3 demande de comprendre le modèle de
permissions en vigueur. La famille 2 est la plus longue mais la plus utile :
c'est elle qui garantit qu'aucun test ne dépend d'une base réelle.

Une fois le job vert, passer `continue-on-error` à `false` pour qu'il redevienne
bloquant — sans quoi il se dégradera de nouveau sans que personne ne le voie.
