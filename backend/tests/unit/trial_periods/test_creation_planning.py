"""Période d'essai créée à l'embauche : saisie du formulaire ou barème société."""

from datetime import date

from app.modules.trial_periods.application.creation import plan_trial_period


def _employee(**overrides):
    base = {
        "id": "e1",
        "hire_date": "2026-03-01",
        "contract_type": "CDI",
        "statut": "Non-Cadre",
        "contract_end_date": None,
    }
    base.update(overrides)
    return base


def test_cdi_non_cadre_suit_le_bareme():
    plan = plan_trial_period(_employee(), company_settings={}, requested=None)
    assert plan == {
        "start_date": date(2026, 3, 1),
        "duration_value": 2,
        "duration_unit": "mois",
        "renewal_allowed": True,
    }


def test_cadre_quatre_mois():
    plan = plan_trial_period(
        _employee(statut="Cadre"), company_settings={}, requested=None
    )
    assert plan["duration_value"] == 4


def test_saisie_explicite_prime_sur_le_bareme():
    plan = plan_trial_period(
        _employee(),
        company_settings={},
        requested={"duree_initiale": 3, "unite": "semaines", "renouvellement_possible": False},
    )
    assert plan["duration_value"] == 3
    assert plan["duration_unit"] == "semaines"
    assert plan["renewal_allowed"] is False


def test_apprenti_sans_periode():
    assert (
        plan_trial_period(
            _employee(contract_type="Apprentissage"), company_settings={}, requested=None
        )
        is None
    )


def test_sans_date_d_entree_rien_n_est_cree():
    assert plan_trial_period(_employee(hire_date=None), company_settings={}, requested=None) is None


def test_refus_explicite_du_formulaire():
    # has_periode_essai décoché : le formulaire envoie explicitement None.
    assert (
        plan_trial_period(_employee(), company_settings={}, requested=None, wanted=False)
        is None
    )


def test_cdd_court_suit_la_regle_legale():
    plan = plan_trial_period(
        _employee(contract_type="CDD", contract_end_date="2026-06-30"),
        company_settings={},
        requested=None,
    )
    assert plan["duration_unit"] == "jours"
    assert plan["duration_value"] == 14
