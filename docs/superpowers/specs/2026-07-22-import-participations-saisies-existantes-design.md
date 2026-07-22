# Import des participations depuis des saisies existantes

**Date :** 2026-07-22
**Statut :** validé (design)
**Module :** `backend/app/modules/participation`

## Problème

Les montants de participation « exercice 2025 » apparaissent correctement sur les
bulletins de mai 2026 de 5 sociétés (MBC, Cartol, Lewis, Comitech, Colorplast),
mais uniquement sous forme de **saisies mensuelles** (`monthly_inputs`) libellées
« Participation 2025 … » / « Avance participation 2025 … ». Ils ont été créés lors
des backtests, **hors du module participation** :

- `participation_campaigns` : 1 seule campagne (Comitech), en `draft`, jamais
  envoyée, sans bulletin.
- `participation_bulletins` : table **vide**.
- Les 291 saisies participation ont toutes `participation_campaign_id = NULL`.

Le module participation dispose d'un cycle de vie complet
(`create_campaign` → `publish` → `respond` → `generate_payroll_lines`) et d'une UI
RH (`ParticipationCampaignPanel`). **Mais ce flux *produit* les saisies ; il
n'existe aucun chemin pour enregistrer rétroactivement une campagne à partir de
saisies déjà présentes.** C'est la capacité manquante.

## Objectif

1. Ajouter une capacité **réutilisable** : importer les participations d'une
   société/année depuis les saisies existantes, en reconstruisant une campagne
   clôturée + les bulletins d'option, et en rattachant les saisies.
2. Exposer cette capacité par un endpoint API et un bouton dans l'UI campagnes.
3. L'exécuter pour les 5 sociétés (exercice 2025, paie 05/2026).

## Décisions de cadrage (validées)

- **Mécanisme :** service backend réutilisable + endpoint + bouton UI.
- **État des campagnes reconstruites :** `closed`. Choix salarié **déduit** des
  saisies (numéraire seul → `full_cash`, PEE seul → `full_pee`, les deux →
  `partial_cash`). **Aucune** notification/envoi salarié, **aucun** PDF généré.
  La participation étant déjà versée, on ne re-déclenche pas le workflow de choix.
- **Périmètre :** les 5 sociétés ayant des saisies participation 2025.

## Données constatées (base réelle, 2026-07-22)

- **188 bénéficiaires** : MBC 72, Cartol 65, Lewis 28, Comitech 18, Colorplast 5.
- Profils : **177 full_cash**, **9 partial_cash** (numéraire + PEE), **2 full_pee**.
- Aucune avance orpheline (toute avance a une ligne numéraire associée).
- 2 styles de libellés coexistent :
  - MBC/Colorplast/Comitech : `Participation 2025 — numéraire` + ligne d'avance
    séparée `Avance participation 2025 (déjà versée)` (négative).
  - Cartol/Lewis : `Participation 2025` simple.
- 11 lignes PEE (`Participation 2025 PEE` / `— PEE`) ; quelques `Acompte …`.
- 1 ligne `Remboursement note de frais (participation)` → **exclue** (pas un versement).
- Flags saisie numéraire : `is_socially_taxed=False, is_taxable=True` (régime CSG seule).

## Architecture

Découpage en unités isolées :

### 1. Reconstruction — fonction pure (domaine)

Emplacement : `participation/domain/` (nouveau module, ex. `import_reconstruction.py`).

Entrée : liste des `monthly_inputs` participation d'une société/année.
Sortie : liste d'objets `ReconstructedBulletin` (une par salarié bénéficiaire).

Classification de chaque ligne par `name` (insensible à la casse) :

| Type | Détection | Rôle |
|---|---|---|
| numéraire | contient `participation`/`intéressement`, montant **> 0**, hors `pee`/`épargne`/`avance`/`acompte`/`frais`/`remboursement` | brut versé `N` |
| PEE | contient `pee`/`épargne`, montant > 0 | net placé `P` |
| avance | contient `avance`/`acompte`, montant **< 0** | acompte versé `A = |montant|` |
| exclu | `note de frais`/`remboursement` | ignoré |

Agrégation par salarié puis (CSG 9,7 % = 6,8 % déd. + 2,9 % non déd.) :

```
pee_gross   = round(P / 0,903, 2)          # regonfle le net PEE en brut
gross       = N + pee_gross
csg_nd      = round(gross × 0,029, 2)
csg_d       = round(gross × 0,068, 2)
net_final   = round(gross − csg_nd − csg_d − A, 2)
choice      = full_cash (P == 0) | full_pee (N == 0) | partial_cash (sinon)
cash_amount = round(N × 0,903 − A, 2)      # 0 si full_pee
pee_amount  = P
advance_amount = A
advance_label  = libellé de la ligne d'avance (ou "")
```

Invariant vérifié : `cash_amount + pee_amount == net_final` (aux arrondis cents près).
Se réconcilie ligne à ligne avec le bulletin de mai (numéraire brut → net ×0,903 ;
PEE ; avance). L'arrondi sur `pee_gross` est cosmétique : le bulletin importé est un
enregistrement d'affichage/traçabilité et **ne régénère aucune paie**.

