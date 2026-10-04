"""Un bulletin non recalculé ou dont les cumuls ne suivent plus ne se valide pas."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payslips.domain.coherence import (
    MESSAGE_A_RECALCULER,
    MESSAGE_A_REGENERER,
    MESSAGE_RECALCUL_EN_ATTENTE,
    a_regenerer,
    cumul_brut,
    raisons_de_ne_pas_valider,
)

pytestmark = pytest.mark.unit


def _bulletin(brut, cumul):
    return {"salaire_brut": brut, "cumuls": {"cumuls": {"brut_total": cumul}}}


def test_un_recalcul_en_attente_empeche_la_validation():
    assert raisons_de_ne_pas_valider({"recalcul_en_attente": {"erreur": "x"}}) == [
        MESSAGE_RECALCUL_EN_ATTENTE
    ]
    assert raisons_de_ne_pas_valider({"salaire_brut": 1}) == []


def test_un_bulletin_perime_empeche_la_validation():
    data = {"parametres": {"empreinte_entrees": "a" * 64}}
    assert raisons_de_ne_pas_valider(data, "b" * 64) == [MESSAGE_A_RECALCULER]
    assert raisons_de_ne_pas_valider(data, "a" * 64) == []
    assert raisons_de_ne_pas_valider({"salaire_brut": 1}, "a" * 64) == []
    assert raisons_de_ne_pas_valider(data, None) == []


def test_le_cumul_brut_se_lit_dans_les_deux_formes():
    assert cumul_brut(_bulletin(1, 13929.11)) == 13929.11
    assert cumul_brut({"cumuls": {"brut_total": 5.0}}) == 5.0
    assert cumul_brut({}) is None


def test_des_cumuls_qui_se_suivent_ne_disent_rien():
    """Exemple réel d'août : 13 929,11 − 742,16 = 13 186,95, le cumul de juillet."""
    assert a_regenerer(_bulletin(742.16, 13929.11), 13186.95) is None


def test_un_mois_precedent_change_depuis_le_calcul_est_signale():
    assert a_regenerer(_bulletin(742.16, 13929.11), 13286.95) == MESSAGE_A_REGENERER


def test_sans_mois_precedent_rien_a_dire():
    assert a_regenerer(_bulletin(742.16, 13929.11), None) is None
    assert a_regenerer({"salaire_brut": 742.16}, 13186.95) is None


def test_janvier_n_a_pas_de_mois_precedent_dans_l_annee():
    from app.modules.payslips.application.coherence import cumul_brut_du_mois_precedent

    assert cumul_brut_du_mois_precedent("e1", 2026, 1) is None


def test_un_bulletin_repris_n_est_jamais_a_regenerer():
    from app.modules.payslips.application import coherence

    with patch.object(coherence, "cumul_brut_du_mois_precedent", return_value=1.0):
        assert coherence.signal_a_regenerer(
            {"origine": "importe", "employee_id": "e", "year": 2026, "month": 5,
             "payslip_data": _bulletin(742.16, 13929.11)}
        ) is None


def test_la_validation_est_refusee_avec_les_raisons():
    from app.modules.payslips.application import comparison_service as cs
    from app.modules.payslips.application.dto import PayslipBadRequestError, UserContext

    detail = {
        "id": "ps-1", "employee_id": "e1", "company_id": "c1", "year": 2026, "month": 8,
        "payslip_data": {"recalcul_en_attente": {"erreur": "x"}},
    }
    ctx = UserContext(user_id="rh", is_platform_admin=False,
                      has_rh_access_in_company=lambda _c: True, active_company_id="c1")
    with (
        patch.object(cs, "payslip_meta_reader", MagicMock()),
        patch.object(cs, "_ensure_edit_meta"),
        patch.object(cs, "get_payslip_details", return_value=detail),
        patch.object(cs, "signal_a_regenerer", return_value=MESSAGE_A_REGENERER),
        patch.object(cs, "_etat_actuel_du_bulletin", return_value=(None, None)),
        patch.object(cs, "mark_payslip_validated") as valider,
    ):
        with pytest.raises(PayslipBadRequestError) as exc:
            cs.validate_payslip_for_user("ps-1", ctx)
    assert MESSAGE_RECALCUL_EN_ATTENTE in str(exc.value)
    assert MESSAGE_A_REGENERER in str(exc.value)
    valider.assert_not_called()


