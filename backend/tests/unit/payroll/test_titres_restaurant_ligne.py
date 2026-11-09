"""Les titres-restaurant retirés du net se lisent au bulletin et dans l'OD (R-213)."""

from __future__ import annotations

from types import SimpleNamespace

from app.modules.exports.infrastructure.payslip_accounting_extract import (
    extract_elements_hors_brut,
)
from app.modules.payroll.documents.bulletin_view import _lignes_hors_brut
from app.modules.payroll.engine.calcul_net import deduction_titres_restaurant

LIBELLE = "Titres-restaurant (part salariale)"


def _contexte(**titres) -> SimpleNamespace:
    return SimpleNamespace(contrat={"specificites_paie": {"titres_restaurant": titres}})


def test_la_deduction_est_la_part_salariale_du_mois():
    contexte = _contexte(
        beneficie=True, valeur_faciale=10.0, part_patronale=6.0, nombre_par_mois=18
    )
    assert deduction_titres_restaurant(contexte) == 72.0


def test_sans_titres_aucune_deduction():
    assert deduction_titres_restaurant(_contexte(beneficie=False)) == 0.0
    assert deduction_titres_restaurant(SimpleNamespace(contrat={})) == 0.0


def test_beneficiaire_sans_nombre_ne_retire_rien():
    assert deduction_titres_restaurant(_contexte(beneficie=True, nombre_par_mois=0)) == 0.0


def test_le_bulletin_montre_la_retenue():
    bulletin = {"synthese_net": {"titres_restaurant": 72.0}}
    lignes = [l for l in _lignes_hors_brut(bulletin) if l["libelle"] == LIBELLE]
    assert len(lignes) == 1
    assert lignes[0]["montant_salarial"] == -72.0


def test_sans_titres_aucune_ligne():
    assert not [
        l for l in _lignes_hors_brut({"synthese_net": {}}) if l["libelle"] == LIBELLE
    ]


def test_l_extraction_comptable_porte_la_retenue():
    elements = extract_elements_hors_brut({"synthese_net": {"titres_restaurant": 72.0}})
    trouves = [e for e in elements if e["libelle"] == LIBELLE]
    assert len(trouves) == 1
    assert trouves[0]["montant"] == -72.0
