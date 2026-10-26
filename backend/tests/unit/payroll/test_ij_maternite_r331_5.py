"""IJ estimées d'un congé de maternité, de paternité ou d'adoption (CSS R331-5).

Le texte (Légifrance, LEGIARTI000054167779, même calcul depuis le 14/04/2021,
LEGIARTI000043356709) : l'indemnité se détermine selon R323-4 et R323-8, les
trois derniers salaires ÷ 91,25, chaque paie retenue « dans la limite du
plafond mentionné à l'article L. 241-3 en vigueur le dernier jour du mois
civil précédant celui de l'interruption de travail » ; « ce salaire est
diminué par application d'un taux forfaitaire représentatif de la part
salariale des cotisations », fixé à 21 % par l'arrêté du 28 mars 2013.
Service-public F2265 (vérifié le 01/06/2026) : plafond 4 005 € par mois en
2026, taux de 21 %, IJ de 104,02 € par jour au plus.

Le moteur prenait le salaire de base ÷ 30,42, plafonné à 1,8 plafond
journalier, sans le taux forfaitaire.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

pytestmark = pytest.mark.unit

SEPTEMBRE = (date(2026, 9, 1), date(2026, 9, 30))
REGLAGES = {"apply_legal_maintenance": True, "maintain_parental_leave": False, "subrogation_mode": "never"}


def _ctx(salaire_base: float = 2500.0) -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=salaire_base,
        statut_salarie="Non-Cadre",
        baremes={
            "pss": {"annuel": 48060.0, "mensuel": 4005.0},
            "ij_plafonds": {"maladie": 42.97, "maternite_paternite": 104.02,
                            "at_mp": 240.49, "at_mp_majoree": 320.66},
        },
        contrat={"contrat": {"date_entree": "2021-08-01", "statut": "Non-Cadre"}},
    )


def _ijss(salaires=None, arret_type="maternite", salaire_base=2500.0):
    arret = {
        "arret_type": arret_type, "date_debut": "2026-09-01", "date_fin": "2026-09-30",
        "subrogation_active": False, "nombre_enfants": 0, "salaire_periode_reelle": 0.0,
    }
    if salaires is not None:
        arret["salaires_bruts_reference"] = salaires
    return calculer_maintien(arret, _ctx(salaire_base), dict(REGLAGES), *SEPTEMBRE)["ijss"]


def test_trois_derniers_bruts_divises_par_91_25_moins_21_pour_cent():
    ijss = _ijss([2600.0, 2700.0, 2800.0])
    # (2 600 + 2 700 + 2 800) ÷ 91,25 = 88,7671 ; × 0,79 = 70,1260 par jour.
    assert ijss["salaire_journalier_base"] == pytest.approx(88.7671, abs=1e-4)
    assert ijss["ijss_journaliere"] == pytest.approx(70.1260, abs=1e-4)
    assert ijss["nb_jours_indemnises"] == 30
    assert ijss["ijss_theorique"] == round(8100.0 / 91.25 * 0.79 * 30, 2)


def test_chaque_paie_retenue_dans_la_limite_du_plafond_mensuel():
    # Une paie de 6 000 € compte pour 4 005 € : elle ne compense pas les autres.
    ijss = _ijss([2600.0, 2700.0, 6000.0])
    assert ijss["ijss_journaliere"] == pytest.approx((2600 + 2700 + 4005) / 91.25 * 0.79, abs=1e-4)


def test_au_dessus_du_plafond_l_ij_vaut_le_maximum_de_2026():
    ijss = _ijss([6000.0, 6000.0, 6000.0])
    assert round(ijss["ijss_journaliere"], 2) == 104.02  # 3 × 4 005 ÷ 91,25 × 0,79


def test_un_mois_sans_bulletin_compte_le_salaire_de_base():
    ijss = _ijss([None, 2700.0, 2800.0], salaire_base=2500.0)
    assert ijss["ijss_journaliere"] == pytest.approx(8000.0 / 91.25 * 0.79, abs=1e-4)


def test_la_paternite_suit_le_meme_calcul():
    assert _ijss([2600.0, 2700.0, 2800.0], arret_type="paternite")["ijss_journaliere"] == (
        pytest.approx(8100.0 / 91.25 * 0.79, abs=1e-4)
    )


def _ijss_du(debut, fin, salaires, salaire_base=2500.0, **extra):
    arret = {
        "arret_type": "maternite", "date_debut": debut, "date_fin": fin,
        "subrogation_active": False, "nombre_enfants": 0, "salaire_periode_reelle": 0.0,
        "salaires_bruts_reference": salaires, **extra,
    }
    periode = (date.fromisoformat(debut).replace(day=1), date.fromisoformat(fin))
    return calculer_maintien(arret, _ctx(salaire_base), dict(REGLAGES), *periode)["ijss"]


def test_le_plafond_est_celui_du_dernier_jour_du_mois_qui_precede_l_arret():
    # Congé du 05/01/2026 : plafond en vigueur le 31/12/2025, 3 925 € (F2265),
    # et non celui des barèmes de 2026. 3 × 3 925 ÷ 91,25 × 0,79 = 101,94.
    ijss = _ijss_du("2026-01-05", "2026-01-31", [5000.0, 5000.0, 5000.0])
    assert round(ijss["ijss_journaliere"], 2) == 101.94


def test_l_ij_ne_descend_pas_sous_le_minimum_de_2026():
    # 3 × 300 ÷ 91,25 × 0,79 = 7,79 : le minimum de 11,12 € s'applique (F2265).
    ijss = _ijss_du("2026-09-01", "2026-09-30", [300.0, 300.0, 300.0], salaire_base=300.0)
    assert round(ijss["ijss_journaliere"], 2) == 11.12


def test_le_detail_dit_le_taux_forfaitaire_retire():
    # Le pliant relie le salaire journalier à l'indemnité : 88,77 € moins 21 %,
    # soit 70,13 € par jour. Sans ce taux, 100 % × 88,77 ne redonnait pas l'IJ.
    ijss = _ijss([2600.0, 2700.0, 2800.0])
    assert ijss["taux_forfaitaire_retire"] == 0.21
    assert ijss["base_plafonnee"] == pytest.approx(70.1260, abs=1e-4)


def test_une_maladie_ne_retire_aucun_taux_forfaitaire():
    ijss = _ijss([2600.0, 2700.0, 2800.0], arret_type="maladie_simple")
    assert ijss["taux_forfaitaire_retire"] == 0.0
