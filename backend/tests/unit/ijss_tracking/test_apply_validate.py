"""Tests service validate IJSS (montant CPAM)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import app.modules.ijss_tracking.application.apply_to_payslip as mod
from app.modules.ijss_tracking.application.apply_to_payslip import (
    _resolve_brut_amount,
    apply_validated_ijss_to_payslip,
)


def test_resolve_brut_manual_preempts():
    exp = {"employee_id": "e1", "ijss_brut_validated": 100.0}
    amt, src = _resolve_brut_amount(exp, "p1", 448.0, "manual")
    assert amt == 448.0
    assert src == "manual"


def test_resolve_brut_from_cpam_matched():
    exp = {"employee_id": "e1"}
    received = [
        {
            "employee_id": "e1",
            "source": "cpam_decompte",
            "match_status": "matched",
            "amount": 320.5,
        }
    ]

    class FakeRepo:
        @staticmethod
        def list_received_lines(_period_id):
            return received

    original = mod.repo.list_received_lines
    mod.repo.list_received_lines = FakeRepo.list_received_lines
    try:
        amt, src = _resolve_brut_amount(exp, "p1", None, None)
    finally:
        mod.repo.list_received_lines = original
    assert amt == 320.5
    assert src == "cpam_decompte"


# --- « Appliquer au bulletin » : une saisie du mois, puis la génération normale ---

EXPECTED = {
    "id": "exp-1",
    "period_id": "per-1",
    "employee_id": "emp-1",
    "ijss_brut_validated": 320.5,
    "validation_source": "cpam_decompte",
    "ijss_theorique": 350.0,
    "payslip_id": "ps-old",
}
PERIOD = {"id": "per-1", "period_year": 2026, "period_month": 5, "status": "open"}


class _Saisies:
    """`supabase.table("monthly_inputs")` : garde ce qui est effacé et écrit."""

    def __init__(self):
        self.ecrites: list[dict] = []
        self.effacees: list[dict] = []
        self.ordre: list[str] = []
        self._filtre: dict = {}

    def table(self, nom):
        assert nom == "monthly_inputs", nom
        self._filtre = {}
        return self

    def delete(self):
        self._action = "delete"
        return self

    def insert(self, ligne):
        self._action, self._ligne = "insert", ligne
        return self

    def match(self, filtre):
        self._filtre.update(filtre)
        return self

    def eq(self, cle, valeur):
        self._filtre[cle] = valeur
        return self

    def execute(self):
        if self._action == "delete":
            self.effacees.append(dict(self._filtre))
        else:
            self.ecrites.append(dict(self._ligne))
        self.ordre.append(self._action)
        return MagicMock(data=[])


def _monter(monkeypatch, *, bulletin=None, refus_salarie=None, origine=None):
    from app.modules.payslips.application import commands as cmd_mod
    from app.modules.payslips.application.dto import PayslipBadRequestError

    lignes: dict = {}
    monkeypatch.setattr(mod.repo, "get_expected_line", lambda _c, _e: dict(EXPECTED))
    monkeypatch.setattr(mod.repo, "get_period", lambda _c, _p: dict(PERIOD))
    monkeypatch.setattr(
        mod.repo,
        "update_expected_line",
        lambda eid, fields: lignes.update(fields) or {**EXPECTED, **fields},
    )
    monkeypatch.setattr(
        "app.modules.ijss_tracking.application.service._recompute_period",
        lambda p: p,
    )
    saisies = _Saisies()
    monkeypatch.setattr(mod, "supabase", saisies)

    def generable(employee_id, year, month):
        if refus_salarie:
            raise PayslipBadRequestError(refus_salarie)
        return {"id": employee_id}

    monkeypatch.setattr(mod, "salarie_generable", generable)
    monkeypatch.setattr(mod, "_fetch_existing_payslip", lambda *a: bulletin)
    monkeypatch.setattr(
        cmd_mod,
        "_fetch_payslip_status",
        lambda pid: {"id": pid, "status": "brouillon", "origine": origine},
    )

    generations: list = []

    def generer(cmd):
        saisies.ordre.append("generation")
        generations.append(cmd)
        return MagicMock(status="success", payslip_id="ps-new")

    monkeypatch.setattr(mod, "generate_payslip", generer)
    return saisies, generations, lignes


def test_appliquer_ecrit_la_saisie_du_mois_puis_passe_par_la_generation_normale(monkeypatch):
    from app.modules.ijss_tracking.domain.saisie_ijss import LIBELLE_IJSS_VALIDEES

    saisies, generations, lignes = _monter(monkeypatch, bulletin={"id": "ps-old"})

    result = apply_validated_ijss_to_payslip("co-1", "exp-1", "user-1")

    # La saisie précédente est remplacée, jamais doublée, avant le calcul.
    assert saisies.ordre == ["delete", "insert", "generation"]
    assert saisies.effacees == [
        {"employee_id": "emp-1", "year": 2026, "month": 5, "name": LIBELLE_IJSS_VALIDEES}
    ]
    [ecrite] = saisies.ecrites
    assert ecrite["name"] == LIBELLE_IJSS_VALIDEES
    assert ecrite["amount"] == 320.5
    assert (ecrite["employee_id"], ecrite["company_id"], ecrite["year"], ecrite["month"]) == (
        "emp-1",
        "co-1",
        2026,
        5,
    )
    assert ecrite["manual_override"] is True
    assert ecrite["is_socially_taxed"] is False
    # La génération normale : gardes de bascule, archive d'un bulletin validé,
    # documents de sortie, note du PDF.
    [cmd] = generations
    assert (cmd.employee_id, cmd.year, cmd.month) == ("emp-1", 2026, 5)
    assert cmd.regenerer_bulletin_valide is True
    assert cmd.requested_by == "user-1"
    assert result["applied_ijss_brut"] == 320.5
    assert result["payslip_id"] == "ps-new"
    assert lignes["applied_ijss_brut"] == 320.5
    assert lignes["payslip_id"] == "ps-new"


def test_un_mois_repris_par_la_bascule_est_refuse_sans_rien_ecrire(monkeypatch):
    refus = (
        "Le mois 05/2026 a été payé par le logiciel précédent et son bulletin est "
        "repris tel quel : il ne se recalcule pas."
    )
    saisies, generations, lignes = _monter(monkeypatch, refus_salarie=refus)

    with pytest.raises(ValueError, match="payé par le logiciel précédent"):
        apply_validated_ijss_to_payslip("co-1", "exp-1", "user-1")

    assert saisies.ordre == []
    assert generations == []
    assert lignes == {}


def test_un_bulletin_importe_est_refuse_sans_rien_ecrire(monkeypatch):
    saisies, generations, lignes = _monter(
        monkeypatch, bulletin={"id": "ps-old"}, origine="importe"
    )

    with pytest.raises(ValueError, match="repris tel quel"):
        apply_validated_ijss_to_payslip("co-1", "exp-1", "user-1")

    assert saisies.ordre == []
    assert generations == []
    assert lignes == {}


def test_un_recalcul_refuse_garde_la_saisie_et_le_dit(monkeypatch):
    from app.modules.payslips.application.dto import PayslipHeuresSurArretError

    saisies, _generations, lignes = _monter(monkeypatch, bulletin={"id": "ps-old"})

    def refuse(_cmd):
        raise PayslipHeuresSurArretError("Des heures sont saisies pendant l'arrêt.")

    monkeypatch.setattr(mod, "generate_payslip", refuse)

    with pytest.raises(ValueError) as exc:
        apply_validated_ijss_to_payslip("co-1", "exp-1", "user-1")

    assert "enregistré" in str(exc.value)
    assert "Des heures sont saisies pendant l'arrêt." in str(exc.value)
    assert len(saisies.ecrites) == 1
    assert lignes == {}
