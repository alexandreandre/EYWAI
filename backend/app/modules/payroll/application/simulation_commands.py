"""
Commandes applicatives : simulation de bulletins, calcul inverse (net → brut), génération PDF simulée.
Le router simulation appelle ce module, pas engine ni documents directement.
"""

from __future__ import annotations

from typing import Any, Dict, List


def run_reverse_calculation(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    baremes: Dict[str, Any],
    calendrier: Dict[str, Any],
    saisies: Dict[str, Any],
    net_target: float,
    net_type: str,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calcul inverse : détermine le brut nécessaire pour obtenir un net cible.
    Délègue à engine.calcul_inverse.calculer_brut_depuis_net.
    Retourne un dict compatible avec ReverseCalculationResponse (brut_calcule, net_obtenu, ecart, iterations, convergence, bulletin_complet, cout_employeur).
    """
    from app.modules.payroll.engine.calcul_inverse import (
        calculer_brut_depuis_net,
        CalculInverseError,
        NonConvergenceError,
    )

    try:
        return calculer_brut_depuis_net(
            net_cible=net_target,
            type_net=net_type,
            employee_data=employee_data,
            company_data=company_data,
            baremes=baremes,
            calendrier=calendrier,
            saisies=saisies,
            options=options,
        )
    except (CalculInverseError, NonConvergenceError) as e:
        raise ValueError(str(e)) from e


def creer_simulation_bulletin(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    baremes: Dict[str, Any],
    month: int,
    year: int,
    scenario_data: Dict[str, Any],
    prefill_from_real: bool,
    calendrier_reel: Any = None,
    saisies_reelles: Any = None,
) -> Dict[str, Any]:
    """Crée un bulletin simulé. Délègue à engine.simulation."""
    from app.modules.payroll.engine.simulation import creer_simulation_bulletin as _impl

    return _impl(
        employee_data=employee_data,
        company_data=company_data,
        baremes=baremes,
        month=month,
        year=year,
        scenario_params=scenario_data,
        prefill_from_real=prefill_from_real,
        calendrier_reel=calendrier_reel,
        saisies_reelles=saisies_reelles,
    )


def comparer_simulation_reel(
    bulletin_simule: Dict[str, Any],
    bulletin_reel: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare simulation et bulletin réel. Délègue à engine.simulation."""
    from app.modules.payroll.engine.simulation import comparer_simulation_reel as _impl

    return _impl(
        bulletin_simule=bulletin_simule,
        bulletin_reel=bulletin_reel,
    )


def generer_scenarios_predefinis(employee_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Génère des scénarios de simulation prédéfinis. Délègue à engine.simulation."""
    from app.modules.payroll.engine.simulation import (
        generer_scenarios_predefinis as _impl,
    )

    return _impl(employee_data=employee_data)


def get_simulated_payslip_generator() -> Any:
    """Retourne la classe SimulatedPayslipGenerator (documents). Pour génération PDF simulée."""
    from app.modules.payroll.documents.simulated_payslip_generator import (
        SimulatedPayslipGenerator,
    )

    return SimulatedPayslipGenerator