def test_la_validation_est_refusee_si_l_empreinte_a_change():
    from app.modules.payslips.application import comparison_service as cs
    from app.modules.payslips.application.dto import PayslipBadRequestError, UserContext

    detail = {
        "id": "ps-1", "employee_id": "e1", "company_id": "c1", "year": 2026, "month": 8,
        "payslip_data": {"parametres": {"empreinte_entrees": "a" * 64}},
    }
    ctx = UserContext(user_id="rh", is_platform_admin=False,
                      has_rh_access_in_company=lambda _c: True, active_company_id="c1")
    with (
        patch.object(cs, "payslip_meta_reader", MagicMock()),
        patch.object(cs, "_ensure_edit_meta"),
        patch.object(cs, "get_payslip_details", return_value=detail),
        patch.object(cs, "signal_a_regenerer", return_value=None),
        patch.object(cs, "_etat_actuel_du_bulletin", return_value=("b" * 64, None)),
        patch.object(cs, "mark_payslip_validated") as valider,
    ):
        with pytest.raises(PayslipBadRequestError) as exc:
            cs.validate_payslip_for_user("ps-1", ctx)
    assert MESSAGE_A_RECALCULER in str(exc.value)
    valider.assert_not_called()


# --- Cascade : l'empreinte des cumuls du mois d'avant décide ------------------


def _detail(**surcharges):
    detail = {"origine": "calcule", "employee_id": "e", "year": 2026, "month": 5,
              "payslip_data": _bulletin(742.16, 13929.11)}
    detail.update(surcharges)
    return detail


def test_des_cumuls_d_avant_changes_sont_a_regenerer_meme_a_brut_identique():
    """Mars recalculé après une correction de la réduction générale : son brut ne
    bouge pas, avril reste faux. Le contrôle du seul brut cumulé ne le voyait pas."""
    from app.modules.payslips.application import coherence

    with patch.object(coherence, "cumul_brut_du_mois_precedent", return_value=13186.95):
        assert coherence.signal_a_regenerer(_detail(), True) == MESSAGE_A_REGENERER


def test_des_cumuls_d_avant_inchanges_font_foi_sur_le_brut_cumule():
    """Premier mois d'un nouveau contrat : le brut cumulé repart de zéro et ne suit
    plus le mois d'avant, sans que rien ne soit à régénérer."""
    from app.modules.payslips.application import coherence

    with patch.object(coherence, "cumul_brut_du_mois_precedent", return_value=9000.0):
        assert coherence.signal_a_regenerer(_detail(), False) is None


def test_sans_empreinte_des_cumuls_le_brut_cumule_reste_le_controle():
    from app.modules.payslips.application import coherence

    with patch.object(coherence, "cumul_brut_du_mois_precedent", return_value=13286.95):
        assert coherence.signal_a_regenerer(_detail(), None) == MESSAGE_A_REGENERER
        assert coherence.signal_a_regenerer(_detail()) == MESSAGE_A_REGENERER


def test_un_bulletin_repris_n_est_jamais_a_regenerer_meme_si_les_cumuls_ont_change():
    from app.modules.payslips.application import coherence

    assert coherence.signal_a_regenerer(_detail(origine="importe"), True) is None


def test_la_validation_est_refusee_si_le_mois_d_avant_a_change_une_seule_fois():
    from app.modules.payslips.application import comparison_service as cs
    from app.modules.payslips.application.dto import PayslipBadRequestError, UserContext

    detail = {
        "id": "ps-1", "employee_id": "e1", "company_id": "c1", "year": 2026, "month": 8,
        "origine": "calcule", "payslip_data": {"parametres": {"empreinte_entrees": "a" * 64}},
    }
    ctx = UserContext(user_id="rh", is_platform_admin=False,
                      has_rh_access_in_company=lambda _c: True, active_company_id="c1")
    with (
        patch.object(cs, "payslip_meta_reader", MagicMock()),
        patch.object(cs, "_ensure_edit_meta"),
        patch.object(cs, "get_payslip_details", return_value=detail),
        patch.object(cs, "_etat_actuel_du_bulletin", return_value=("a" * 64, True)),
        patch.object(cs, "mark_payslip_validated") as valider,
    ):
        with pytest.raises(PayslipBadRequestError) as exc:
            cs.validate_payslip_for_user("ps-1", ctx)
    assert str(exc.value).count(MESSAGE_A_REGENERER) == 1
    assert MESSAGE_A_RECALCULER not in str(exc.value)
    valider.assert_not_called()
