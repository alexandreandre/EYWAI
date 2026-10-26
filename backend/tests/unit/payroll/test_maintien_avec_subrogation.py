"""Arrêt avec subrogation : le garanti moins les IJSS des seuls jours maintenus.

Avec subrogation, la CPAM verse à l'employeur les IJSS de tout l'arrêt, et le
bulletin les reverse au salarié (« IJSS subrogées »). Le maintien versé est le
garanti moins les IJSS des jours que l'employeur maintient et que la CPAM
indemnise, plancher à 0 (D1226-5) : la règle du chemin sans subrogation. Les
IJSS des jours que l'employeur ne maintient pas (carence employeur, J4 à J7 en
maintien légal) ne se déduisent jamais : le salarié les reçoit en plus du
garanti. Avant le 24/10/2026, le moteur retirait du garanti toutes les IJSS de
l'arrêt : le salarié ne touchait que le garanti, et une carence payée seule
n'était pas payée.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.payslip_run_heures import (
    _appliquer_maintien_arret_maladie,
    _extraire_arret_pour_maintien,
)
from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

from .helpers import build_test_contexte
from .test_maintien_sans_subrogation import (
    JUIN,
    PLASTURGIE,
    SEPTEMBRE,
    _arret,
    _contexte_plasturgie,
    _ctx,
    _jours_d_arret,
    _legal,
)

pytestmark = pytest.mark.unit


def _subroge(**extra):
    return _arret(subrogation_active=True, **extra)


def _juin(arret, **reglages):
    return calculer_maintien(arret, _ctx(), _legal(**reglages), *JUIN)


def _au_bulletin(resultat, contexte=None):
    """Ce que le bulletin pose : la ligne de maintien (brut) et les IJSS subrogées (net)."""
    lignes: list = []
    _csg, ijss, _modifie = _appliquer_maintien_arret_maladie(
        contexte or build_test_contexte(salaire_base=2500.0), resultat, lignes
    )
    maintien = sum(l["gain"] for l in lignes if l.get("is_maintien_employeur"))
    return round(maintien, 2), round(sum(i["montant"] for i in ijss), 2)


# --- Maintien légal : le garanti, plus les IJSS de la carence employeur -----


def test_maintien_legal_le_salarie_recoit_le_garanti_et_les_ijss_de_la_carence_employeur():
    """Arrêt du 05 au 20/06 : IJSS du 08 au 20 (13 j), maintien du 12 au 20 (9 j)."""
    r = _juin(_subroge())
    m = r["maintien"]
    assert r["subrogation_active"] is True
    assert r["ijss"]["ijss_theorique"] == 534.25
    assert m["maintien_cible"] == 665.68
    assert m["maintien_verse"] == 295.82  # 665,68 − 369,86 (du 12 au 20/06) ; et non 131,43
    assert m["complement_employeur"] == 295.82
    assert "ijss_deduites" not in m  # clés d'affichage du seul chemin sans subrogation

    maintien, ijss = _au_bulletin(r)
    assert (maintien, ijss) == (295.82, 534.25)
    # Le garanti des jours maintenus, plus les IJSS du 08 au 11/06 (carence employeur).
    assert round(maintien + ijss, 2) == round(665.68 + 164.39, 2) == 830.07


def test_montant_valide_du_suivi_ijss_sa_part_des_jours_maintenus_au_prorata():
    r = _juin(_subroge(ijss_brut_override=480.0))
    assert r["ijss"]["ijss_theorique"] == 480.0
    assert r["maintien"]["maintien_verse"] == 333.37  # 665,68 − 480 × 9/13 (332,31)
    assert "ijss_deduites" not in r["maintien"]
    assert _au_bulletin(r) == (333.37, 480.0)  # le relevé validé est reversé en entier


def test_plancher_a_zero_quand_les_ijss_des_jours_maintenus_depassent_le_garanti():
    r = _juin(_subroge(ijss_brut_override=5000.0))
    assert r["maintien"]["maintien_verse"] == 0  # et non −4 334,32
    assert r["maintien"]["complement_employeur"] == 0
    assert _au_bulletin(r) == (0, 5000.0)


# --- Sans carence : tous les jours indemnisés sont maintenus, rien ne change -


@pytest.mark.parametrize(
    "arret, reglages, cible, ijss, verse",
    [
        # Accident du travail : ni carence de la caisse, ni carence employeur.
        (_subroge(arret_type="accident_travail"), {}, 1183.43, 788.95, 394.48),
        # Maintien conventionnel à 100 % dès le premier jour.
        (
            _subroge(),
            {"maintain_100_percent": True, "remove_employer_waiting": True,
             "employer_waiting_days": 0},
            1314.92, 534.25, 780.67,
        ),
    ],
    ids=["accident_du_travail", "conventionnel_100_des_j1"],
)
def test_sans_carence_employeur_le_resultat_ne_change_pas(arret, reglages, cible, ijss, verse):
    r = _juin(arret, **reglages)
    m = r["maintien"]
    assert r["ijss"]["ijss_theorique"] == ijss
    assert m["maintien_cible"] == cible
    assert m["maintien_verse"] == verse == round(cible - ijss, 2)  # le calcul d'avant


# --- Carence payée seule : la carence est payée, les IJSS reversées ----------


def test_carence_payee_seule_en_jours_calendaires_les_ijss_sont_toutes_reversees():
    """Les trois jours payés sont ceux de la carence de la caisse : sans IJSS, rien à déduire."""
    reglages = {k: v for k, v in PLASTURGIE.items() if k != "maintain_working_days"}
    reglages["subrogation_mode"] = "when_maintien"
    contexte = _contexte_plasturgie()
    arret = _extraire_arret_pour_maintien(
        _jours_d_arret(("2026-09-01", "2026-09-30")), contexte, *SEPTEMBRE
    )
    arret["arrets_annee"] = [{"debut": "2026-09-01", "fin": "2026-09-30", "type": "maladie_simple"}]
    r = calculer_maintien(arret, contexte, reglages, *SEPTEMBRE)
    assert r["subrogation_active"] is True
    assert r["maintien_base_ouvree"] is False
    assert r["ijss"]["ijss_theorique"] == pytest.approx(871.69, abs=0.01)
    assert r["maintien"]["maintien_cible"] == pytest.approx(193.69, abs=0.01)
    assert r["maintien"]["maintien_verse"] == pytest.approx(193.69, abs=0.01)  # et non −678,00
    assert _au_bulletin(r, contexte) == (pytest.approx(193.69, abs=0.01), 871.69)


# --- Deux arrêts dans le mois ----------------------------------------------


def _deux_arrets(override=None):
    """Du 02 au 13/06 (IJSS 9 j, 5 maintenus) et du 16 au 30/06 (IJSS 12 j, 8 maintenus)."""
    premier = _subroge(date_debut="2025-06-02", date_fin="2025-06-13")
    second = _subroge(date_debut="2025-06-16", date_fin="2025-06-30")
    arret = {**premier, "arrets_du_mois": [premier, second]}
    if override is not None:
        arret["ijss_brut_override"] = override
    return calculer_maintien(arret, _ctx(), _legal(), *JUIN)


def test_deux_arrets_chacun_deduit_les_ijss_de_ses_jours_maintenus():
    r = _deux_arrets()
    assert [a["maintien_verse"] for a in r["arrets_du_mois"]] == [164.34, 262.95]
    assert r["maintien"]["maintien_verse"] == 427.29
    assert r["ijss"]["ijss_theorique"] == 863.01  # 369,86 + 493,15, toutes reversées


def test_deux_arrets_le_releve_valide_se_repartit_sur_le_mois():
    """600 € validés pour 21 jours indemnisés, dont 13 maintenus : 371,43 € déduits."""
    r = _deux_arrets(override=600.0)
    assert r["ijss"]["ijss_theorique"] == 600.0
    cible = r["maintien"]["maintien_cible"]
    assert cible == 961.54
    assert r["maintien"]["maintien_verse"] == pytest.approx(cible - 371.43, abs=0.02)
    assert [a["maintien_verse"] for a in r["arrets_du_mois"]] == [226.96, 363.15]


# --- Jours ouvrés : IJSS subrogées au bulletin, sauf reconstitution Cegid ----
# Défaut du 24/10 : en jours ouvrés, le bulletin laissait les IJSS hors du net
# même avec une vraie subrogation, quand la CPAM les verse à l'employeur. Le
# salarié ne touchait que le complément. Seule la reconstitution d'un bulletin
# Cegid (saisie « IJSS override » : le montant est la retenue relevée sur ce
# bulletin, sans IJSS au net) les garde hors bulletin.

LEGAL_OUVRES_SUBROGE = {
    **PLASTURGIE,
    "subrogation_mode": "when_maintien",
    "apply_legal_maintenance": True,
    "paid_waiting_days_per_year": None,
    "employer_waiting_days": 7,
}


def _septembre_ouvres(**extra):
    """Arrêt du 07 au 18/09 : IJSS du 10 au 18 (9 j), maintien du 14 au 18 (5 jours ouvrés)."""
    contexte = _contexte_plasturgie()
    arret = _extraire_arret_pour_maintien(
        _jours_d_arret(("2026-09-07", "2026-09-18")), contexte, *SEPTEMBRE
    )
    arret.update(extra)
    return calculer_maintien(arret, contexte, dict(LEGAL_OUVRES_SUBROGE), *SEPTEMBRE), contexte


def test_reconstitution_cegid_la_retenue_saisie_se_deduit_en_entier():
    """Saisie « IJSS override » (backtest Mont Blanc) : jours ouvrés, IJSS hors bulletin.

    Le montant saisi est la retenue relevée sur le bulletin Cegid (absence à
    100 % moins maintien), calibrée pour que le maintien versé soit celui de ce
    bulletin : le garanti moins le montant saisi, au centime. Ce n'est pas un
    relevé de la caisse, il ne se répartit pas sur les jours maintenus.
    """
    r, contexte = _septembre_ouvres(
        ijss_brut_override=200.0, maintien_base_ouvree=True, ijss_releve_du_bulletin=True
    )
    m = r["maintien"]
    assert r["subrogation_active"] is True
    assert r["maintien_base_ouvree"] is True
    assert r["ijss"]["ijss_theorique"] == 200.0
    assert m["maintien_cible"] == 466.16
    assert m["maintien_verse"] == 266.16  # 466,16 − 200, et non 466,16 − 200 × 5/9
    assert _au_bulletin(r, contexte) == (266.16, 0)  # IJSS hors bulletin


def test_jours_ouvres_ijss_estimees_seules_celles_des_jours_maintenus_sont_deduites():
    r, contexte = _septembre_ouvres()
    m = r["maintien"]
    assert r["subrogation_active"] is True
    assert r["maintien_base_ouvree"] is True
    assert r["ijss"]["ijss_theorique"] == 290.56
    assert m["maintien_cible"] == 466.16
    assert m["maintien_verse"] == 304.74  # 466,16 − 161,42 (du 14 au 18/09) ; et non 175,60
    # Subrogation : la CPAM verse les IJSS à l'employeur, qui les reverse.
    assert _au_bulletin(r, contexte) == (304.74, 290.56)
    # Le garanti des jours maintenus, plus les IJSS du 10 au 13/09 (carence employeur).
    assert round(304.74 + 290.56, 2) == round(466.16 + 290.56 - 161.42, 2)


def test_jours_ouvres_par_le_reglage_de_la_societe_les_ijss_subrogees_sont_reversees():
    # Le mode vient du réglage « maintien en jours ouvrés », pas des jours d'arrêt.
    contexte = _contexte_plasturgie()
    arret = _extraire_arret_pour_maintien(
        _jours_d_arret(("2026-09-07", "2026-09-18")), contexte, *SEPTEMBRE
    )
    arret.pop("maintien_base_ouvree", None)
    reglages = {**LEGAL_OUVRES_SUBROGE, "maintain_working_days": True}
    r = calculer_maintien(arret, contexte, reglages, *SEPTEMBRE)
    assert r["maintien_base_ouvree"] is True and r["subrogation_active"] is True
    assert _au_bulletin(r, contexte) == (304.74, 290.56)


def test_sans_subrogation_en_jours_ouvres_les_ijss_restent_hors_bulletin():
    r, contexte = _septembre_ouvres(subrogation_active=False)
    assert r["subrogation_active"] is False
    assert _au_bulletin(r, contexte)[1] == 0


def test_jours_ouvres_montant_valide_du_suivi_ijss_au_prorata_et_reverse():
    # Un montant validé au suivi IJSS est un relevé de la caisse, pas la retenue
    # d'un bulletin Cegid : sa part des jours maintenus (5 sur 9, au prorata
    # des IJSS estimées) se déduit, et il est reversé au bulletin.
    r, contexte = _septembre_ouvres(ijss_brut_override=200.0)
    assert r["maintien"]["maintien_verse"] == round(466.16 - 200.0 * 161.42 / 290.56, 2)
    assert _au_bulletin(r, contexte) == (r["maintien"]["maintien_verse"], 200.0)


def test_la_chaine_marque_la_reconstitution_cegid_depuis_la_saisie():
    import inspect

    from app.modules.payroll.documents import payslip_run_forfait, payslip_run_heures

    for module in (payslip_run_heures, payslip_run_forfait):
        source = inspect.getsource(module)
        assert 'arret_data["ijss_releve_du_bulletin"] = True' in source
