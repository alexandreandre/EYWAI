"""Maintien et IJSS subrogées d'un arrêt qui dépasse la sortie (A1, 17/11).

Sortie le 15/10, arrêt du 12 au 23/10 : le bulletin maintenait et indemnisait
jusqu'au 23/10 (9 jours d'IJSS, 5 de maintien). Le contrat a pris fin le 15 :
l'employeur ne maintient plus rien, la Sécurité sociale paie le salarié en
direct ; sur le bulletin, l'arrêt s'arrête au dernier jour du contrat.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.unit.payroll.profils_salaries import ANNEE, MOIS, PROFILS, SOCIETE, banc  # noqa: F401

pytestmark = pytest.mark.unit

SORTIE = 15


def _arret(debut: int, fin: int) -> dict[int, dict]:
    """Un arrêt maladie du `debut` au `fin` du mois, week-ends compris (bornes réelles)."""
    jours = {}
    for j in range(debut, fin + 1):
        ouvre = date(ANNEE, MOIS, j).weekday() < 5
        jours[j] = {
            "type": "arret_maladie" if ouvre else "weekend",
            "arret_type": "maladie_simple",
            "date_debut_arret_reel": f"{ANNEE}-{MOIS:02d}-{debut:02d}",
            "date_fin_arret_reel": f"{ANNEE}-{MOIS:02d}-{fin:02d}",
        }
    return jours


def _sortie_le_15() -> dict:
    return {"contract_end_date": f"{ANNEE}-{MOIS:02d}-{SORTIE:02d}"}


def _ij(donnees: dict) -> dict:
    return (donnees.get("bloc_maintien") or {}).get("ijss") or {}


@pytest.mark.parametrize("profil", PROFILS)
def test_rien_n_est_maintenu_ni_indemnise_apres_la_sortie(banc, profil):  # noqa: F811
    donnees = banc.generer(profil, jours=_arret(12, 23), fiche_en_plus=_sortie_le_15())

    # 12, 13, 14 : carence ; le 15, dernier jour du contrat, seul jour indemnisé.
    assert _ij(donnees).get("nb_jours_indemnises") == 1
    assert float(donnees["synthese_net"].get("maintien_employeur") or 0.0) == pytest.approx(0.0)
    ij_subrogees = float(donnees["synthese_net"].get("ijss_subrogees") or 0.0)
    assert ij_subrogees == pytest.approx(float(_ij(donnees)["ijss_journaliere"]), abs=0.01)
    # Le bulletin le dit (relecture du 18/11) : jamais en silence.
    assert any(
        "après le dernier jour du contrat" in a and "23/10/2026" in a
        for a in donnees["synthese_net"].get("alertes_maintien") or []
    )


@pytest.mark.parametrize("profil", ("heures", "forfait_jours"))
def test_sans_subrogation_les_ij_deduites_s_arretent_aussi_a_la_sortie(banc, profil):  # noqa: F811
    banc.base.tables["company_maintenance_settings"] = [
        {"company_id": SOCIETE, "subrogation_mode": "never"}
    ]
    donnees = banc.generer(profil, jours=_arret(12, 23), fiche_en_plus=_sortie_le_15())

    assert _ij(donnees).get("nb_jours_indemnises") == 1
    assert float(donnees["synthese_net"].get("maintien_employeur") or 0.0) == pytest.approx(0.0)


@pytest.mark.parametrize("profil", ("heures", "forfait_jours"))
def test_temoin_sans_sortie_l_arret_est_maintenu_jusqu_au_bout(banc, profil):  # noqa: F811
    donnees = banc.generer(profil, jours=_arret(12, 23))

    assert _ij(donnees).get("nb_jours_indemnises") == 9
    assert float(donnees["synthese_net"].get("maintien_employeur") or 0.0) > 0.0
    assert not any(
        "après le dernier jour du contrat" in a for a in donnees["synthese_net"].get("alertes_maintien") or []
    )
