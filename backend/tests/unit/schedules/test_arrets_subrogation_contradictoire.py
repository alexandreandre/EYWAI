"""Deux arrêts validés qui se recouvrent avec une subrogation différente.

Septembre 2026 : un arrêt subrogé du 17/08 au 03/09, sa prolongation subrogée
du 03/09 au 18/09, puis un arrêt non subrogé saisi sur tout le mois. Le
bulletin suit le planning (le dernier validé) sans le dire. On ne bloque pas
la saisie (une prolongation recouvre souvent un jour) : le bulletin alerte.
"""

from datetime import date, timedelta

from app.modules.schedules.domain.conflits_arret import alerte_arrets_contradictoires


def _jours(debut: date, fin: date) -> list[str]:
    return [(debut + timedelta(days=i)).isoformat() for i in range((fin - debut).days + 1)]


def _arret(debut: date, fin: date, subrogation) -> dict:
    return {
        "type": "arret_maladie",
        "status": "validated",
        "subrogation_active": subrogation,
        "selected_days": _jours(debut, fin),
    }


SEPT = (date(2026, 9, 1), date(2026, 9, 30))


def test_le_cas_de_septembre_alerte_sur_les_jours_contradictoires():
    demandes = [
        _arret(date(2026, 8, 17), date(2026, 9, 3), True),
        _arret(date(2026, 9, 1), date(2026, 9, 30), False),
        _arret(date(2026, 9, 3), date(2026, 9, 18), True),
    ]
    alerte = alerte_arrets_contradictoires(demandes, *SEPT)
    assert alerte["code"] == "arrets_subrogation_contradictoire"
    assert alerte["critique"] is False
    assert [j["jour"] for j in alerte["jours"]] == list(range(1, 19))
    assert alerte["message"] == (
        "Deux arrêts validés se recouvrent du 1er au 18 septembre, l'un avec subrogation, "
        "l'autre sans. Le bulletin suit le planning : vérifiez dans Congés & absences "
        "quel arrêt est juste et corrigez l'autre."
    )


def test_une_prolongation_de_meme_subrogation_ne_dit_rien():
    demandes = [
        _arret(date(2026, 8, 17), date(2026, 9, 3), False),
        _arret(date(2026, 9, 3), date(2026, 9, 18), False),
    ]
    assert alerte_arrets_contradictoires(demandes, *SEPT) is None


def test_un_recouvrement_hors_du_mois_ne_dit_rien():
    demandes = [
        _arret(date(2026, 8, 10), date(2026, 8, 20), True),
        _arret(date(2026, 8, 15), date(2026, 8, 31), False),
    ]
    assert alerte_arrets_contradictoires(demandes, *SEPT) is None


def test_les_autres_absences_ne_comptent_pas():
    demandes = [
        _arret(date(2026, 9, 1), date(2026, 9, 5), True),
        {"type": "conge_paye", "status": "validated", "subrogation_active": False,
         "selected_days": _jours(date(2026, 9, 1), date(2026, 9, 5))},
    ]
    assert alerte_arrets_contradictoires(demandes, *SEPT) is None
