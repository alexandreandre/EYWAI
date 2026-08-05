"""Barème de période d'essai par société, avec repli légal."""

from app.modules.employees.domain.trial_period_bareme import (
    DEFAULT_ALERT_DAYS,
    resolve_alert_days,
    resolve_trial_proposal,
)


def test_cdi_non_cadre_deux_mois_par_defaut():
    p = resolve_trial_proposal({}, "CDI", "Non-Cadre")
    assert (p.duration_value, p.duration_unit, p.renewal_allowed) == (2, "mois", True)


def test_cdi_cadre_quatre_mois_par_defaut():
    p = resolve_trial_proposal({}, "CDI", "Cadre")
    assert (p.duration_value, p.duration_unit) == (4, "mois")


def test_apprentissage_exclu():
    assert resolve_trial_proposal({}, "Apprentissage", "Non-Cadre") is None


def test_stage_exclu():
    assert resolve_trial_proposal({}, "Stage", "Non-Cadre") is None


def test_cdd_court_un_jour_par_semaine_plafonne_a_deux_semaines():
    # Contrat de 4 mois, soit environ 17 semaines : le plafond de 14 jours
    # s'applique.
    p = resolve_trial_proposal({}, "CDD", "Non-Cadre", contract_duration_months=4)
    assert (p.duration_value, p.duration_unit, p.renewal_allowed) == (14, "jours", False)


def test_cdd_tres_court_sous_le_plafond():
    # Contrat de 6 semaines : 6 jours d'essai.
    p = resolve_trial_proposal(
        {}, "CDD", "Non-Cadre", contract_duration_months=6 / 4.348
    )
    assert (p.duration_value, p.duration_unit) == (6, "jours")


def test_cdd_long_un_mois():
    p = resolve_trial_proposal({}, "CDD", "Non-Cadre", contract_duration_months=9)
    assert (p.duration_value, p.duration_unit) == (1, "mois")


def test_cdd_sans_duree_connue_retombe_sur_un_mois():
    p = resolve_trial_proposal({}, "CDD", "Non-Cadre", contract_duration_months=None)
    assert (p.duration_value, p.duration_unit) == (1, "mois")


def test_bareme_societe_surcharge_le_defaut():
    settings = {
        "periode_essai": {
            "bareme": [
                {
                    "contract_type": "CDI",
                    "statut": "Cadre",
                    "duree": 3,
                    "unite": "mois",
                    "renouvellement": False,
                }
            ]
        }
    }
    p = resolve_trial_proposal(settings, "CDI", "Cadre")
    assert (p.duration_value, p.duration_unit, p.renewal_allowed) == (3, "mois", False)
    # Les lignes non surchargées gardent le défaut légal.
    assert resolve_trial_proposal(settings, "CDI", "Non-Cadre").duration_value == 2


def test_exclusions_parametrables():
    settings = {"periode_essai": {"exclusions": ["CDD"]}}
    assert resolve_trial_proposal(settings, "CDD", "Non-Cadre") is None


def test_regle_cdd_desactivable():
    settings = {
        "periode_essai": {
            "regle_legale_cdd": False,
            "bareme": [
                {
                    "contract_type": "CDD",
                    "statut": "Non-Cadre",
                    "duree": 3,
                    "unite": "semaines",
                    "renouvellement": False,
                }
            ],
        }
    }
    p = resolve_trial_proposal(settings, "CDD", "Non-Cadre", contract_duration_months=4)
    assert (p.duration_value, p.duration_unit) == (3, "semaines")


def test_delai_d_alerte_par_defaut_et_surcharge():
    assert resolve_alert_days({}) == DEFAULT_ALERT_DAYS
    assert resolve_alert_days({"periode_essai": {"alerte_jours": 30}}) == 30
    # Une valeur absurde retombe sur le défaut.
    assert resolve_alert_days({"periode_essai": {"alerte_jours": 0}}) == DEFAULT_ALERT_DAYS
    assert (
        resolve_alert_days({"periode_essai": {"alerte_jours": "trente"}})
        == DEFAULT_ALERT_DAYS
    )


def test_casse_et_espaces_ignores():
    p = resolve_trial_proposal({}, "  cdi ", "cadre")
    assert p.duration_value == 4
