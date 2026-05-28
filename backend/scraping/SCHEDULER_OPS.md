# Planification mensuelle des taux (ops)

Le rafraîchissement automatique des taux réglementaires repose sur :

1. **`scraping_schedules`** — une planification active par source critique (`is_critical = true`), par exemple :
   - `schedule_type`: `interval` avec `interval_days: 30`, ou
   - `schedule_type`: `cron` avec `cron_expression`: `0 6 1 * *` (1er de chaque mois à 06:00 UTC).

2. **`backend/scraping/scheduler.py`** — processus à exécuter en cron (VM, Cloud Run job, etc.) qui lit les schedules dont `next_run_at` est dépassé et lance les orchestrateurs.

3. **Page RH `/rates`** — en complément, une mise à jour automatique est proposée au **premier chargement du mois** (clé `localStorage` `rates_auto_sync_month`) via `POST /api/rates/sync`.

Configuration des schedules : interface Super Admin **Veille réglementaire**, onglet Sources / planifications, ou API `POST /api/scraping/schedules` (super admin uniquement).
