"""Le réglage société « compensation des heures entre semaines » (option Gaëlle)."""

import pytest
from pydantic import ValidationError

from app.modules.companies.schemas.requests import CompanySettingsUpdate


def test_le_booleen_est_un_champ_declare_du_patch():
    assert "compensation_heures_entre_semaines" in CompanySettingsUpdate.model_fields


def test_le_booleen_passe_dans_le_delta_des_reglages():
    delta = CompanySettingsUpdate(compensation_heures_entre_semaines=True).to_settings_delta()
    assert delta == {"compensation_heures_entre_semaines": True}


def test_desactiver_l_option_est_conserve_dans_le_delta():
    """False n'est pas None : la société doit pouvoir revenir à la règle hebdomadaire."""
    delta = CompanySettingsUpdate(compensation_heures_entre_semaines=False).to_settings_delta()
    assert delta == {"compensation_heures_entre_semaines": False}


def test_absent_du_patch_il_ne_touche_pas_aux_reglages():
    assert CompanySettingsUpdate(medical_follow_up_enabled=True).to_settings_delta() == {
        "medical_follow_up_enabled": True
    }


def test_une_valeur_non_booleenne_est_refusee():
    with pytest.raises(ValidationError):
        CompanySettingsUpdate(compensation_heures_entre_semaines="oui")
