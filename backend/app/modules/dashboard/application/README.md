# Analytics gestion — orchestration

`analytics_gestion.py` agrège des **queries read-only** exposées par chaque module métier
(certifications, CSE, legal_obligations, medical_follow_up, training, objectives, etc.).

Règle : les routers et le dashboard n'importent pas les repositories voisins ; chaque module
fournit une fonction du type `get_*_for_dashboard(company_id, period)`.
