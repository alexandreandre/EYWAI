"""Restaurer une version revient à ses heures sup et à ses primes, puis recalcule.

Audit du 28/09 : la restauration recopiait l'ancien bulletin sans rien
recalculer ni revenir sur les variables du mois ; le prochain recalcul
effaçait la restauration.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payslips.domain.corrections import corrections_pour_revenir

pytestmark = pytest.mark.unit


def _bulletin(hs25=None, hs50=None, primes=(), non_soumises=(), declarees=None):
    brut = [{"libelle": "Salaire de base", "quantite": 151.67, "taux": 14.28, "gain": 2165.85}]
    if hs25 is not None:
        brut.append({"libelle": "Heures suppl. majorées à 25%", "quantite": hs25, "taux": 17.85, "gain": 1})
    if hs50 is not None:
        brut.append({"libelle": "Heures suppl. majorées à 50%", "quantite": hs50, "taux": 21.42, "gain": 1})
    for sid, libelle, montant in primes:
        brut.append({"libelle": libelle, "gain": montant, "saisie_id": sid})
    data = {
        "calcul_du_brut": brut,
        "primes_non_soumises": [
            {"libelle": libelle, "montant": montant, "saisie_id": sid}
            for sid, libelle, montant in non_soumises
        ],
    }
    if declarees is not None:
        data["heures_sup_declarees"] = {"hs25": declarees[0], "hs50": declarees[1], "planning": 6.0}
    return data


def test_une_version_ancienne_rend_ses_quantites_d_heures():
    c = corrections_pour_revenir(_bulletin(hs25=15.0), _bulletin(hs25=12.0, hs50=3.5))
    assert c.heures_sup == (12.0, 3.5)


def test_une_version_recente_rend_ses_heures_declarees():
    c = corrections_pour_revenir(_bulletin(hs25=6.0), _bulletin(hs25=4.0, declarees=(4.0, 0.0)))
    assert c.heures_sup == (4.0, 0.0)


def test_memes_heures_rien_a_declarer():
    assert corrections_pour_revenir(_bulletin(hs25=6.0), _bulletin(hs25=6.0)).heures_sup is None
    assert (
        corrections_pour_revenir(
            _bulletin(hs25=4.0, declarees=(4.0, 0.0)), _bulletin(hs25=4.0, declarees=(4.0, 0.0))
        ).heures_sup
        is None
    )


def test_une_prime_ajoutee_depuis_est_retiree():
    c = corrections_pour_revenir(_bulletin(primes=[("s-1", "Prime", 100.0)]), _bulletin())
    assert c.primes.retirees == ("s-1",)


def test_une_prime_corrigee_depuis_reprend_son_montant():
    c = corrections_pour_revenir(
        _bulletin(primes=[("s-1", "Prime", 150.0)]), _bulletin(primes=[("s-1", "Prime", 100.0)])
    )
    assert c.primes.modifiees == (("s-1", 100.0),)


def test_une_prime_supprimee_depuis_est_recreee_avec_son_regime():
    c = corrections_pour_revenir(
        _bulletin(),
        _bulletin(primes=[("s-1", "Prime de chantier", 100.0)], non_soumises=[("s-2", "Panier", 7.5)]),
    )
    assert c.primes.ajoutees == (
        {"name": "Prime de chantier", "amount": 100.0, "is_socially_taxed": True,
         "is_taxable": True, "catalog_prime_id": None},
        {"name": "Panier", "amount": 7.5, "is_socially_taxed": False,
         "is_taxable": False, "catalog_prime_id": None},
    )


def test_une_saisie_encore_presente_n_est_pas_recreee():
    c = corrections_pour_revenir(
        _bulletin(), _bulletin(primes=[("s-1", "Prime", 100.0)]), saisies_existantes={"s-1"}
    )
    assert c.primes.ajoutees == ()
    assert c.primes.modifiees == (("s-1", 100.0),)


def test_meme_heures_et_memes_primes_rien_a_restaurer():
    b = _bulletin(hs25=6.0, primes=[("s-1", "Prime", 100.0)])
    assert not corrections_pour_revenir(b, b).change_des_variables


# --- La commande ---

from app.modules.payslips.application import corrections as mod  # noqa: E402
from app.modules.payslips.application.dto import (  # noqa: E402
    PayslipBadRequestError,
    PayslipNotFoundError,
    RestorePayslipInput,
)


def _restaurer(bulletin, version=3, existantes=()):
    with (
        patch.object(mod, "_lire_bulletin", return_value=bulletin),
        patch.object(mod, "_refuser_si_importe"),
        patch.object(mod, "_saisies_existantes", return_value=set(existantes)),
        patch.object(mod, "corriger_bulletin", return_value={"ok": True}) as corriger,
    ):
        resultat = mod.restaurer_version(
            RestorePayslipInput(payslip_id="ps-1", version=version, current_user_id="rh-1", current_user_name="RH")
        )
    return resultat, corriger


BULLETIN = {
    "id": "ps-1", "employee_id": "emp-1", "company_id": "comp-1", "year": 2026, "month": 8,
    "payslip_data": _bulletin(hs25=4.0, declarees=(4.0, 0.0)),
    "edit_history": [
        {"version": 3, "previous_payslip_data": _bulletin(hs25=6.0)},
        {"version": 4, "previous_payslip_data": _bulletin(hs25=4.0, declarees=(4.0, 0.0))},
    ],
}


def test_restaurer_passe_par_la_correction_avec_un_resume():
    _, corriger = _restaurer(BULLETIN, version=3)
    entree = corriger.call_args.args[0]
    assert entree.corrections.heures_sup == (6.0, 0.0)
    assert entree.changes_summary == "Retour à la version 3"
    assert entree.current_user_id == "rh-1"


def test_une_version_identique_n_a_rien_a_restaurer():
    with pytest.raises(PayslipBadRequestError, match="rien à restaurer"):
        _restaurer(BULLETIN, version=4)


def test_une_version_inconnue_est_introuvable():
    with pytest.raises(PayslipNotFoundError):
        _restaurer(BULLETIN, version=9)


def test_un_bulletin_importe_ne_se_restaure_pas():
    with (
        patch.object(mod, "_lire_bulletin", return_value=BULLETIN),
        patch.object(mod, "_refuser_si_importe", side_effect=PayslipBadRequestError("repris")),
        patch.object(mod, "corriger_bulletin") as corriger,
    ):
        with pytest.raises(PayslipBadRequestError):
            mod.restaurer_version(
                RestorePayslipInput(payslip_id="ps-1", version=3, current_user_id="rh-1", current_user_name="RH")
            )
    corriger.assert_not_called()
