"""Une prime de règle automatique retirée reste à 0 dans les saisies : le
bulletin ne l'imprime pas pour autant en ligne à 0,00."""

from __future__ import annotations

import inspect
import json

import pytest

from app.modules.payroll.documents import payslip_generator as pg
from app.modules.payroll.documents.bac_a_sable import BacASable
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader
from tests.unit.payroll.test_filet_heures_sur_arret import (  # noqa: F401 — fixture `moteur`
    EMP,
    MOIS,
    _Base,
    _reel_de_septembre,
    moteur,
)

pytestmark = pytest.mark.unit

RETIREE = {
    "id": "s-auto",
    "name": "Prime de poste difficile",
    "description": "Auto: PRIME_POSTE_DIFFICILE",
    "amount": 0,
    "manual_override": True,
    "is_socially_taxed": True,
    "is_taxable": True,
}
AUTRE = {
    "id": "s-main",
    "name": "Prime exceptionnelle",
    "description": None,
    "amount": 50.0,
    "manual_override": True,
    "is_socially_taxed": True,
    "is_taxable": True,
}


class _BaseAvecSaisies(_Base):
    def lire(self, table: str, colonnes: str):
        if table == "monthly_inputs":
            return [dict(RETIREE), dict(AUTRE)]
        return super().lire(table, colonnes)


def test_la_prime_retiree_n_est_pas_imprimee(monkeypatch, moteur):
    from app.modules.payroll.documents import payslip_run_heures

    lu: dict = {}

    def run(employee_path, year, month, *_a, **_k):
        chemin = employee_path / "saisies" / f"{month:02d}.json"
        lu.update(json.loads(chemin.read_text(encoding="utf-8")))
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", run)
    monkeypatch.setattr(pg, "supabase", _BaseAvecSaisies(_reel_de_septembre(), compensation=False))
    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *_a, **_k: {EMP: []})

    pg.process_payslip_generation(EMP, 2026, MOIS, bac_a_sable=BacASable())

    assert [p["libelle"] for p in lu["primes"]] == ["Prime exceptionnelle"]


def test_le_generateur_au_forfait_l_ecarte_aussi():
    from app.modules.payroll.documents import payslip_generator_forfait as pgf

    source = inspect.getsource(pgf.process_payslip_generation_forfait)
    debut = source.index("for row in saisies_res.data:")
    assert source.index("if est_saisie_retiree(row):", debut) > debut
