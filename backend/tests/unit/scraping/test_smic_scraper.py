"""Tests unitaires SMIC (primary + Sonar)."""

from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from scraping.SMIC.SMIC import (
    applicable_segment_table_text,
    extract_smic_data,
)
from scraping.SMIC.SMIC_AI import _reference_core, extract_smic
from scraping.SMIC.spec import _equal, _extract_sig

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "scraping"
    / "smic"
    / "urssaf_multi_revision.html"
)


def test_extract_june_2026_rates():
    soup = BeautifulSoup(FIXTURES.read_text(encoding="utf-8"), "html.parser")
    data = extract_smic_data(soup, reference_date=date(2026, 6, 2))
    assert data["cas_general"] == 12.31
    assert data["jeune_17_ans"] == 11.08
    assert data["jeune_moins_17_ans"] == 9.85
    assert data["smic_mensuel_brut"] == 1867.02


def test_applicable_segment_table_text_mentions_youth_rates():
    soup = BeautifulSoup(FIXTURES.read_text(encoding="utf-8"), "html.parser")
    text = applicable_segment_table_text(soup, reference_date=date(2026, 6, 2))
    assert "12.31" in text or "12,31" in text
    assert "11.08" in text or "11,08" in text
    assert "9.85" in text or "9,85" in text


def test_extract_smic_consensus_mocked(monkeypatch):
    soup = BeautifulSoup(FIXTURES.read_text(encoding="utf-8"), "html.parser")
    reference = extract_smic_data(soup, reference_date=date(2026, 6, 2))
    ref_core = _reference_core(reference)

    monkeypatch.setattr("scraping.SMIC.SMIC_AI.smic_module.fetch_soup", lambda: soup)
    monkeypatch.setattr(
        "scraping.SMIC.SMIC_AI.smic_module.extract_smic_data",
        lambda _soup: reference,
    )
    monkeypatch.setattr(
        "scraping.SMIC.SMIC_AI.extract_structured_json",
        lambda **kw: {
            "cas_general": 12.31,
            "jeune_17_ans": 11.08,
            "jeune_moins_17_ans": 9.85,
            "smic_mensuel_brut": 1867.02,
        },
    )

    sections = extract_smic()
    assert sections is not None
    assert _equal(sections, ref_core)


def test_sonar_youth_confusion_would_fail_consensus():
    """Repro du bug : Sonar renvoie 9.85 / 8.62 au lieu de 11.08 / 9.85."""
    primary = {
        "cas_general": 12.31,
        "jeune_17_ans": 11.08,
        "jeune_moins_17_ans": 9.85,
        "smic_mensuel_brut": 1867.02,
        "smic_horaire_brut": 12.31,
    }
    sonar_wrong = {
        "cas_general": 12.31,
        "jeune_17_ans": 9.85,
        "jeune_moins_17_ans": 8.62,
        "smic_mensuel_brut": 1867.02,
        "smic_horaire_brut": 12.31,
    }
    assert not _equal(primary, sonar_wrong)


def test_payload_signatures_match_on_fixture():
    soup = BeautifulSoup(FIXTURES.read_text(encoding="utf-8"), "html.parser")
    data = extract_smic_data(soup, reference_date=date(2026, 6, 2))
    payload = {"sections": {k: v for k, v in data.items() if k != "source"}}
    sig = _extract_sig(payload)
    assert sig["cas_general"] == 12.31
    assert sig["jeune_17_ans"] == 11.08


# --- Mise à jour du barème : l'historique se garde (janvier 2027) -----------
#
# Avant le 12/10/2026, `_build` réécrivait le barème en entier, sans
# `historique` : un nouveau SMIC validé effaçait les paliers de 2026, et la
# réduction générale (qui lit le SMIC du 1er janvier dans l'historique) comme le
# SMIC d'un mois passé retombaient sur un repli.

