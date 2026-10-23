"""La DSN recalcule base × taux sur plusieurs familles : une ligne corrigée par la
règle 3 y passe au centime (spec § 7). Chiffres sondés le 23/10."""

from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations

pytestmark = pytest.mark.unit


def _dsn(lignes, brut=2000.0):
    _, cotisations, avertissements = build_bases_and_cotisations(
        lignes, brut=brut, period_start="2026-10-01", period_end="2026-10-31"
    )
    assert avertissements == []
    return {c.code: round(float(c.montant_patronal or 0.0), 2) for c in cotisations}


def test_une_maladie_corrigee_par_son_taux_se_scinde_en_socle_et_complement():
    ligne = {"coti_id": "securite_sociale_maladie", "libelle": "Maladie, maternité, invalidité, décès",
             "base": 2000.0, "taux_salarial": 0.0, "taux_patronal": 0.073, "montant_salarial": 0.0,
             "montant_patronal": 146.0, "correction": {"saisie_id": "c1"}, "valeur_calculee": {"montant_patronal": 140.0}}
    assert _dsn([ligne]) == {"075": 140.0, "907": 6.0}


def test_une_csg_corrigee_par_sa_base_se_recalcule_au_centime():
    lignes = [
        {"coti_id": "csg_deductible", "libelle": "CSG déductible", "base": 2100.0, "taux_salarial": 0.068,
         "taux_patronal": None, "montant_salarial": 142.8, "montant_patronal": 0.0, "correction": {"saisie_id": "c1"}},
        {"coti_id": "csg_non_deductible", "libelle": "CSG/CRDS non déductible", "base": 2000.0, "taux_salarial": 0.029,
         "taux_patronal": None, "montant_salarial": 58.0, "montant_patronal": 0.0},
    ]
    dsn = _dsn(lignes)
    assert round(dsn["072"] + dsn["079"], 2) == round(142.8 + 58.0, 2)


def test_une_reduction_generale_corrigee_se_declare_pour_son_montant():
    lignes = [
        {"coti_id": "vieillesse_plafonnee", "libelle": "Vieillesse plafonnée", "base": 2000.0, "taux_salarial": 0.069,
         "taux_patronal": 0.0855, "montant_salarial": 138.0, "montant_patronal": 171.0},
        {"coti_id": "reduction_generale", "libelle": "Réduction générale de cotisations patronales", "base": 2000.0,
         "taux_salarial": None, "taux_patronal": 0.1978, "montant_salarial": 0.0, "montant_patronal": -250.0,
         "smic_reference_mois": 1823.03, "correction": {"saisie_id": "c1"}},
    ]
    dsn = _dsn(lignes)
    assert round(dsn["018"] + dsn["106"], 2) == -250.0
