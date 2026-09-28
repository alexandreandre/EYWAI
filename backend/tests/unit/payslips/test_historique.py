"""L'historique d'un bulletin s'ouvre toujours et désigne la bonne version."""

from datetime import datetime

import pytest

from app.modules.payslips.domain.historique import (
    VERSIONS_CONSERVEES,
    entree_de_version,
    plafonner,
    prochaine_version,
)
from app.modules.payslips.schemas.responses import HistoryEntry

pytestmark = pytest.mark.unit


def _h(*versions):
    return [{"version": v, "changes_summary": f"v{v}"} for v in versions]


def test_la_version_suivante_suit_le_plus_grand_numero_pas_la_longueur():
    assert prochaine_version(_h(3, 4, 5, 6, 7, 8, 9, 10, 11, 12)) == 13
    assert prochaine_version([]) == 1


def test_une_entree_illisible_ne_bloque_pas_la_numerotation():
    assert prochaine_version([None, {"version": "x"}, {"version": 4}]) == 5


def test_le_plafond_garde_les_plus_recentes():
    assert VERSIONS_CONSERVEES == 10
    assert [e["version"] for e in plafonner(_h(*range(1, 15)))] == list(range(5, 15))


def test_on_retrouve_une_version_par_son_numero_pas_par_sa_position():
    historique = _h(3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
    assert entree_de_version(historique, 5)["changes_summary"] == "v5"
    assert entree_de_version(historique, 12)["changes_summary"] == "v12"
    assert entree_de_version(historique, 2) is None


def test_un_ancien_doublon_de_numero_rend_la_plus_recente():
    historique = [{"version": 10, "changes_summary": "ancienne"}, {"version": 10, "changes_summary": "recente"}]
    assert entree_de_version(historique, 10)["changes_summary"] == "recente"


def test_une_version_sans_auteur_reste_lisible():
    """370 versions archivées par une régénération n'ont pas d'auteur : l'écran
    de modification tombait en erreur au lieu de s'ouvrir."""
    e = HistoryEntry(
        version=1,
        edited_at=datetime(2026, 9, 14, 19, 34),
        edited_by=None,
        edited_by_name=None,
        changes_summary="Régénération",
        previous_payslip_data={},
    )
    assert e.edited_by is None and e.edited_by_name is None


def test_l_archive_avant_regeneration_numerote_apres_le_plus_grand_et_plafonne():
    from unittest.mock import MagicMock, patch

    from app.modules.payslips.application import commands
    from app.modules.payslips.application.dto import GeneratePayslipInput

    existant = {
        "id": "ps-1",
        "status": "brouillon",
        "payslip_data": {"net_a_payer": 1},
        "url": "u",
        "edit_history": _h(*range(3, 13)),
    }
    client = MagicMock()
    with patch.object(commands, "supabase", client):
        commands._archive_before_regeneration(
            existant, GeneratePayslipInput(employee_id="e", year=2026, month=8)
        )

    ecrit = client.table.return_value.update.call_args.args[0]["edit_history"]
    assert len(ecrit) == VERSIONS_CONSERVEES
    assert ecrit[-1]["version"] == 13
    assert ecrit[-1]["edited_by_name"] == "Système"
    assert ecrit[0]["version"] == 4
