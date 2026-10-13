"""Les deux générateurs calculent un mois de l'ancien contrat sur la fiche de ce contrat [D4].

Après « Nouveau contrat », la fiche porte le CDI commencé le 01/10/2026 ; le
bulletin de septembre, dernier mois du CDD rangé, se recalcule avec le CDD :
son type, son entrée, sa fin, sa durée et sa sortie (pour la précarité,
l'indemnité de congés et le prorata).
"""

from __future__ import annotations

import inspect
import json

import pytest

from app.modules.payroll.documents import payslip_generator as pg
from app.modules.payroll.documents import payslip_run_heures
from app.modules.payroll.documents.bac_a_sable import BacASable
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader
from tests.unit.payroll.test_filet_heures_sur_arret import (  # noqa: F401 — fixture `moteur`
    EMP,
    _Base,
    moteur,
)

pytestmark = pytest.mark.unit

FICHE_DU_CDD = {
    "hire_date": "2026-03-02",
    "date_debut_execution": None,
    "date_conclusion_contrat": None,
    "contract_type": "CDD",
    "contract_end_date": "2026-09-30",
    "duree_hebdomadaire": 35,
    "is_temps_partiel": False,
    "job_title": "Opératrice",
    "seniority_reference_date": None,
}
PERIODE = {
    "id": "periode-1",
    "employee_id": EMP,
    "contract_type": "CDD",
    "date_debut": "2026-03-02",
    "date_fin": "2026-09-30",
    "fiche": FICHE_DU_CDD,
}


def test_le_generateur_heures_calcule_septembre_sur_le_cdd_range(monkeypatch, moteur):  # noqa: F811
    from app.modules.employees.application.contrat_du_mois import lecteur_contrats

    lu: dict = {}

    def run_espion(employee_path, *_a, **_k):
        lu.update(json.loads((employee_path / "contrat.json").read_text(encoding="utf-8")))
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    class _FicheEnCdi(_Base):
        def lire(self, table, colonnes):
            ligne = super().lire(table, colonnes)
            if table == "employees":
                ligne = {
                    **ligne,
                    "hire_date": "2026-10-01",
                    "contract_type": "CDI",
                    "contract_end_date": None,
                    "duree_hebdomadaire": 39,
                    "employment_status": "actif",
                    "current_exit_id": None,
                }
            return ligne

    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", run_espion)
    monkeypatch.setattr(pg, "supabase", _FicheEnCdi([], compensation=False))
    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *_a, **_k: {EMP: []})
    monkeypatch.setattr(lecteur_contrats, "contrat_passe_du_mois", lambda *_a: PERIODE)
    monkeypatch.setattr(lecteur_contrats, "sortie_du_contrat", lambda *_a: "2026-09-30")

    pg.process_payslip_generation(EMP, 2026, 9, bac_a_sable=BacASable(cumuls_precedents=None))

    contrat = lu["contrat"]
    assert contrat["type_contrat"] == "CDD"
    assert contrat["date_entree"] == "2026-03-02"
    assert contrat["date_fin_contrat"] == "2026-09-30"
    assert str(contrat["date_sortie"])[:10] == "2026-09-30"


def test_le_generateur_forfait_lit_aussi_la_fiche_du_mois():
    from app.modules.payroll.documents import payslip_generator_forfait as pgf

    source = inspect.getsource(pgf.process_payslip_generation_forfait)
    lecture = source.index('.table("employees")')
    fiche = source.index("fiche_du_mois(")
    garde = source.index("payslip_employment_period_block_reason(")
    assert lecture < fiche < garde
