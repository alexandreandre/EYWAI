"""Les brouillons d'un départ supprimé ne s'affichent plus (réunion du 10/11/2026).

Colorplast, F.A.O. : dix documents de sortie en brouillon en deux séries, l'une
issue d'un départ supprimé puis ressaisi. Rien n'est effacé en base.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.documents.domain.departs_supprimes import (
    departs_cites,
    sans_les_brouillons_de_departs_supprimes,
)

pytestmark = pytest.mark.unit

SUPPRIME, ACTUEL = "3259a881", "7d1d12ff"


def _doc(id_, exit_id, status="brouillon", source="employee_exit_bundle"):
    return {
        "id": id_,
        "status": status,
        "generation_context": {"source": source, "exit_id": exit_id},
    }


DOCS = [
    _doc("a", SUPPRIME),
    _doc("b", SUPPRIME, source="employee_exit_bundle_portability"),
    _doc("c", SUPPRIME, status="envoye"),
    _doc("d", ACTUEL),
    {"id": "e", "status": "brouillon", "generation_context": {"source": "modele"}},
    {"id": "f", "status": "brouillon", "generation_context": None},
]


def test_brouillons_du_depart_supprime_retires():
    gardes = sans_les_brouillons_de_departs_supprimes(DOCS, {ACTUEL})
    assert [d["id"] for d in gardes] == ["c", "d", "e", "f"]


def test_departs_cites():
    assert departs_cites(DOCS) == {SUPPRIME, ACTUEL}


def test_le_depot_filtre_la_liste():
    from app.modules.documents.infrastructure import repository as repo_mod

    requete = MagicMock()
    for nom in ("select", "eq", "in_", "gte", "lte", "order"):
        getattr(requete, nom).return_value = requete
    requete.execute.return_value = MagicMock(data=[dict(d) for d in DOCS])
    departs = MagicMock()
    departs.select.return_value = departs
    departs.in_.return_value = departs
    departs.execute.return_value = MagicMock(data=[{"id": ACTUEL}])

    def table(nom):
        return departs if nom == "employee_exits" else requete

    with (
        patch.object(repo_mod, "supabase") as sb,
        patch.object(repo_mod.SupabaseDocumentsRepository, "_enrich_rows"),
    ):
        sb.table.side_effect = table
        lignes = repo_mod.SupabaseDocumentsRepository().get_all("c1", employee_id="e1")
    assert [d["id"] for d in lignes] == ["c", "d", "e", "f"]


def test_depart_illisible_rien_n_est_cache():
    from app.modules.documents.infrastructure import repository as repo_mod

    requete = MagicMock()
    for nom in ("select", "eq", "in_", "gte", "lte", "order"):
        getattr(requete, nom).return_value = requete
    requete.execute.return_value = MagicMock(data=[dict(d) for d in DOCS])
    departs = MagicMock()
    departs.select.return_value = departs
    departs.in_.return_value = departs
    departs.execute.side_effect = RuntimeError("réseau")

    with (
        patch.object(repo_mod, "supabase") as sb,
        patch.object(repo_mod.SupabaseDocumentsRepository, "_enrich_rows"),
    ):
        sb.table.side_effect = lambda nom: departs if nom == "employee_exits" else requete
        lignes = repo_mod.SupabaseDocumentsRepository().get_all("c1")
    assert len(lignes) == len(DOCS)
