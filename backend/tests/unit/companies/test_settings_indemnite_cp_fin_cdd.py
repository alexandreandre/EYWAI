"""Le réglage société « indemnité de congés payés de fin de CDD » : deux méthodes nommées."""

import pytest
from pydantic import ValidationError

from app.modules.companies.schemas.requests import CompanySettingsUpdate


def test_le_champ_est_declare():
    assert "indemnite_cp_fin_cdd" in CompanySettingsUpdate.model_fields


@pytest.mark.parametrize("methode", ["remuneration_versee", "salaire_retabli_solde_n1"])
def test_les_deux_methodes_passent_dans_le_delta(methode):
    delta = CompanySettingsUpdate(indemnite_cp_fin_cdd=methode).to_settings_delta()
    assert delta == {"indemnite_cp_fin_cdd": methode}


def test_absent_du_patch_il_ne_touche_pas_aux_reglages():
    assert CompanySettingsUpdate(medical_follow_up_enabled=True).to_settings_delta() == {
        "medical_follow_up_enabled": True
    }


def test_une_methode_inconnue_est_refusee():
    with pytest.raises(ValidationError):
        CompanySettingsUpdate(indemnite_cp_fin_cdd="quadra")
