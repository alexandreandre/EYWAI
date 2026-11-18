"""Forfait jours, sortie après la fin d'une période décalée (A9, 18/11).

Période d'octobre du 21/09 au 25/10, sortie le 28/10 : il n'y aura pas de
bulletin de novembre. Les jours du 26 au 28/10 étaient sous contrat mais hors
de toute période : ni retenue, ni maintien, ni IJ. La période du forfait va
désormais jusqu'au dernier jour du contrat, comme la fenêtre des heures.
"""

from __future__ import annotations

from datetime import date

import pytest

from tests.unit.payroll.profils_salaries import ANNEE, MOIS, banc  # noqa: F401

pytestmark = pytest.mark.unit

SORTIE = {"contract_type": "CDD", "hire_date": "2025-01-06", "contract_end_date": f"{ANNEE}-{MOIS:02d}-28"}


def _arret(debut: int, fin: int) -> dict[int, dict]:
    jours = {}
    for j in range(debut, fin + 1):
        jours[j] = {
            "type": "arret_maladie" if date(ANNEE, MOIS, j).weekday() < 5 else "weekend",
            "arret_type": "maladie_simple",
            "date_debut_arret_reel": f"{ANNEE}-{MOIS:02d}-{debut:02d}",
            "date_fin_arret_reel": f"{ANNEE}-{MOIS:02d}-{fin:02d}",
        }
    return jours


@pytest.mark.parametrize("profil", ("heures", "forfait_jours"))
def test_l_arret_est_indemnise_jusqu_a_la_sortie(banc, profil):  # noqa: F811
    donnees = banc.generer(profil, jours=_arret(19, 31), fiche_en_plus=SORTIE)

    # 19, 20, 21 : carence ; du 22 au 28 : 7 jours indemnisés, puis la sortie.
    assert (donnees["bloc_maintien"]["ijss"]).get("nb_jours_indemnises") == 7


def test_un_sans_solde_apres_le_25_est_retenu_au_mois_de_sortie(banc):  # noqa: F811
    avec = banc.generer("forfait_jours", jours={27: "absence_non_remuneree"}, fiche_en_plus=SORTIE)
    sans = banc.generer("forfait_jours", fiche_en_plus=SORTIE)

    assert float(avec["salaire_brut"]) < float(sans["salaire_brut"]) - 1.0


def test_hors_mois_de_sortie_la_periode_ne_bouge_pas(banc):  # noqa: F811
    """Sortie en novembre : le bulletin d'octobre garde sa période au 25/10."""
    novembre = {**SORTIE, "contract_end_date": f"{ANNEE}-11-27"}
    avec = banc.generer("forfait_jours", jours={27: "absence_non_remuneree"}, fiche_en_plus=novembre)
    sans = banc.generer("forfait_jours", fiche_en_plus=novembre)

    assert float(avec["salaire_brut"]) == pytest.approx(float(sans["salaire_brut"]), abs=0.01)


def _arret_a_cheval() -> tuple[dict[int, dict], dict[tuple[int, int], dict[int, dict]]]:
    """Arrêt du 19/10 au 13/11 : les jours d'octobre et ceux de novembre."""
    def jour(a: int, m: int, j: int) -> dict:
        return {
            "type": "arret_maladie" if date(a, m, j).weekday() < 5 else "weekend",
            "arret_type": "maladie_simple",
            "date_debut_arret_reel": "2026-10-19",
            "date_fin_arret_reel": "2026-11-13",
        }
    octobre = {j: jour(2026, 10, j) for j in range(19, 32)}
    novembre = {j: jour(2026, 11, j) for j in range(1, 14)}
    return novembre, {(2026, 10): octobre}


@pytest.mark.parametrize("profil", ("heures", "forfait_jours"))
def test_un_nouveau_contrat_ne_repaie_pas_les_jours_d_avant_son_entree(banc, profil):  # noqa: F811
    """Relecture A9 (18/11) : CDD jusqu'au 31/10, CDI au 01/11. Au forfait, la
    période de novembre commence le 26/10 ; le bulletin du nouveau contrat
    repayait IJ et maintien du 26 au 31/10, déjà payés par l'ancien."""
    novembre, voisins = _arret_a_cheval()
    donnees = banc.generer(
        profil,
        jours=novembre,
        jours_des_mois_voisins=voisins,
        mois=11,
        fiche_en_plus={"hire_date": "2026-11-01"},
    )

    # Carence du 19 au 21/10 (ancien contrat) ; indemnisés du 01 au 13/11 seulement.
    assert donnees["bloc_maintien"]["ijss"].get("nb_jours_indemnises") == 13