Un salarié sans aucune ligne numéraire/PEE positive n'est **pas** un bénéficiaire
(ignoré). `dispositif_type = "participation"` (pas d'intéressement dans ces données).

### 2. Service d'import (application)

Emplacement : `participation/application/campaign_import_service.py`.

`import_campaign_from_inputs(company_id, year, payroll_year, payroll_month, *, dry_run=False, force=False) -> ImportResult`

1. Charge les saisies participation de la société pour `(payroll_year, payroll_month)`
   (les saisies sont datées sur la paie, ex. 05/2026 ; `year` = exercice, ex. 2025).
2. Reconstruit via §1.
3. **Idempotence** : s'il existe déjà une campagne `(company_id, year)` **avec des
   bulletins** → skip et retourne l'existant, sauf `force=True`. Si la campagne
   existante est un brouillon **sans bulletin** (cas Comitech) → elle est
   supprimée puis remplacée. `force=True` supprime la (les) campagne(s) issue(s)
   de cet import pour `(company_id, year)` — identifiée(s) par
   `status="closed"` **et** `simulation_id IS NULL` (heuristique retenue faute de
   colonne `source`) — délie ses saisies, puis rejoue. Une campagne « normale »
   (issue d'une simulation) n'est jamais supprimée.
4. Si `dry_run` : retourne le résumé (compteurs) **sans écrire**.
5. Sinon : crée la campagne (`status="closed"`, `exercise_label="PARTICIPATION {year}"`,
   `simulation_id=None`, `payroll_year`, `payroll_month`), insère les
   `participation_campaign_advances` et les `participation_bulletins`
   (`status="responded"`, `choice_type`, `cash_amount`, `pee_amount`, `csg_*`,
   `advance_*`, `net_amount`, `responded_at=now`).
6. Rattache les saisies : sur toutes les `monthly_inputs` d'un bénéficiaire
   entrant dans la reconstruction (numéraire, PEE, avance), met à jour
   `participation_campaign_id` et `participation_bulletin_id` (id du bulletin de
   ce salarié). La ligne `note de frais` exclue n'est pas rattachée.

`ImportResult` : `{campaign_id, bulletins, full_cash, partial_cash, full_pee,
linked_inputs, skipped, dry_run}`.

**Réversibilité** : fonction `delete_imported_campaign(campaign_id, company_id)` —
supprime la campagne (cascade bulletins + advances) et remet à `NULL` les liens
`participation_campaign_id`/`participation_bulletin_id` sur les saisies.

Aucun appel à `publish_campaign`, aux notifications, ni à `document_service`.

### 3. Endpoint API

`POST /api/participation/campaigns/import-from-inputs`
- Body : `{year: int, payroll_year: int, payroll_month: int, dry_run?: bool, force?: bool}`.
- `company_id` depuis le contexte utilisateur ; permission
  `participation.allocation.manage` ; garde RH/admin (patterns existants du router).
- Réponse : `ImportResult` sérialisé.

Schémas : ajout dans `campaign_requests.py` (`ImportFromInputsRequest`) et
`campaign_responses.py` (`ImportResultResponse`).

### 4. Frontend

`ParticipationCampaignPanel.tsx` : bouton **« Importer depuis les saisies
existantes »**.
- Ouvre une petite modale : saisie exercice (année) + mois/année de paie
  (pré-remplis : 2025 / 05-2026).
- Appelle d'abord l'endpoint en `dry_run=true` → affiche l'aperçu (nb bulletins,
  répartition des choix, saisies à rattacher) → bouton **Confirmer** rejoue en
  `dry_run=false`, puis rafraîchit la liste des campagnes.
- Client dans `api/participation.ts` (`importParticipationFromInputs`).

### 5. Exécution 2025 (opération de données)

Après implémentation + tests, lancer l'import pour les 5 sociétés
(`year=2025`, `payroll_year=2026`, `payroll_month=5`) — via un script one-shot
appelant le service, ou via l'endpoint par société.

Vérification post-exécution :
- 5 campagnes `closed` (exercice 2025).
- ~188 bulletins `responded` (177 full_cash / 9 partial_cash / 2 full_pee).
- 291 saisies participation avec `participation_campaign_id` renseigné.
- Les montants sur les bulletins de mai **inchangés** (l'import ne touche pas aux
  `amount`/flags des saisies, seulement aux colonnes de liaison).

## Tests

- **TDD** sur la fonction pure de reconstruction (§1) :
  - full_cash (numéraire seul), full_cash + avance ;
  - partial_cash (numéraire + PEE) ;
  - full_pee (PEE seul) ;
  - exclusion de la ligne `note de frais` ;
  - label simple `Participation 2025` vs `— numéraire` traités identiquement ;
  - invariant `cash + pee == net_final` ; arrondis cents.
- **Intégration légère** du service en `dry_run` (compteurs attendus sur un jeu
  simulé). Vérification manuelle des compteurs en base après exécution 2025.
- Non-régression : la suite `pytest` du module participation reste verte.

## Hors périmètre (YAGNI)

- Pas de colonne `source` ajoutée aux campagnes (l'idempotence s'appuie sur
  `(company_id, year)` + présence de bulletins).
- Pas de reconstruction d'intéressement (absent des données).
- Pas de génération de PDF ni de notifications pour les campagnes importées.
- Pas de refonte du flux `create_campaign` existant.
