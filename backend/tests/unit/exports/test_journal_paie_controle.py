"""Journal de paie : le contrôle du net ne crie plus au loup.

La prévisualisation comparait le net à « brut − cotisations − PAS » avec un
PAS toujours lu à zéro (clé absente des totaux), sans les éléments hors brut
ni les retenues : un écart était annoncé presque chaque mois.
"""

from types import SimpleNamespace

import pytest

from app.modules.exports.infrastructure import export_journal_paie as journal

pytestmark = pytest.mark.unit


class _Requete:
    def __init__(self, lignes):
        self._lignes = lignes

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def execute(self):
        return SimpleNamespace(data=self._lignes)


class _Base:
    def __init__(self, lignes):
        self._lignes = lignes

    def table(self, nom):
        return _Requete(self._lignes)


def _bulletin(net):
    return {
        "id": "bulletin-1",
        "employee_id": "salarie-1",
        "employees": {"id": "salarie-1", "first_name": "Salarié", "last_name": "Témoin", "companies": {}},
        "payslip_data": {
            "salaire_brut": 3000.0,
            "net_a_payer": net,
            "structure_cotisations": {
                "total_salarial": 600.0,
                "total_patronal": 900.0,
                "bloc_principales": [
                    {"coti_id": "csg_deductible", "montant_salarial": 600.0, "montant_patronal": 900.0}
                ],
            },
            "synthese_net": {
                "net_imposable": 2500.0,
                "acompte_verse": 300.0,
                "impot_prelevement_a_la_source": {"montant": 100.0},
            },
            "primes_non_soumises": [{"libelle": "Indemnité de transport", "montant": 50.0}],
        },
    }


def test_bulletin_complet_sans_avertissement(monkeypatch):
    monkeypatch.setattr(journal, "supabase", _Base([_bulletin(2050.0)]))
    preview = journal.preview_journal_paie("societe", "2026-09")
    assert preview["warnings"] == []
    assert preview["totals"]["total_pas"] == 100.0


def test_bulletin_incoherent_nomme(monkeypatch):
    monkeypatch.setattr(journal, "supabase", _Base([_bulletin(2050.01)]))
    preview = journal.preview_journal_paie("societe", "2026-09")
    assert len(preview["warnings"]) == 1
    assert "Salarié Témoin" in preview["warnings"][0]
    assert "0,01" in preview["warnings"][0]


def test_bulletin_repris_jamais_a_recalculer(monkeypatch):
    bulletin = _bulletin(2050.01)
    bulletin["payslip_data"]["reprise"] = {"logiciel_precedent": "Quadra"}
    monkeypatch.setattr(journal, "supabase", _Base([bulletin]))
    preview = journal.preview_journal_paie("societe", "2026-09")
    assert "repris" in preview["warnings"][0]
    assert "recalculez" not in preview["warnings"][0]
