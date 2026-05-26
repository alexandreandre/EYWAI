# Registre des scénarios — Promotions

Légende couverture : `auto` = pytest unitaire/intégration, `manuel` = checklist UI, `supabase` = script DB réel, `—` = non exécuté.

| ID | Scénario | Attendu | Couverture | Statut |
|----|----------|---------|------------|--------|
| A1-poste-futur | Création poste, date future | draft | auto | OK |
| A1-poste-auj | Création poste, date aujourd'hui | effective + apply | auto | OK |
| A2-salaire-futur | Création salaire, date future | draft | auto | OK |
| A2-salaire-auj | Création salaire, date aujourd'hui | effective + apply | auto | OK |
| A3a-statut-nc-cadre | Non-Cadre → Cadre | snapshot + statut employé | auto | OK |
| A3b-statut-cadre-nc | Cadre → Non-Cadre | snapshot + statut employé | auto | OK |
| A3c-statut-identique | Cadre → Cadre | enregistré | auto | OK |
| A4-classif | Classification conventionnelle | draft/effective | auto | OK |
| A5-mixte | Poste + salaire + statut + classif | tous champs | auto | OK |
| A-RH0 | Sans accès RH | OK | auto | OK |
| A-RH1 | null → collaborateur_rh | OK | auto | OK |
| A-RH2 | null → rh | OK | auto | OK |
| A-RH3 | null → admin | 400 | auto | OK |
| A-RH4 | collaborateur_rh → rh/admin | OK | auto | OK |
| A-RH5 | rh → admin | OK | auto | OK |
| A-RH6 | rh → collaborateur_rh | 400 | auto | OK |
| A-RH7 | employé sans user_id + grant RH | 400 à apply | auto | OK |
| A-unique | 2e draft même employé | erreur DB | supabase | skip (pas d'employé test) |
| B1 | Aucun champ nouveau | 422 | auto | OK |
| B2 | Date effet hier | 422 | auto | OK |
| B3 | grant_rh sans new_rh_access | 422 | auto | OK |
| B4 | Transition RH invalide | 400 | auto | OK |
| B5 | employee_id inexistant | 404/500 | auto | partiel |
| B6 | statut sans new_statut | 422 | auto | OK |
| B7 | new_statut libre "cadre" | accepté | auto | OK |
| C1 | draft → mark-effective | effective + apply | auto | OK |
| C2 | draft → submit | pending_approval | auto | OK |
| C3 | pending → approve | approved + PDF | auto/intégration | OK |
| C4 | pending → reject | rejected | auto | OK |
| C5 | approved → mark-effective | effective + apply | auto | OK (corrigé) |
| C6 | approved depuis liste draft | N/A | — | N/A |
| C7 | effective → mark-effective | idempotent | auto | OK |
| C8 | rejected → mark-effective | 400 | auto | OK |
| C9 | cancelled → action | 400 | auto | OK |
| C10 | draft → update | 200 | auto | OK |
| C11 | pending → update | 200 | auto | OK (corrigé) |
| C12 | draft → delete | 204 | auto | OK |
| C13 | pending → delete | 204 | auto | OK (corrigé) |
| C14 | effective → delete | 400 | auto | OK |
| C15 | submit sans champ nouveau | 400 | auto | OK |
| D1 | GET sans auth | 401 | intégration | OK |
| D2 | GET collaborateur | 403 | intégration | OK |
| D3 | GET filtres | 200 | intégration | OK |
| D4 | GET by id 200/404 | | intégration | OK |
| D5 | GET stats | 200 | intégration | OK |
| D6 | GET employee RH access | 200 | auto | OK |
| D7 | GET document PDF | stream/404 | intégration | partiel |
| D8 | Pas active_company | 400 | intégration | partiel |
| E1 | Fiche employé après effective | statut à jour | supabase | skip (pas d'employé test) |
| E2 | PromotionComparison before/after | UI | manuel | à valider |
| E3 | Forfait jour après statut | paie | manuel | à valider |
| E4 | Registre carrière KPI | front | auto (careerActivity) | OK |
| E5 | Double mark-effective | pas double apply | auto | OK |
| F1 | Validations modal par type | toasts | manuel | à valider |
| F2 | Toast appliquée (date auj.) | | manuel | à valider |
| F3 | Toast brouillon (date fut.) | | manuel | à valider |
| F4 | Liste actions draft only | | manuel/code | OK |
| F5 | Approve/reject admin | | manuel | à valider |
| F6 | Mark-effective approved | 200 | manuel/code | OK (corrigé) |
| F7 | Filtres page Augmentations | | manuel | à valider |
| F8 | Lien entretien annuel | | manuel | à valider |
| G1 | Déjà Cadre → Cadre | enregistré | auto | OK |
| G2 | Salaire 0/négatif | | auto | partiel |
| G3 | Classification partielle | coefficient seul | auto | OK |
| G4 | Mixte statut+salaire | | auto | OK |
| G5 | Édition type poste→statut | draft | auto | OK |
| G6 | performance_review_id orphelin | | — | — |
| G7 | PDF échoue à approve | approved sans URL | auto | OK |
| G8 | Effective puis nouvelle promo | OK | supabase | skip (pas d'employé test) |

## Exécution automatisée (dernière passe)

```bash
cd backend && .venv-ci-local/bin/python -m pytest tests/unit/promotions/ --confcutdir=tests/unit/promotions -q
# 97 passed
```

Script Supabase : `PYTHONPATH=. python tests/test_promotions_complet.py` — nécessite employé dans la company de test.
