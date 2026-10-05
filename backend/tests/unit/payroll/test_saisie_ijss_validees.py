"""Le montant d'IJSS validé au suivi IJSS est une saisie du mois, relue à chaque calcul.

« Appliquer au bulletin » passait le montant au générateur en paramètre, sans
l'écrire nulle part : le recalcul suivant le perdait. Il s'écrit désormais comme
saisie du mois. Le générateur la relit comme le montant des IJSS subrogées, et
rien d'autre : ni prime, ni net, ni le mode « jours ouvrés » que pose la saisie
« IJSS override » (reconstitution d'un bulletin Cegid).
"""

from __future__ import annotations

import inspect
import json

import pytest

from app.modules.ijss_tracking.domain.saisie_ijss import (
    LIBELLE_IJSS_VALIDEES,
    est_saisie_ijss_validees,
)
from app.modules.payroll.documents import payslip_generator as pg
from app.modules.payroll.documents.bac_a_sable import BacASable
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader
from tests.unit.payroll.test_filet_heures_sur_arret import (  # noqa: F401 — fixture `moteur`
    ARRET_VALIDE,
    EMP,
    MOIS,
    _Base,
    _reel_de_septembre,
    moteur,
)

pytestmark = pytest.mark.unit

SAISIE = {
    "name": LIBELLE_IJSS_VALIDEES,
    "description": "Suivi IJSS, ligne exp-1",
    "amount": 320.5,
    "is_socially_taxed": False,
    "is_taxable": False,
    "manual_override": True,
}


class _BaseAvecSaisie(_Base):
    def lire(self, table: str, colonnes: str):
        if table == "monthly_inputs":
            return [dict(SAISIE)]
        return super().lire(table, colonnes)


def test_la_saisie_se_reconnait_a_son_libelle_et_n_est_pas_une_reconstitution():
    assert est_saisie_ijss_validees(SAISIE)
    assert not est_saisie_ijss_validees({"name": "Prime exceptionnelle", "amount": 320.5})
    # Pas la saisie « IJSS override », qui bascule aussi le maintien en jours ouvrés.
    assert not pg._is_ijss_override_input(SAISIE)


def test_le_generateur_relit_le_montant_comme_ijss_subrogees(monkeypatch, moteur):
    from app.modules.payroll.documents import payslip_run_heures

    lu: dict = {}

    def run(employee_path, year, month, *_a, **_k):
        chemin = employee_path / "saisies" / f"{month:02d}.json"
        lu.update(json.loads(chemin.read_text(encoding="utf-8")))
        return {"alertes_baremes": [], "salaire_brut": 0.0, "net_a_payer": 0.0}

    monkeypatch.setattr(payslip_run_heures, "run_payslip_generation_heures", run)
    monkeypatch.setattr(pg, "supabase", _BaseAvecSaisie(_reel_de_septembre(), compensation=False))
    monkeypatch.setattr(arrets_valides_reader, "par_salarie", lambda *_a, **_k: {EMP: [ARRET_VALIDE]})

    pg.process_payslip_generation(EMP, 2026, MOIS, bac_a_sable=BacASable())

    assert lu["ijss_brut_override"] == 320.5
    assert "maintien_base_ouvree" not in lu
    assert [p for p in lu["primes"] if p.get("libelle") == LIBELLE_IJSS_VALIDEES] == []
    assert lu["acompte"] == 0


def test_le_generateur_au_forfait_la_relit_aussi():
    from app.modules.payroll.documents import payslip_generator_forfait as pgf

    source = inspect.getsource(pgf.process_payslip_generation_forfait)
    debut = source.index("if est_saisie_ijss_validees(row):")
    assert source.index('saisies_data["ijss_brut_override"]', debut) > debut