_BAREME_2026 = {
    "annee": 2026,
    "historique": [
        {"date_debut": "2026-01-01", "cas_general": 12.02},
        {"date_debut": "2026-06-01", "cas_general": 12.31},
    ],
    "cas_general": 12.31,
    "jeune_17_ans": 11.08,
    "smic_horaire_brut": 12.31,
    "smic_mensuel_brut": 1867.02,
    "jeune_moins_17_ans": 9.85,
}


def _payload(cas_general, j17, jm17, mensuel, annee, effet):
    return {
        "sections": {
            "cas_general": cas_general,
            "smic_horaire_brut": cas_general,
            "jeune_17_ans": j17,
            "jeune_moins_17_ans": jm17,
            "smic_mensuel_brut": mensuel,
            "annee": annee,
            "effective_from": effet,
        }
    }


def test_un_nouveau_smic_garde_l_historique_et_ajoute_son_palier_date(monkeypatch):
    import copy

    from scraping.SMIC.spec import _build

    monkeypatch.setattr("core.year_utils.current_year", lambda: 2027)
    sig = _extract_sig(_payload(12.5, 11.25, 10.0, 1895.83, 2027, "2027-01-01"))
    courant = {"config_data": copy.deepcopy(_BAREME_2026)}

    nouveau = _build(sig, courant)

    assert nouveau["historique"] == [
        {"date_debut": "2026-01-01", "cas_general": 12.02},
        {"date_debut": "2026-06-01", "cas_general": 12.31},
        {"date_debut": "2027-01-01", "cas_general": 12.5},
    ]
    assert nouveau["annee"] == 2027
    assert nouveau["cas_general"] == 12.5
    assert "effective_from" not in nouveau
    # Le barème courant n'est pas modifié en place.
    assert courant["config_data"] == _BAREME_2026


def test_le_smic_de_reference_de_la_nouvelle_annee_est_pose_au_1er_janvier(monkeypatch):
    from app.modules.payroll.engine.calcul_reduction_generale import (
        smic_horaire_au_1er_janvier,
    )
    from scraping.SMIC.spec import _build

    monkeypatch.setattr("core.year_utils.current_year", lambda: 2027)
    sig = _extract_sig(_payload(12.5, 11.25, 10.0, 1895.83, 2027, "2027-01-01"))
    nouveau = _build(sig, {"config_data": dict(_BAREME_2026)})

    baremes = {"smic": nouveau}
    assert smic_horaire_au_1er_janvier(baremes, 2027) == 12.5
    assert smic_horaire_au_1er_janvier(baremes, 2026) == 12.02


def test_sans_date_d_effet_le_smic_d_une_annee_nouvelle_est_date_du_1er_janvier(monkeypatch):
    # La source IA peut ne pas rendre la date d'effet.
    from scraping.SMIC.spec import _build

    monkeypatch.setattr("core.year_utils.current_year", lambda: 2027)
    sig = _extract_sig(_payload(12.5, 11.25, 10.0, 1895.83, 2027, None))
    nouveau = _build(sig, {"config_data": dict(_BAREME_2026)})

    assert nouveau["historique"][-1] == {"date_debut": "2027-01-01", "cas_general": 12.5}


def test_un_smic_inchange_ne_modifie_pas_le_bareme(monkeypatch):
    # Sinon chaque relevé déposerait une revue humaine « à valider » pour rien.
    from scraping.SMIC.spec import _build

    monkeypatch.setattr("core.year_utils.current_year", lambda: 2026)
    sig = _extract_sig(_payload(12.31, 11.08, 9.85, 1867.02, 2026, "2026-06-01"))

    assert _build(sig, {"config_data": dict(_BAREME_2026)}) == _BAREME_2026


def test_un_premier_bareme_sans_historique_en_ouvre_un(monkeypatch):
    from scraping.SMIC.spec import _build

    monkeypatch.setattr("core.year_utils.current_year", lambda: 2026)
    sig = _extract_sig(_payload(12.31, 11.08, 9.85, 1867.02, 2026, "2026-06-01"))

    assert _build(sig, None)["historique"] == [
        {"date_debut": "2026-06-01", "cas_general": 12.31}
    ]
