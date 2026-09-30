"""L'alerte du filet (`alerte_heures_ecartees`) : quels jours écartés elle nomme.

Les heures sup se comptent par semaine civile : un jour écarté ne peut changer un
bulletin que s'il tombe dans une semaine de sa période (mois civil ∪ fenêtre des
variables). L'alerte nomme donc les jours du lundi de son premier jour au
dimanche de son dernier, et rien au-delà.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.application.heures_sur_arret import (
    CODE_ALERTE_HEURES_ECARTEES,
    alerte_heures_ecartees,
)
from app.modules.schedules.domain.conflits_arret import JourEnConflit

pytestmark = pytest.mark.unit

#: Septembre 2026 : le 1er est un mardi, le 30 un mercredi. Ses semaines vont du
#: lundi 31 août au dimanche 4 octobre.
DEBUT, FIN = date(2026, 9, 1), date(2026, 9, 30)


def _jour(annee: int, mois: int, jour: int, heures: float = 7.0) -> JourEnConflit:
    return JourEnConflit(jour, "arret_maladie", heures, annee=annee, mois=mois)


def _jours_nommes(alerte: dict | None) -> list[tuple[int, int]]:
    return [(j["mois"], j["jour"]) for j in (alerte or {}).get("jours", [])]


def test_les_semaines_de_la_periode_vont_du_lundi_au_dimanche():
    jours = [_jour(2026, 8, 31), _jour(2026, 9, 7), _jour(2026, 10, 4)]

    alerte = alerte_heures_ecartees(jours, DEBUT, FIN)

    assert _jours_nommes(alerte) == [(8, 31), (9, 7), (10, 4)]


def test_les_jours_de_m_moins_1_et_m_plus_1_hors_de_ces_semaines_sont_exclus():
    jours = [_jour(2026, 8, 30), _jour(2026, 8, 31), _jour(2026, 10, 4), _jour(2026, 10, 5)]

    alerte = alerte_heures_ecartees(jours, DEBUT, FIN)

    assert _jours_nommes(alerte) == [(8, 31), (10, 4)]
    assert alerte["message"].startswith(
        "Heures saisies pendant l'arrêt, écartées du calcul : le 31 août et le 4 octobre (14 h)."
    )


def test_une_fenetre_des_variables_qui_deborde_elargit_les_semaines():
    """Fenêtre du lundi 24 août au mercredi 23 septembre : la période commence le
    24 août, et le samedi 22 août reste dehors."""
    jours = [_jour(2026, 8, 22), _jour(2026, 8, 24)]

    alerte = alerte_heures_ecartees(jours, date(2026, 8, 24), FIN)

    assert _jours_nommes(alerte) == [(8, 24)]


def test_sans_jour_dans_les_semaines_pas_d_alerte():
    assert alerte_heures_ecartees([_jour(2026, 8, 30), _jour(2026, 10, 5)], DEBUT, FIN) is None
    assert alerte_heures_ecartees([], DEBUT, FIN) is None


def test_la_forme_de_l_alerte():
    alerte = alerte_heures_ecartees([_jour(2026, 9, 7, 8.5)], DEBUT, FIN)

    assert alerte == {
        "code": CODE_ALERTE_HEURES_ECARTEES,
        "critique": False,
        "severity": "warning",
        "message": (
            "Heures saisies pendant l'arrêt, écartées du calcul : le 7 septembre (8,5 h). "
            "Effacez-les du calendrier, ou corrigez l'arrêt si elles ont été travaillées."
        ),
        "jours": [{"annee": 2026, "mois": 9, "jour": 7, "heures": 8.5}],
    }
