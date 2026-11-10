"""Catégorie « Téléphone » des notes de frais (retour du 10/11/2026)."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.expenses.domain.enums import ExpenseType
from app.modules.expenses.schemas.requests import ExpenseBase, ExpenseUpdateRequest
from app.modules.expenses.schemas.responses import Expense
from app.modules.exports.infrastructure.export_notes_frais import EXPENSE_TYPE_ACCOUNTS
from app.modules.exports.schemas.requests import NotesFraisExportRequest
from app.modules.payroll.engine.frais_professionnels import libelle_de_note_de_frais

pytestmark = pytest.mark.unit


def test_le_type_existe():
    assert ExpenseType("Téléphone") is ExpenseType.TELEPHONE


def test_une_note_telephone_se_depose_et_se_modifie():
    note = ExpenseBase(date=date(2026, 10, 3), amount=29.99, vat_rate=20, type="Téléphone")
    assert note.type == "Téléphone"
    assert ExpenseUpdateRequest(type="Téléphone").type == "Téléphone"


def test_la_reponse_l_accepte():
    assert "Téléphone" in Expense.model_fields["type"].annotation.__args__


def test_compte_de_charge_des_telecommunications():
    # PCG, compte 626 « Frais postaux et de télécommunications ».
    assert EXPENSE_TYPE_ACCOUNTS["Téléphone"] == "626000"


def test_l_export_filtre_sur_le_telephone():
    requete = NotesFraisExportRequest(period="2026-10", expense_types=["Téléphone"])
    assert requete.expense_types == ["Téléphone"]


def test_libelle_sur_le_bulletin_enregistre():
    assert libelle_de_note_de_frais("Téléphone", "2026-10-03") == "Note de frais : téléphone du 03/10/2026"
