# Arrêt sans subrogation : déduire ou non les IJSS du maintien — conception

Date : 23/10/2026. Demande d'Alexandre : « est-ce qu'on peut laisser comme ça et juste mettre une option pour pouvoir régler ça elle-même ? Il faut que les utilisateurs puissent bien régler ça facilement et que ça marche proprement. » Option A, avec les précisions de ce document, validée le même jour (« Oui »).

## 1. Le problème

Pendant un arrêt indemnisé par la CPAM, deux cas existent.
- **Avec subrogation**, l'employeur reçoit les IJSS et verse le salaire maintenu. Le bulletin les déduit. Ce cas est juste aujourd'hui.
- **Sans subrogation**, la CPAM verse les IJSS au salarié. L'employeur ne doit que le complément « sous déduction des IJSS » (Code du travail, D1226-5).

Aujourd'hui, sans subrogation, `maintien_salaire_service` verse le salaire garanti en entier : `maintien_verse = maintien_cible` (MSS:942-946). Le salarié touche donc le garanti, plus les IJSS de la CPAM. C'est aussi vrai en jours ouvrés quand la société est réglée « Jamais » (MSS:1566).

Colorplast et Comitech sont les seules sociétés concernées sur la base de test. Toutes deux sont en « Jamais » et en jours ouvrés, avec 3 arrêts non subrogés chacune (relevé du 23/10). Leurs bulletins ont été calés sur Quadra. La question de leur pratique n'a jamais été posée à Gaëlle.

## 2. Ce qu'on construit

Un réglage par société, dans la carte « Maintien de salaire ». Il porte sur tous les arrêts non subrogés qui ouvrent un maintien employeur : maladie, AT/MP, et congés parentaux quand la société les maintient.

| Choix affiché | Valeur | Effet sans subrogation |
|---|---|---|
| « Verser le salaire garanti en entier » | `false` | le calcul d'aujourd'hui, inchangé |
| « Verser le complément, IJSS déduites (règle légale) » | `true` | `maintien_verse = max(0, maintien_cible − IJSS retenues)` |

- **Texte d'aide sous le choix** : « Sans subrogation, la CPAM paie les IJSS directement au salarié. Martine peut les déduire du maintien, comme le prévoit la loi, ou verser le salaire garanti en entier. »
- **IJSS retenues** : le montant validé dans « Suivi IJSS / CPAM » et appliqué au bulletin (`ijss_brut_override`, MSS:1599-1608). À défaut, l'estimation de Martine (`ijss_theorique`).
- **Avec subrogation**, rien ne change.

### Ce qui ne change pas
- **Colorplast, Comitech et toute société qui a déjà une ligne de réglages de maintien** : la migration pose `false`, le calcul d'aujourd'hui.
- **Une société sans ligne de réglages, ou une nouvelle société** : la règle légale (`true`). L'écran (GET) et le moteur lisent la même valeur par défaut. Aucun bulletin ne bouge pour autant : sans ligne, le mode de subrogation par défaut (« Automatique si maintien applicable », MSS:1210) subroge tout arrêt qui ouvre un maintien. Au 23/10, les seuls arrêts non subrogés sont ceux de Colorplast et de Comitech. Le filet le vérifie.
- **Un bulletin sans arrêt non subrogé** : il est identique au centime et clé pour clé, et ne passe pas « À recalculer ». Le filet doit montrer 0 écart.

## 3. Ce qui se voit

- **Bulletin, écran** : la ligne « Maintien de salaire employeur » reçoit une explication dans « D'où viennent ces lignes », par exemple « Complément employeur : salaire garanti 1 234,56 € moins 345,67 € d'IJSS versées par la CPAM au salarié (estimées par Martine) » ou « (montant validé dans le suivi IJSS) ». L'alerte existante « IJSS versées directement au salarié » (MSS:1750) dit la même chose quand la déduction joue.
- **PDF** : une mention sous la ligne de maintien, avec le même mécanisme que les mentions de correction du théorème, sans changer le libellé de la ligne : « dont IJSS déduites : 345,67 € (estimées) ».
- **« Suivi IJSS / CPAM »** : un bulletin dont le maintien a déduit des IJSS a sa ligne attendue, même sans subrogation. Aujourd'hui ces bulletins sont sautés (`ijss_tracking/application/service.py:246`). On peut y saisir le vrai montant, puis « Appliquer au bulletin », qui recalcule avec ce montant.
- **Changer le réglage** :
  - les bulletins du mois qui ont un arrêt non subrogé passent « À recalculer » avec le motif existant « Un réglage de paie de la société a changé » ;
  - les autres bulletins ne bougent pas ;
  - la carte confirme l'enregistrement, comme ses autres réglages.

