# Module exports — migration et autonomie

## Structure

- **api/** : router (prefix `/api/exports`), dependencies (`get_active_company_id`).
- **schemas/** : schémas Pydantic propres au module (requests, responses).
- **application/** : service (preview, generate, history, download), commands, queries, dto.
- **domain/** : règles métier, value_objects, interfaces.
- **infrastructure/** : repository, storage, queries, mappers, providers (délégation vers implémentations locales `export_*.py`).

## Autonomie (voir AUTONOMY_ANALYSIS.md)

Le module est **autonome** : il n'importe plus rien depuis `api/*`, `schemas/*`, `services/*`, ni `core` (legacy). Il s'appuie uniquement sur `app.core`, `app.shared`, `app.modules` et les librairies externes.

- **DB** : `app.core.database.supabase`
- **Export (CSV/XLSX, format période/devise)** : `app.shared.utils.export`
- **Générateurs** : implémentations locales dans `infrastructure/export_journal_paie.py`, `export_paiement_salaires.py`, `export_ecritures_comptables.py`, `export_formats_cabinet.py`, `export_dsn.py`

## Fichiers legacy (toujours présents, non utilisés par ce module)

- `api/routers/exports.py` : ancien router (peut rester pour compatibilité).
- `schemas/export.py` : peut réexporter depuis `app.modules.exports.schemas` pour d'autres consommateurs.
- `services/export_service.py`, `services/exports/*` : conservés ; d'autres parties de l'app (ex. `rib_alert_service`) peuvent encore les utiliser.

## Points inchangés

- Préfixe et routes : `POST /preview`, `POST /generate`, `GET /history`, `GET /download/{export_id}`.
- Noms des schémas et champs, branches par `export_type`, comportement métier et HTTP.
