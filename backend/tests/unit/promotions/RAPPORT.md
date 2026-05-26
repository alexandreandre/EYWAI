# Rapport d'exécution — Tests promotions exhaustifs

Date : exécution plan « scénarios promotions exhaustifs ».

## Synthèse

| Zone | Résultat |
|------|----------|
| Tests unitaires promotions | **97/97 OK** |
| Correctifs workflow | **Appliqués** (C5, C11, C13, submit UI) |
| Tests intégration HTTP | Code ajouté ; exécution locale bloquée (FastAPI `add_event_handler` / env) |
| Script Supabase | Lancé ; **skip** — aucun employé pour la company de test |
| Checklist UI F1–F8 | Validée par **analyse de code** ; F7–F8 à confirmer en navigateur |

## Correctifs livrés

1. **`mark_effective`** accepte `draft` et `approved` → `effective` + application employé.
2. **`update` / `delete`** acceptent `draft` et `pending_approval`.
3. **Frontend** [`PromotionDetail.tsx`](../../../frontend/src/pages/PromotionDetail.tsx) : bouton « Soumettre pour validation », mark-effective sur `draft` et `approved`.
4. **Tests** : matrice [`test_scenarios_matrix.py`](test_scenarios_matrix.py), registre [`SCENARIOS.md`](SCENARIOS.md).

## Scénarios critiques validés (auto)

- **A3a** Non-Cadre → Cadre : snapshot + apply (unit).
- **C5** approved → mark-effective : OK (plus de 400).
- **C2** submit → pending_approval : OK.
- **C11/C13** update/delete pending_approval : OK.
- Tous les types A1–A5 (draft / effective selon date).

## À faire côté environnement

1. Peupler une company de test avec au moins un employé, puis relancer :
   `cd backend && PYTHONPATH=. .venv-ci-local/bin/python tests/test_promotions_complet.py`
2. Valider F7–F8 en UI (filtres, lien entretien).
3. Tests intégration : lancer en CI ou après alignement FastAPI local.

## Risque produit documenté

- **`new_statut`** non contraint à `Cadre` / `Non-Cadre` (B7) — incohérences possibles avec le module paie (`Non-cadre` vs `Non-Cadre`).
