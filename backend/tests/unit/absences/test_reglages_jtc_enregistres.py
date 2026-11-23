"""La case « Compteur JTC » et ses deux nombres s'enregistrent (panne vue le 23/11 :
le serveur les ignorait sans rien dire)."""

from app.modules.absences.application.leave_settings_commands import _WRITABLE_POLICY_KEYS
from app.modules.absences.schemas.leave_settings import LeaveSettingsUpdate


def test_les_reglages_jtc_sont_enregistrables():
    assert {"jtc_enabled", "jtc_annual_days", "jtc_absence_threshold_days"} <= _WRITABLE_POLICY_KEYS


def test_chaque_reglage_enregistrable_existe_dans_le_schema():
    champs = set(LeaveSettingsUpdate.model_fields)
    assert _WRITABLE_POLICY_KEYS - champs == set()
