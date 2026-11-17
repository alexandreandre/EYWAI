"""Variables de paie automatiques avant le bulletin : une fonction, les deux générateurs.

Réglage de la société « générer les variables avant le bulletin ». Il ne jouait
qu'au générateur des heures ; le forfait jours l'ignorait (audit du 17/11/2026,
test de parité).
"""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)


def variables_automatiques_avant_bulletin(
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    *,
    en_bac_a_sable: bool,
    contract_period_id: str | None,
) -> None:
    """Écrit les variables automatiques du seul salarié du bulletin, si la société
    le demande.

    Jamais en bac à sable : la génération des variables écrit les saisies du
    mois, et le bac à sable ne doit rien écrire. Celles du seul salarié du
    bulletin : les autres ne changent pas [J8]. Un échec n'arrête pas le
    bulletin : il est noté comme repli, donc dit sur le bulletin.
    """
    try:
        from app.modules.planning.infrastructure.repository import planning_repository

        planning_settings = planning_repository.get_company_planning_settings(str(company_id))
        if (
            not en_bac_a_sable
            and not contract_period_id
            and planning_settings
            and planning_settings.get("auto_generate_payroll_variables_before_payslip")
        ):
            from app.modules.payroll_variables.application.generate_monthly import (
                generate_monthly_variables,
            )

            generate_monthly_variables(
                str(company_id),
                year,
                month,
                dry_run=False,
                employee_id=str(employee_id),
            )
    except Exception as auto_var_exc:  # noqa: BLE001 — repli dit sur le bulletin
        logger.warning("Génération auto variables paie ignorée: %s", auto_var_exc)
        from app.modules.payroll.engine.replis import CODE_REPLI_VARIABLES_AUTO, noter_repli

        noter_repli(CODE_REPLI_VARIABLES_AUTO)
