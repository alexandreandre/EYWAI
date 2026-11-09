"""IJ de maladie : un mois de référence sans bulletin vaut le salaire de la fiche.

C'est une estimation, que le décompte de la caisse remplace. Elle pouvait finir
sur le bulletin sans que rien ne le dise.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.maintien_salaire_service import alerte_ij_mois_sans_bulletin

pytestmark = pytest.mark.unit


def test_dit_combien_de_mois_sont_estimes():
    assert alerte_ij_mois_sans_bulletin({"salaires_bruts_reference": [2000.0, None, None]}, 40.0) == (
        "IJSS estimées : 2 mois de référence sans bulletin, salaire de la fiche retenu. "
        "Reportez le décompte de la CPAM dans Suivi IJSS."
    )


def test_un_mois_au_singulier():
    assert "1 mois de référence" in alerte_ij_mois_sans_bulletin(
        {"salaires_bruts_reference": [2000.0, 2000.0]}, 40.0
    )


def test_trois_bulletins_rien_a_dire():
    assert alerte_ij_mois_sans_bulletin({"salaires_bruts_reference": [1.0, 2.0, 3.0]}, 40.0) is None


def test_aperçu_sans_bruts_fournis_rien_a_dire():
    assert alerte_ij_mois_sans_bulletin({}, 40.0) is None


def test_aucune_ij_rien_a_dire():
    assert alerte_ij_mois_sans_bulletin({"salaires_bruts_reference": [None, None, None]}, 0.0) is None


def _maintien_avec_mois_sans_bulletin(**arret_en_plus):
    from datetime import date
    from types import SimpleNamespace

    from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

    statut = "Non-Cadre"
    contexte = SimpleNamespace(
        salaire_base_mensuel=3000.0,
        statut_salarie=statut,
        baremes={
            "pss": {"annuel": 48000.0},
            "ij_plafonds": {
                "maladie": 51.0,
                "maternite_paternite": 95.22,
                "at_mp": 205.47,
                "at_mp_majoree": 274.0,
            },
        },
        contrat={"contrat": {"date_entree": "2021-01-15", "statut": statut}},
    )
    arret = {
        "arret_type": "maladie_simple",
        "date_debut": "2026-06-01",
        "date_fin": "2026-06-10",
        "subrogation_active": True,
        "nombre_enfants": 0,
        "salaire_periode_reelle": 0.0,
        "salaires_bruts_reference": [3000.0, 3000.0, None],
        **arret_en_plus,
    }
    return calculer_maintien(arret, contexte, {}, date(2026, 6, 1), date(2026, 6, 30))


def _alertes_ij_estimees(resultat: dict) -> list[str]:
    return [a for a in resultat["alertes"] if "IJSS estimées" in a]


def test_sans_montant_valide_l_estimation_reste_signalee():
    assert len(_alertes_ij_estimees(_maintien_avec_mois_sans_bulletin())) == 1


@pytest.mark.parametrize("montant", [448.0, 0.0])
def test_un_montant_valide_remplace_l_estimation_donc_plus_d_alerte(montant):
    assert _alertes_ij_estimees(_maintien_avec_mois_sans_bulletin(ijss_brut_override=montant)) == []
