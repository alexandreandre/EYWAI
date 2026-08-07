"""Paramétrage JTC société — repli désactivé, dérivation vers le domaine de calcul."""

from app.modules.absences.domain.jtc import (
    JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT,
    JTC_ANNUAL_DAYS_DEFAULT,
)
from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)


def test_jtc_desactive_par_defaut():
    """Aucune société hors MBC ne doit voir de compteur JTC apparaître."""
    policy = LeavePolicySettings()
    assert policy.jtc_enabled is False
    assert policy.jtc_settings.enabled is False


def test_jtc_settings_reprend_les_valeurs_de_la_politique():
    policy = LeavePolicySettings(
        jtc_enabled=True,
        jtc_annual_days=3,
        jtc_absence_threshold_days=30,
    )
    settings = policy.jtc_settings
    assert settings.enabled is True
    assert settings.annual_days == JTC_ANNUAL_DAYS_DEFAULT
    assert settings.absence_threshold_days == JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT


def test_solde_douverture_jtc_par_defaut_nul():
    assert EmployeeLeaveAdjustment.empty().jtc_opening_balance == 0.0