## 4. Où vit le code

- **Migration** : colonne `company_maintenance_settings.deduire_ijss_sans_subrogation boolean not null default true`, puis `update … set … = false` sur toutes les lignes existantes, dans le même fichier. Application à la main sur la base de test (option `migration` du workflow), comme les migrations précédentes.
- **Schémas et API** : `maintenance_settings/schemas/responses.py` et `requests.py`, GET/PUT `/api/maintenance-settings/`.
- **Moteur** (MSS, branche sans subrogation, MSS:942-946 et le chemin maternité MSS:840-870) :
  - la déduction, plancher à 0 ;
  - le montant d'IJSS retenu et sa source (`estimees` ou `validees`), posés sur le résultat du maintien pour l'écran et le PDF ;
  - lecture `settings.get("deduire_ijss_sans_subrogation", True)` : même défaut que la réponse GET sans ligne.
- **Empreinte** (`empreinte_entrees_service._reglages_societe_du_mois`) : la clé n'entre dans la partie « maintien » que si la ligne de réglages la porte à `true`. Sinon, l'ajout de la colonne, posée à `false` partout, périmerait tous les bulletins avec un arrêt. Passer de `false` à `true` fait donc passer « À recalculer » les bulletins du mois qui ont un arrêt ; repasser à `false` aussi.
- **Écran** : `MaintenanceSettingsCard.tsx`, sous le choix « Mode de subrogation » : deux boutons radio et le texte d'aide.
- **Suivi IJSS** : la synchronisation garde un bulletin non subrogé dont le maintien a déduit des IJSS.
- **Explications et PDF** : `explications_lignes.py` et le mécanisme de mention des lignes (`corrections_du_bulletin` / `bulletin_view.py`).

## 5. Tests et preuves

- **Moteur** :
  - réglage `false` : versé = garanti, comme `test_sans_subrogation_pas_deduction_ijss`, qui doit rester vert sans modification ;
  - réglage `true` : versé = garanti − IJSS estimées, puis garanti − IJSS validées après application du suivi ;
  - plancher à 0 si les IJSS dépassent le garanti ;
  - jours ouvrés + « Jamais » (cas Colorplast) avec `true` ;
  - congés parentaux maintenus ;
  - avec subrogation : rien ne change.
- **Empreinte** : réglage absent ou `false` → empreinte inchangée. Passage à `true` (ou retour à `false`) → « À recalculer » seulement pour les bulletins avec un arrêt.
- **Réglages** : GET sans ligne → `true` ; GET après migration sur une ligne existante → `false` ; PUT qui enregistre le choix.
- **Écran** : les deux choix, l'enregistrement, le texte d'aide (vitest).
- **Suivi IJSS** : la ligne attendue d'un bulletin non subrogé avec déduction.
- **Filet au centime** (`~/dev/eywai-filet/lancer.sh`, `comparer5.py`), base f92ca62e/d1fb04d1 contre la branche : 0 bulletin avec écart, 0 cumul avec écart. Sans changement d'option, rien ne doit bouger.
- **Jeu de bout en bout chez MAJI**, sur un personnage :
  - un arrêt non subrogé, avec le réglage à `true` puis à `false` ;
  - lire le bulletin, le PDF, « Suivi IJSS / CPAM » et « Appliquer au bulletin » ;
  - puis ranger MAJI.

## 6. Hors champ

- **Changer le réglage de Colorplast ou de Comitech.** C'est à Gaëlle, après sa réponse à la question : « Quand un salarié n'est pas subrogé, tu déduis les IJSS du maintien dans Quadra ? ».
- **Régulariser les mois passés.**
- **Un choix par arrêt.** La carte « Corriger une ligne » couvre un cas isolé.

## 7. Règles

- Moteur en Opus, tests d'abord, filet au centime avant tout déploiement. Déploiement seulement sur accord d'Alexandre.
- Ne jamais régénérer un vrai bulletin.
- Aucun nom de salarié dans le code ni les commits.
- Python 3.11 en CI.
- Textes en français, simples ; le produit s'appelle « Martine ».
