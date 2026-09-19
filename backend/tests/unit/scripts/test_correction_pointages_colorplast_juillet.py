"""La correction de juillet 2026 sur le test : une fonction pure, rejouable."""

from scripts.correction_pointages_colorplast_juillet import appliquer_corrections


def _reel():
    return [
        {"jour": 16, "type": "travail", "heures_faites": -10.5},
        {"jour": 17, "type": "travail", "heures_faites": -0.5},
        {"jour": 20, "type": "travail", "heures_faites": 10.5},
        {"jour": 29, "type": "travail", "heures_faites": 8.5},
    ]


def test_corrige_les_cases_retire_les_jours_de_juin_et_garde_le_reste():
    nouveau, journal = appliquer_corrections(_reel(), {16: 10.0, 17: 6.5}, {29, 30})

    assert [(d["jour"], d["heures_faites"]) for d in nouveau] == [
        (16, 10.0),
        (17, 6.5),
        (20, 10.5),
    ]
    assert all(d["type"] == "travail" for d in nouveau)
    assert journal == [(16, -10.5, 10.0), (17, -0.5, 6.5), (29, 8.5, None)]


def test_une_case_absente_du_calendrier_est_creee_en_travail():
    nouveau, journal = appliquer_corrections([], {24: 4.5}, set())

    assert nouveau == [{"jour": 24, "type": "travail", "heures_faites": 4.5}]
    assert journal == [(24, None, 4.5)]


def test_rejouer_ne_change_plus_rien():
    premier, _ = appliquer_corrections(_reel(), {16: 10.0, 17: 6.5}, {29, 30})

    second, journal = appliquer_corrections(premier, {16: 10.0, 17: 6.5}, {29, 30})

    assert second == premier
    assert journal == []
