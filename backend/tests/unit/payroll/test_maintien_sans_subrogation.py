"""Arrêt sans subrogation : déduire du maintien les IJSS des jours maintenus, ou non.

Sans subrogation, la CPAM verse les IJSS au salarié. Réglage à true : Martine
ne verse que le complément « sous déduction des IJSS » (D1226-5), et seulement
celles des jours que l'employeur maintient et que la CPAM indemnise. Les IJSS
de la carence employeur (J4 à J7) restent au salarié ; sur des jours de carence
payés, la CPAM ne verse rien. Réglage à false ou absent : le salaire garanti en
entier, le calcul d'avant (conception du 23/10/2026).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.documents.payslip_run_heures import _extraire_arret_pour_maintien
from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

CLE = "deduire_ijss_sans_subrogation"
JUIN = (date(2025, 6, 1), date(2025, 6, 30))
SEPTEMBRE = (date(2026, 9, 1), date(2026, 9, 30))
ALERTE = "IJSS versées directement au salarié"


def _ctx():
    return SimpleNamespace(
        salaire_base_mensuel=2500.0,
        baremes={"pss": {"annuel": 48000.0}},
        contrat={"contrat": {"date_entree": "2021-01-15"}},
    )


def _legal(**extra):
    return {
        "apply_legal_maintenance": True,
        "min_seniority_months": 12,
        "employer_waiting_days": 7,
        "seniority_extension_enabled": False,
        "remove_employer_waiting": False,
        "annual_unique_waiting": False,
        "maintain_100_percent": False,
        "differentiated_at_illness": False,
        "maintain_by_category": False,
        "no_seniority_condition": False,
        "custom_duration_days": None,
        "provident_relay_days": None,
        **extra,
    }


def _arret(**extra):
    return {
        "arret_type": "maladie_simple",
        "date_debut": "2025-06-05",
        "date_fin": "2025-06-20",
        "subrogation_active": False,
        "nombre_enfants": 0,
        "salaire_periode_reelle": 0.0,
        **extra,
    }


def _juin(arret=None, **reglages):
    return calculer_maintien(arret or _arret(), _ctx(), _legal(**reglages), *JUIN)


# --- Réglage éteint ou absent : rien ne change ------------------------------


def test_reglage_eteint_ou_absent_le_garanti_est_verse_en_entier():
    for reglages in ({}, {CLE: False}):
        r = _juin(**reglages)
        assert r["maintien"]["maintien_cible"] == 665.68
        assert r["maintien"]["maintien_verse"] == 665.68
        assert "ijss_deduites" not in r["maintien"]
        assert ALERTE in r["alertes"]


def test_reglage_eteint_le_resultat_est_identique_cle_pour_cle():
    assert _juin() == _juin(**{CLE: False})


def test_avec_subrogation_le_reglage_ne_change_rien():
    subroge = _arret(subrogation_active=True)
    assert _juin(subroge, **{CLE: True}) == _juin(subroge)


# --- Réglage allumé : les IJSS des seuls jours maintenus --------------------


def test_maintien_legal_seules_les_ijss_des_jours_maintenus_sont_deduites():
    r = _juin(**{CLE: True})
    m = r["maintien"]
    assert r["ijss"]["ijss_theorique"] == 534.25  # 13 jours, du 08 au 20/06
    assert m["maintien_cible"] == 665.68
    assert m["ijss_deduites"] == 369.86  # 9 jours maintenus, du 12 au 20/06
    assert m["ijss_deduites_source"] == "estimees"
    assert m["maintien_verse"] == 295.82  # et non 131,43
    assert m["complement_employeur"] == 295.82
    assert (
        "IJSS versées directement au salarié : 369,86 € déduites du maintien "
        "(estimées par Martine)"
    ) in r["alertes"]
    assert ALERTE not in r["alertes"]


def test_montant_valide_sa_part_des_jours_maintenus_au_prorata():
    r = _juin(_arret(ijss_brut_override=480.0), **{CLE: True})
    m = r["maintien"]
    assert r["ijss"]["ijss_theorique"] == 480.0
    assert m["ijss_deduites"] == 332.31  # 480 × 9/13
    assert m["ijss_deduites_source"] == "validees"
    assert m["maintien_verse"] == 333.37
    assert any("(montant validé dans le suivi IJSS)" in a for a in r["alertes"])


def test_plancher_a_zero_quand_les_ijss_depassent_le_garanti():
    m = _juin(_arret(ijss_brut_override=5000.0), **{CLE: True})["maintien"]
    assert m["maintien_verse"] == 0
    assert m["ijss_deduites"] == 665.68
    assert m["complement_employeur"] == 0


def test_un_arret_tout_dans_la_carence_employeur_n_a_rien_a_deduire():
    r = _juin(_arret(date_fin="2025-06-10"), **{CLE: True})
    assert r["ijss"]["ijss_theorique"] > 0  # du 08 au 10/06, au salarié
    assert r["maintien"]["maintien_verse"] == 0
    assert "ijss_deduites" not in r["maintien"]


# --- Plasturgie : jours ouvrés, « Jamais », carence payée (cas Colorplast) ---

PLASTURGIE = {
    "apply_legal_maintenance": False,
    "min_seniority_months": 10,
    "employer_waiting_days": 3,
    "subrogation_mode": "never",
    "paid_waiting_days_per_year": 3,
    "paid_waiting_min_seniority_months": 12,
    "maintain_working_days": True,
}


def _contexte_plasturgie():
    return build_test_contexte(
        salaire_base=1963.99, duree_hebdo=39.0, date_entree="2021-09-13",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )


def _jours_d_arret(*arrets):
    jours = []
    for debut, fin in arrets:
        d = date.fromisoformat(debut)
        while d <= date.fromisoformat(fin):
            jours.append({
                "date_complete": d.isoformat(),
                "type": "weekend" if d.weekday() >= 5 else "arret_maladie",
                "arret_type": "maladie_simple",
                "date_debut_arret_reel": debut,
                "date_fin_arret_reel": fin,
            })
            d = date.fromordinal(d.toordinal() + 1)
    return jours


def _septembre(reglages, debut="2026-09-07", fin="2026-09-18"):
    contexte = _contexte_plasturgie()
    arret = _extraire_arret_pour_maintien(_jours_d_arret((debut, fin)), contexte, *SEPTEMBRE)
    arret["arrets_annee"] = [{"debut": debut, "fin": fin, "type": "maladie_simple"}]
    arret["arrets_connus"] = list(arret["arrets_annee"])
    return calculer_maintien(arret, contexte, dict(reglages), *SEPTEMBRE)


def test_carence_payee_seule_rien_n_est_deduit():
    for debut, fin in (("2026-09-07", "2026-09-18"), ("2026-09-01", "2026-09-30")):
        r = _septembre({**PLASTURGIE, CLE: True}, debut, fin)
        assert r["ijss"]["ijss_theorique"] > 0
        assert r["maintien"]["maintien_verse"] == pytest.approx(310.78, abs=0.01)
        assert "ijss_deduites" not in r["maintien"]
        assert r == _septembre(PLASTURGIE, debut, fin)


def test_jours_ouvres_jamais_avec_maintien_legal_les_week_ends_comptent():
    """Maintien légal dès J4 : du 10 au 18/09, week-end des 12 et 13 compris."""
    r = _septembre({**PLASTURGIE, "apply_legal_maintenance": True, CLE: True})
    m = r["maintien"]
    assert r["subrogation_active"] is False
    assert r["ijss"]["nb_jours_indemnises"] == 9
    assert m["ijss_deduites"] == r["ijss"]["ijss_theorique"]
    eteint = _septembre({**PLASTURGIE, "apply_legal_maintenance": True})["maintien"]
    assert m["maintien_cible"] == eteint["maintien_cible"]
    assert m["maintien_verse"] == pytest.approx(
        eteint["maintien_verse"] - r["ijss"]["ijss_theorique"], abs=0.01
    )


def test_caracterisation_avec_subrogation_carence_payee_seule():
    """Hors champ (conception § 6) : ce que fait AUJOURD'HUI le chemin subrogé.

    La subrogation retire toutes les IJSS de l'arrêt du maintien, sans plancher :
    sur la seule carence payée, le versé devient négatif, la ligne de maintien
    n'est pas posée et les 310,78 € de carence ne sont pas payés. Le réglage n'y
    change rien. Test de caractérisation : à revoir avec Alexandre, pas un
    comportement voulu.
    """
    subroge = {**PLASTURGIE, "subrogation_mode": "when_maintien"}
    for reglages in (subroge, {**subroge, CLE: True}):
        r = _septembre(reglages, "2026-09-01", "2026-09-30")
        assert r["subrogation_active"] is True
        assert r["maintien"]["maintien_cible"] == pytest.approx(310.78, abs=0.01)
        assert r["ijss"]["ijss_theorique"] == pytest.approx(871.69, abs=0.01)
        assert r["maintien"]["maintien_verse"] == pytest.approx(-560.91, abs=0.01)


# --- Congés de parentalité maintenus ----------------------------------------


def _ctx_parental():
    return SimpleNamespace(
        salaire_base_mensuel=4000.0,
        statut_salarie="Non-Cadre",
        baremes={
            "pss": {"annuel": 48060.0},
            "ij_plafonds": {"maladie": 42.97, "maternite_paternite": 104.02,
                            "at_mp": 240.49, "at_mp_majoree": 320.66},
        },
        contrat={"contrat": {"date_entree": "2021-08-01", "statut": "Non-Cadre"}},
    )


def test_conge_parental_maintenu_les_ij_de_tout_le_conge_sont_deduites():
    arret = {
        "arret_type": "maternite", "date_debut": "2026-09-07", "date_fin": "2026-09-30",
        "subrogation_active": False, "nombre_enfants": 0, "salaire_periode_reelle": 0.0,
    }
    reglages = _legal(maintain_parental_leave=True)
    allume = calculer_maintien(arret, _ctx_parental(), {**reglages, CLE: True}, *SEPTEMBRE)
    eteint = calculer_maintien(arret, _ctx_parental(), reglages, *SEPTEMBRE)
    ij = allume["ijss"]["ijss_theorique"]
    assert 0 < ij < eteint["maintien"]["maintien_verse"]
    assert allume["maintien"]["ijss_deduites"] == ij
    assert allume["maintien"]["maintien_verse"] == pytest.approx(
        eteint["maintien"]["maintien_verse"] - ij, abs=0.01
    )


# --- Deux arrêts dans le mois -----------------------------------------------

LEGAL_OUVRES = {**PLASTURGIE, "apply_legal_maintenance": True, "paid_waiting_days_per_year": None}


def _deux_arrets(reglages, override=None):
    contexte = _contexte_plasturgie()
    jours = _jours_d_arret(("2026-09-01", "2026-09-11"), ("2026-09-21", "2026-09-30"))
    arret = _extraire_arret_pour_maintien(jours, contexte, *SEPTEMBRE)
    if override is not None:
        arret["ijss_brut_override"] = override
    return calculer_maintien(arret, contexte, dict(reglages), *SEPTEMBRE)


def test_deux_arrets_les_deductions_s_additionnent():
    r = _deux_arrets({**LEGAL_OUVRES, CLE: True})
    m = r["maintien"]
    assert len(r["arrets_du_mois"]) == 2
    assert m["ijss_deduites"] > 0
    assert m["ijss_deduites_source"] == "estimees"
    eteint = _deux_arrets(LEGAL_OUVRES)["maintien"]
    assert m["maintien_verse"] == pytest.approx(
        eteint["maintien_verse"] - m["ijss_deduites"], abs=0.01
    )
    assert len([a for a in r["alertes"] if a.startswith(ALERTE)]) == 1


def test_deux_arrets_le_releve_valide_se_repartit_sur_le_mois():
    estime = _deux_arrets({**LEGAL_OUVRES, CLE: True})
    part = estime["maintien"]["ijss_deduites"] / estime["ijss"]["ijss_theorique"]
    r = _deux_arrets({**LEGAL_OUVRES, CLE: True}, override=600.0)
    assert r["ijss"]["ijss_theorique"] == 600.0
    assert r["maintien"]["ijss_deduites_source"] == "validees"
    assert r["maintien"]["ijss_deduites"] == pytest.approx(600.0 * part, abs=0.02)


def test_deux_arrets_reglage_eteint_identique_au_calcul_d_aujourd_hui():
    assert _deux_arrets({**LEGAL_OUVRES, CLE: False}, override=600.0) == _deux_arrets(
        LEGAL_OUVRES, override=600.0
    )
    assert "ijss_deduites" not in _deux_arrets(LEGAL_OUVRES)["maintien"]
