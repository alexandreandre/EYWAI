"""Arrêt maladie : maintien employeur dans le brut + IJSS subrogées et CSG."""

from __future__ import annotations

from app.modules.payroll.documents.payslip_run_heures import (
    _appliquer_maintien_arret_maladie,
)

from .helpers import build_test_contexte


def _details_base():
    return [
        {"libelle": "Salaire de base", "gain": 2500.0, "perte": None},
        {
            "libelle": "Absence arrêt maladie (jours déduction)",
            "gain": None,
            "perte": 400.0,
            "is_arret_maladie": True,
        },
    ]


def test_maintien_ajoute_au_brut_cotisable():
    ctx = build_test_contexte(salaire_base=2500.0)
    details = _details_base()
    rm = {
        "subrogation_active": False,
        "maintien": {"maintien_verse": 300.0, "complement_employeur": 300.0},
        "ijss": {"ijss_theorique": 0.0},
    }
    csg, ijss, modif = _appliquer_maintien_arret_maladie(ctx, rm, details)
    assert modif is True
    assert any(l.get("is_maintien_employeur") for l in details)
    assert csg == []
    assert ijss == []


def test_ijss_subrogees_csg_et_imposable():
    ctx = build_test_contexte(salaire_base=2500.0)
    details = _details_base()
    rm = {
        "subrogation_active": True,
        "maintien": {"maintien_verse": 300.0, "complement_employeur": 300.0},
        "ijss": {"ijss_theorique": 250.0},
    }
    csg, ijss, modif = _appliquer_maintien_arret_maladie(ctx, rm, details)
    assert modif is True
    libelles = {l["libelle"]: l["montant_salarial"] for l in csg}
    assert "CSG déductible IJSS" in libelles
    assert "CSG/CRDS IJSS non déductible" in libelles
    assert libelles["CSG déductible IJSS"] == round(250.0 * 0.038, 2)
    assert libelles["CSG/CRDS IJSS non déductible"] == round(250.0 * 0.029, 2)
    assert ijss and ijss[0]["montant"] == 250.0


def test_pas_de_maintien_sans_resultats():
    ctx = build_test_contexte(salaire_base=2500.0)
    details = _details_base()
    csg, ijss, modif = _appliquer_maintien_arret_maladie(ctx, None, details)
    assert (csg, ijss, modif) == ([], [], False)
