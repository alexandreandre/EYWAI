"""La phrase des heures non saisies nomme le mois de paie (Elsa, 26/11)."""

from app.modules.payroll.application.preflight_anomalies import _de_mois


def test_elision_des_mois():
    assert _de_mois(10) == "d'octobre"
    assert _de_mois(4) == "d'avril"
    assert _de_mois(8) == "d'août"
    assert _de_mois(11) == "de novembre"
    assert _de_mois(1) == "de janvier"
