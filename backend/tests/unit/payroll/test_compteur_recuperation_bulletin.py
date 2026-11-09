"""Le bulletin imprime le compteur de récupération, comme Quadra : heures
acquises, heures prises avec leur date, solde ; dès 7 h, la mention des deux
mois (C. trav. D3171-11). Spec 2026-11-05-heures-de-recuperation.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.bulletin_view import construire_compteurs

pytestmark = pytest.mark.unit


def _bulletin(recup: dict | None) -> dict:
    solde = {
        "date_reference": "31/07/2026",
        "conges_payes": {"acquis": 2.08, "pris": 0.0, "solde": 2.08},
    }
    if recup is not None:
        solde["recuperation"] = recup
    return {"pied_de_page": {"solde_conges": solde}}


def test_sans_compteur_de_recuperation_rien_ne_change():
    compteurs = construire_compteurs(_bulletin(None))
    assert [c["titre"] for c in compteurs["colonnes"]] == ["CP N"]
    assert compteurs["notes"] == []


def test_colonne_recuperation_et_heures_prises_avec_leur_date():
    compteurs = construire_compteurs(
        _bulletin(
            {
                "acquis": 9.0,
                "pris": 7.0,
                "paye": 0.0,
                "solde": 2.0,
                "acquis_annee": 12.5,
                "pris_annee": 7.0,
                "prises": [{"date": "2026-07-13", "heures": 7.0}],
            }
        )
    )
    # Le tableau se lit en cumul (comme les congés) ; le détail du mois en note.
    colonne = compteurs["colonnes"][-1]
    assert colonne == {"titre": "Récup. (h)", "acquis": 12.5, "pris": 7.0, "solde": 2.0}
    assert "Récupération ce mois-ci : 9 h acquises, 7 h prises le 13/07" in compteurs["notes"]
    assert not any("deux mois" in n for n in compteurs["notes"])


def test_un_solde_nul_sans_mouvement_s_imprime_quand_meme():
    # Le réglage est actif : un compteur à zéro se montre (jamais d'état muet).
    compteurs = construire_compteurs(
        _bulletin({"acquis": 0.0, "pris": 0.0, "paye": 0.0, "solde": 0.0, "prises": []})
    )
    assert compteurs["colonnes"][-1]["titre"] == "Récup. (h)"


def test_mention_des_deux_mois_des_sept_heures():
    compteurs = construire_compteurs(
        _bulletin(
            {
                "acquis": 8.75,
                "pris": 0.0,
                "paye": 0.0,
                "solde": 10.5,
                "prises": [],
            }
        )
    )
    assert (
        "Droit à repos ouvert : 10,5 h de récupération à prendre dans un délai "
        "maximum de deux mois (C. trav. D3171-11)."
    ) in compteurs["notes"]


def test_heures_payees_dites_en_note():
    compteurs = construire_compteurs(
        _bulletin({"acquis": 0.0, "pris": 0.0, "paye": 2.0, "solde": 0.0, "prises": []})
    )
    assert "Récupération ce mois-ci : 2 h payées" in compteurs["notes"]


def test_au_depart_un_solde_de_recuperation_se_signale():
    from app.modules.payroll.engine.bulletin import alertes_des_compteurs_de_conges

    solde = {"recuperation": {"solde": 2.0, "paye": 0.0}}
    alertes = alertes_des_compteurs_de_conges(solde, bulletin_de_sortie=True)
    codes = {a["code"]: a for a in alertes}
    assert "recuperation_non_prise_au_depart" in codes
    assert "2 h" in codes["recuperation_non_prise_au_depart"]["message"]
    # Hors départ, ou solde payé : rien.
    assert alertes_des_compteurs_de_conges(solde, bulletin_de_sortie=False) == []
    assert alertes_des_compteurs_de_conges(
        {"recuperation": {"solde": 0.0, "paye": 2.0}}, bulletin_de_sortie=True
    ) == []


def test_heures_sup_saisies_a_la_main():
    from app.modules.payroll.documents.payslip_run_heures import heures_sup_saisies

    assert heures_sup_saisies({}) is None
    assert heures_sup_saisies({"heures_supplementaires_conjoncturelles": 8}) == (8.0, 0.0)
    assert heures_sup_saisies({"heures_supplementaires_conjoncturelles_50": 2}) == (0.0, 2.0)
    # Déclarées nulles depuis le bulletin : elles font foi quand même.
    assert heures_sup_saisies({"heures_sup_declarees_au_bulletin": True}) == (0.0, 0.0)


def _bulletin_avec_convention(convention: str, solde_extra: dict) -> dict:
    bulletin = _bulletin({"acquis": 8.0, "pris": 0.0, "paye": 0.0, "solde": 8.0, "prises": []})
    bulletin["pied_de_page"]["solde_conges"].update(solde_extra)
    bulletin["en_tete"] = {"salarie": {"convention_collective": convention}}
    return bulletin


def test_plasturgie_delai_de_deux_a_six_mois_pour_la_recuperation():
    """R-351 : fiche CDTN 292, « minimum de 2 mois et maximum de 6 mois »."""
    notes = construire_compteurs(
        _bulletin_avec_convention("Plasturgie (IDCC 0292)", {})
    )["notes"]
    assert any("de deux à six mois (convention de la plasturgie)" in n for n in notes)
    assert not any("D3171-11" in n for n in notes)


def test_plasturgie_avec_repos_obligatoire_garde_les_deux_mois():
    notes = construire_compteurs(
        _bulletin_avec_convention(
            "Plasturgie (IDCC 0292)", {"repos_compensateur": {"solde": 3.0}}
        )
    )["notes"]
    assert any("maximum de deux mois (C. trav. D3171-11)" in n for n in notes)


def test_autre_convention_garde_les_deux_mois():
    notes = construire_compteurs(
        _bulletin_avec_convention("Métallurgie (IDCC 3248)", {})
    )["notes"]
    assert any("maximum de deux mois (C. trav. D3171-11)" in n for n in notes)
