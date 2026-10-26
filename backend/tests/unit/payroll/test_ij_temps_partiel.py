"""IJ estimées d'un salarié à temps partiel : la quotité ne s'applique pas deux fois.

Le salaire journalier de base se calcule sur les paies réelles, déjà au temps
partiel : CSS R323-4, 1° (Légifrance LEGIARTI000051226486) : « 1/91,25 du
montant des trois dernières paies des mois civils antérieurs à la date de
l'interruption de travail » ; R331-5 y renvoie pour la maternité ; R433-4
retient la dernière paie pour l'accident du travail. Aucun de ces textes ne
réduit encore l'indemnité de la quotité de temps partiel. Le moteur la
multipliait pourtant par la quotité : une salariée à 21 h (quotité 0,6)
recevait 60 % de l'IJ que ses paies lui donnent. Le mi-temps thérapeutique
garde sa règle.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

pytestmark = pytest.mark.unit

SEPTEMBRE = (date(2026, 9, 1), date(2026, 9, 30))
SMIC_2026 = {"cas_general": 12.31, "historique": [{"date_debut": "2026-06-01", "cas_general": 12.31}]}


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=1500.0,
        statut_salarie="Non-Cadre",
        baremes={
            "pss": {"annuel": 48060.0, "mensuel": 4005.0},
            "smic": SMIC_2026,
            "ij_plafonds": {"maladie": 42.97, "maternite_paternite": 104.02,
                            "at_mp": 240.49, "at_mp_majoree": 320.66},
        },
        contrat={"contrat": {"date_entree": "2021-08-01", "statut": "Non-Cadre",
                             "temps_travail": {"is_temps_partiel": True, "quotite": 0.6}}},
    )


def _ij(arret_type: str, temps_partiel: bool = True) -> float:
    arret = {
        "arret_type": arret_type, "date_debut": "2026-09-01", "date_fin": "2026-09-30",
        "subrogation_active": False, "nombre_enfants": 0, "salaire_periode_reelle": 0.0,
        "salaires_bruts_reference": [1500.0, 1500.0, 1500.0],
        "is_temps_partiel": temps_partiel, "quotite_temps_partiel": 0.6,
    }
    reglages = {"apply_legal_maintenance": True, "subrogation_mode": "never"}
    ijss = calculer_maintien(arret, _ctx(), reglages, *SEPTEMBRE)["ijss"]
    return round(ijss["ijss_journaliere"], 4)


def test_maladie_les_trois_paies_a_temps_partiel_sans_quotite_en_plus():
    # 3 × 1 500 ÷ 91,25 × 50 % = 24,6575 par jour, et non × 0,6 (14,7945).
    assert _ij("maladie_simple") == pytest.approx(4500.0 / 91.25 * 0.5, abs=1e-4)
    assert _ij("maladie_simple") == _ij("maladie_simple", temps_partiel=False)


def test_accident_du_travail_sans_quotite_en_plus():
    assert _ij("accident_travail") == _ij("accident_travail", temps_partiel=False)


def test_maternite_sans_quotite_en_plus():
    assert _ij("maternite") == pytest.approx(4500.0 / 91.25 * 0.79, abs=1e-4)


def test_le_mi_temps_therapeutique_garde_sa_quotite():
    assert _ij("mi_temps_therapeutique") == pytest.approx(
        _ij("mi_temps_therapeutique", temps_partiel=False) * 0.6, abs=1e-4
    )
