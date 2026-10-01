"""Fin de CDD en cours de mois : les documents reprennent les lignes du bulletin.

Cas synthétique (Jeanne Essai), sans écriture en base : le brut du moteur
fournit le bulletin, les documents (solde, attestation) doivent afficher les
mêmes indemnité de congés, précarité et dernier salaire.
"""

from __future__ import annotations

import io
from datetime import date
from unittest.mock import MagicMock

import pdfplumber
import pytest

from app.modules.payroll.documents.attestation_employeur_salary_history import get_salary_history
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.solde_de_tout_compte.common.bulletin_de_sortie import (
    lignes_du_bulletin,
    sommes_de_rupture_du_bulletin,
)
from app.modules.payroll.solde_de_tout_compte.common.pdf_helpers import format_currency
from app.modules.payroll.solde_de_tout_compte.document_generator import (
    EmployeeExitDocumentGenerator,
)

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

SALARIE = {
    "id": "emp-cdd-mi-mois",
    "first_name": "Jeanne",
    "last_name": "Essai",
    "date_naissance": "1990-01-01",
    "hire_date": "2026-01-05",
    "job_title": "Opératrice",
    "contract_type": "CDD",
    "salaire_de_base": {"valeur": 2200.0},
    "duree_hebdomadaire": 35,
}
SOCIETE = {"company_name": "Société QA", "siret": "12345678900011", "city": "Belley"}
SORTIE = {"last_working_day": "2026-04-15", "exit_type": "fin_cdd", "notice_period_days": 0}


def _client(bulletin: dict) -> MagicMock:
    client = MagicMock()

    class Requete:
        def __init__(self):
            self.filtres = {}

        def select(self, *_a, **_k):
            return self

        def eq(self, colonne, valeur):
            self.filtres[colonne] = valeur
            return self

        def limit(self, *_a):
            return self

        def execute(self):
            if self.filtres.get("year", 2026) == 2026 and self.filtres.get("month", 4) == 4:
                return MagicMock(data=[{"year": 2026, "month": 4, "payslip_data": bulletin}])
            return MagicMock(data=[])

    client.table.side_effect = lambda _nom: Requete()
    return client


def _texte(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return "\n".join(page.extract_text() or "" for page in document.pages)


def _bulletin_de_fin_cdd_mi_mois() -> dict:
    ctx = build_test_contexte(
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2026-01-05",
        date_fin_contrat="2026-04-15",
        cumuls={"brut_total": 6600.0},
    )
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    return {
        "salaire_brut": res["salaire_brut_total"],
        "net_a_payer": res["salaire_brut_total"],
        "calcul_du_brut": res["lignes_composants_brut"],
    }


def test_fin_cdd_en_cours_de_mois_documents_egale_bulletin():
    bulletin = _bulletin_de_fin_cdd_mi_mois()
    lignes = bulletin["calcul_du_brut"]
    precarite = next(l for l in lignes if "précarité" in l["libelle"].lower())
    iccp = next(l for l in lignes if "compensatrice de congés" in l["libelle"].lower())
    salaire = next(l for l in lignes if l["libelle"] == "Salaire de base")

    assert salaire["gain"] == pytest.approx(1116.90)
    assert precarite["gain"] == pytest.approx(771.69)
    assert iccp["gain"] == pytest.approx(848.86)

    sommes = {s["libelle"]: s["montant"] for s in sommes_de_rupture_du_bulletin(bulletin)}
    assert sommes[precarite["libelle"]] == pytest.approx(precarite["gain"])
    assert sommes[iccp["libelle"]] == pytest.approx(iccp["gain"])

    remuneration, rupture, _apres = lignes_du_bulletin(bulletin)
    assert next(l["montant"] for l in remuneration if l["label"] == "Salaire de base") == pytest.approx(
        salaire["gain"]
    )
    rupture_par_libelle = {l["label"]: l["montant"] for l in rupture}
    assert rupture_par_libelle[precarite["libelle"]] == pytest.approx(precarite["gain"])
    assert rupture_par_libelle[iccp["libelle"]] == pytest.approx(iccp["gain"])

    client = _client(bulletin)
    solde = _texte(
        EmployeeExitDocumentGenerator().generate_solde_tout_compte(
            SALARIE, SOCIETE, SORTIE, {}, client
        )
    )
    assert format_currency(precarite["gain"]) in solde
    assert format_currency(iccp["gain"]) in solde
    assert format_currency(salaire["gain"]) in solde

    historique = get_salary_history("emp-cdd-mi-mois", SALARIE, "2026-04-15", supabase_client=client)
    dernier = historique["months"][-1]
    assert dernier["year"] == 2026 and dernier["month"] == 4
    attendu_salaire = round(bulletin["salaire_brut"] - precarite["gain"] - iccp["gain"], 2)
    assert dernier["gross_salary"] == pytest.approx(attendu_salaire)
    sommes_attestation = {
        s["libelle"]: s["montant"] for s in historique["sommes_de_rupture"]
    }
    assert sommes_attestation[precarite["libelle"]] == pytest.approx(precarite["gain"])
    assert sommes_attestation[iccp["libelle"]] == pytest.approx(iccp["gain"])
