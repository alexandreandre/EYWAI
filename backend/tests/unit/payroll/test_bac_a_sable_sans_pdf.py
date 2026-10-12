"""Un bulletin calculé en bac à sable n'est pas imprimé. [lot 31]

Le bac à sable rend le bulletin à l'appelant et jette son PDF sans le lire.
L'impression (WeasyPrint) coûtait 0,3 s par essai du brut d'une prime, la
moitié d'un essai une fois les lectures gardées en mémoire. Le bulletin
calculé est le même ; la vue imprimée se construit toujours depuis lui
(`construire_vue_bulletin`). Hors bac à sable, le PDF est imprimé comme avant.

Calcul hors ligne : barèmes figés, sans salarié ni société en base.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.core.paths import payroll_engine_root
from app.modules.payroll.documents import payslip_run_forfait, payslip_run_heures
from tests.unit.payroll.test_annee_des_baremes import _baremes, _dossier_salarie

pytestmark = pytest.mark.unit


def _dossier(tmp_path: Path, *, forfait: bool) -> Path:
    dossier = _dossier_salarie(tmp_path, 1)
    contrat = json.loads((dossier / "contrat.json").read_text(encoding="utf-8"))
    contrat["salarie"]["adresse"] = {"code_postal": "39100"}
    if forfait:
        contrat["contrat"].update({"is_forfait_jour": True, "statut": "Cadre"})
    (dossier / "contrat.json").write_text(json.dumps(contrat), encoding="utf-8")
    entreprise = json.loads((dossier / "entreprise.json").read_text(encoding="utf-8"))
    entreprise["entreprise"].setdefault("identification", {})["adresse"] = {"code_postal": "39100"}
    (dossier / "entreprise.json").write_text(json.dumps(entreprise), encoding="utf-8")
    return dossier


@pytest.fixture
def impressions(monkeypatch) -> list[str]:
    journal: list[str] = []

    class _Imprimeur:
        def __init__(self, *_a, **_k):
            journal.append("mise en page")

        def write_pdf(self, *_a, **_k):
            journal.append("pdf")

    def reseau_interdit(*_a, **_k):
        raise AssertionError("appel réseau pendant un test unitaire")

    monkeypatch.setattr(httpx.Client, "send", reseau_interdit)
    monkeypatch.setattr(payslip_run_heures, "HTML", _Imprimeur)
    monkeypatch.setattr(payslip_run_forfait, "HTML", _Imprimeur)
    return journal


MOTEURS = {
    "heures": (payslip_run_heures.run_payslip_generation_heures, False),
    "forfait": (payslip_run_forfait.run_payslip_generation_forfait, True),
}


@pytest.mark.parametrize("moteur", sorted(MOTEURS))
def test_en_bac_a_sable_le_bulletin_n_est_pas_imprime(tmp_path, impressions, moteur):
    calculer, forfait = MOTEURS[moteur]

    imprime = calculer(
        _dossier(tmp_path / "imprime", forfait=forfait), 2026, 1, payroll_engine_root(),
        baremes_override=_baremes(), persister=True,
    )
    assert impressions == ["mise en page", "pdf"]
    impressions.clear()

    a_blanc = calculer(
        _dossier(tmp_path / "a_blanc", forfait=forfait), 2026, 1, payroll_engine_root(),
        baremes_override=_baremes(), persister=False,
    )

    assert impressions == []
    assert a_blanc["net_a_payer"] == imprime["net_a_payer"] > 0
    assert a_blanc["salaire_brut"] == imprime["salaire_brut"]
    assert a_blanc["cumuls"] == imprime["cumuls"]


@pytest.mark.parametrize(
    ("module", "appel"),
    [
        ("payslip_generator", "payslip_json_data = run_payslip_generation_heures("),
        ("payslip_generator_forfait", "payslip_json_data = run_payslip_generation_forfait("),
    ],
)
def test_les_deux_generateurs_calculent_sans_persister_en_bac_a_sable(module, appel):
    import importlib
    import inspect

    source = inspect.getsource(importlib.import_module(f"app.modules.payroll.documents.{module}"))
    debut = source.index(appel)
    arguments = source[debut : source.index("\n        )", debut)]
    assert "persister=bac_a_sable is None" in arguments
