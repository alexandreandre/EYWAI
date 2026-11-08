"""Ce qui ne se corrige pas sur la carte dit où se corriger (R-184)."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.corrections_du_bulletin import blocs_a_la_source

pytestmark = pytest.mark.unit

BULLETIN = {
    "primes_non_soumises": [{"libelle": "Frais de repas", "montant": 12.5}],
    "revenus_hors_brut_imposables": [{"libelle": "Indemnité imposable", "montant": 30.0}],
    "participations": [{"libelle": "Participation", "montant": 200.0}],
    "remboursements_avances": {"total_rembourse": 150.0},
    "retenues_saisies": {"total_preleve": 80.0},
    "remboursements_prets": {"total_rembourse": 45.0},
    "indemnites_sortie": {"lignes_exonerees": [{"libelle": "Indemnité légale de licenciement", "montant": 900.0}]},
    "synthese_net": {"ijss_net": 320.0, "acompte_verse": 25.0},
}


def _par_libelle(blocs):
    return {b["libelle"]: b for b in blocs}


def test_chaque_bloc_hors_carte_dit_sa_source():
    blocs = _par_libelle(blocs_a_la_source(BULLETIN))
    assert set(blocs) == {
        "Frais de repas",
        "Indemnité imposable",
        "Participation",
        "Avances remboursées",
        "Saisies sur salaire",
        "Prêt employeur",
        "Indemnité légale de licenciement",
        "Indemnités journalières nettes",
        "Acomptes du mois",
    }
    assert all(b["source"] for b in blocs.values())
    assert blocs["Avances remboursées"]["montant"] == 150.0
    assert "Prêts employeur" in blocs["Prêt employeur"]["source"]
    assert "Sorties de salarié" in blocs["Indemnité légale de licenciement"]["source"]


@pytest.mark.parametrize("vide", [{}, {"primes_non_soumises": [], "remboursements_prets": {"total_rembourse": 0}, "synthese_net": {"ijss_net": 0}}])
def test_un_bulletin_sans_ces_blocs_ne_liste_rien(vide):
    assert blocs_a_la_source(vide) == []


def test_un_bulletin_illisible_ne_plante_pas():
    assert blocs_a_la_source(None) == []
    assert blocs_a_la_source({"primes_non_soumises": ["x"], "indemnites_sortie": "y", "synthese_net": []}) == []
