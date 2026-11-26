"""La phrase des jours à compléter nomme la paie du mois (Elsa, 26/11)."""

from datetime import date

from app.shared.domain.pluriel import de_mois, phrase_jours_a_completer


def test_elision_des_mois():
    assert de_mois(10) == "d'octobre"
    assert de_mois(4) == "d'avril"
    assert de_mois(8) == "d'août"
    assert de_mois(11) == "de novembre"
    assert de_mois(1) == "de janvier"


def test_phrase_commune_au_controle_et_au_refus():
    assert (
        phrase_jours_a_completer(2, 10, date(2026, 9, 21), date(2026, 10, 25))
        == "2 jours à compléter pour la paie d'octobre (période du 21/09 au 25/10)"
    )
