# Module rates : configs taux (payroll_config), GET /api/rates/all.
# Autonome : aucun import legacy (api/*, schemas/*, services/*). Dépend uniquement de app.core.database.
# Public API : app.modules.rates.application.get_all_rates, app.modules.rates.api.router.
__all__: list[str] = []
