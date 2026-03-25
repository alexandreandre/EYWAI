"""
Audit statique du moteur de paie sous app.modules.payroll.

Vérifie que les mêmes fonctions, le même moteur et le même enchaînement
sont présents dans l'app (sans exécuter de génération ni Supabase).
"""

from __future__ import annotations

import inspect


# --- Helpers communs (payslip_run_common) ---
def test_common_has_get_end_date_for_month():
    from app.modules.payroll.documents.payslip_run_common import _get_end_date_for_month
    from datetime import date

    # 1er lundi d'avril 2026
    got = _get_end_date_for_month(2026, 4, 0, 1)
    assert got == date(2026, 4, 6)


def test_common_has_definir_periode_de_paie():
    from app.modules.payroll.documents import payslip_run_common

    assert hasattr(payslip_run_common, "definir_periode_de_paie")
    sig = inspect.signature(payslip_run_common.definir_periode_de_paie)
    params = list(sig.parameters)
    assert "contexte" in params and "annee" in params and "mois" in params


def test_common_has_mettre_a_jour_cumuls():
    from app.modules.payroll.documents import payslip_run_common

    assert hasattr(payslip_run_common, "mettre_a_jour_cumuls")
    sig = inspect.signature(payslip_run_common.mettre_a_jour_cumuls)
    params = list(sig.parameters)
    assert "contexte" in params and "chemin_employe" in params and "mois" in params


def test_common_has_creer_calendrier_etendu():
    from app.modules.payroll.documents import payslip_run_common

    assert hasattr(payslip_run_common, "creer_calendrier_etendu")
    sig = inspect.signature(payslip_run_common.creer_calendrier_etendu)
    params = list(sig.parameters)
    assert (
        "chemin_employe" in params
        and "date_debut_periode" in params
        and "date_fin_periode" in params
    )


# --- Run heures : même moteur que legacy ---
def test_run_heures_imports_engine():
    from app.modules.payroll.documents import payslip_run_heures as m

    assert hasattr(m, "ContextePaie")
    assert hasattr(m, "calculer_salaire_brut")
    assert hasattr(m, "calculer_cotisations")
    assert hasattr(m, "calculer_reduction_generale")
    assert hasattr(m, "calculer_net_et_impot")
    assert hasattr(m, "creer_bulletin_final")


def test_run_heures_has_run_function():
    from app.modules.payroll.documents.payslip_run_heures import (
        run_payslip_generation_heures,
    )

    sig = inspect.signature(run_payslip_generation_heures)
    params = list(sig.parameters)
    assert params == ["employee_path", "year", "month", "engine_root"]


def test_run_heures_uses_common_definir_periode_and_calendrier():
    from app.modules.payroll.documents import payslip_run_heures

    src = inspect.getsource(payslip_run_heures.run_payslip_generation_heures)
    assert "definir_periode_de_paie" in src
    assert "creer_calendrier_etendu" in src
    assert "mettre_a_jour_cumuls" in src


# --- Run forfait : même moteur et analyser ---
def test_run_forfait_imports_engine_and_analyser():
    from app.modules.payroll.documents import payslip_run_forfait as m

    assert hasattr(m, "analyser_jours_forfait_du_mois")
    assert hasattr(m, "calculer_salaire_brut_forfait")
    assert hasattr(m, "calculer_cotisations")
    assert hasattr(m, "calculer_reduction_generale")
    assert hasattr(m, "calculer_net_et_impot")
    assert hasattr(m, "creer_bulletin_final")


def test_run_forfait_has_run_function():
    from app.modules.payroll.documents.payslip_run_forfait import (
        run_payslip_generation_forfait,
    )

    sig = inspect.signature(run_payslip_generation_forfait)
    params = list(sig.parameters)
    assert params == ["employee_path", "year", "month", "engine_root"]


def test_run_forfait_uses_common():
    from app.modules.payroll.documents import payslip_run_forfait

    src = inspect.getsource(payslip_run_forfait.run_payslip_generation_forfait)
    assert "definir_periode_de_paie" in src
    assert "creer_calendrier_etendu" in src
    assert "mettre_a_jour_cumuls" in src


# --- Moteur : source de vérité dans app.modules.payroll.engine ---
def test_engine_contexte_exports_contexte_paie():
    """Le module engine.contexte expose ContextePaie (cœur du moteur)."""
    from app.modules.payroll.engine import contexte as app_ctx

    assert hasattr(app_ctx, "ContextePaie")
    assert app_ctx.ContextePaie is not None
