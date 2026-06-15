# Planification mensuelle des taux (ops)

Le rafraîchissement automatique repose sur deux mécanismes distincts :

## A. Taux réglementaires (scraping)

1. **`scraping_schedules`** — une planification active par source critique (`is_critical = true`), par exemple :
   - `schedule_type`: `interval` avec `interval_days: 30`, ou
   - `schedule_type`: `cron` avec `cron_expression`: `0 6 1 * *` (1er de chaque mois à 06:00 UTC).

2. **`backend/scraping/scheduler.py`** — processus cron qui lit les schedules dont `next_run_at` est dépassé et lance les orchestrateurs.

3. **Page RH `/rates`** — mise à jour automatique proposée au **premier chargement du mois** (`localStorage` `rates_auto_sync_month`) via `POST /api/rates/sync`.

## B. URLs officielles affichées en bas des cartes (sans rescraper les taux)

Validation mensuelle Sonar + HTTP des `scraping_sources.primary_url`, puis propagation vers `payroll_config.source_links` :

- **GitHub Actions** : workflow `scraping-repair-agent.yml` (validation URLs uniquement) — cron `0 5 1 * *` (1er du mois, 05:00 UTC) → `python -m agent --validate-sources`
- **Cron self-hosted** : `python backend/scraping/scheduler.py --validate-sources` (même fréquence recommandée)

Cette validation ne modifie pas les montants/taux ni les scripts de scraping : elle met à jour uniquement `scraping_sources.primary_url` et les pastilles des cartes Suivi des taux. Si la validation échoue, un second passage Sonar recherche automatiquement la nouvelle URL officielle à afficher.

Configuration des schedules scraping : interface Super Admin **Veille réglementaire**, onglet Sources / planifications, ou API `POST /api/scraping/schedules` (super admin uniquement).
