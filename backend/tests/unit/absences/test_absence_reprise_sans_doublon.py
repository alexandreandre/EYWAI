"""Une absence reprise (import DSN, bulletins Quadra) ne double aucun jour.

Un arrêt de plus d'un mois est déclaré dans chaque DSN mensuelle qu'il touche
(cahier technique DSN 2026.1, bloc S21.G00.60, p. 265 : « En cas de
suspension supra-mensuelle, la suspension doit être déclarée dans toutes les
DSN mensuelles »), et une prolongation garde le même dernier jour travaillé.
Importer avril puis mai donnait deux demandes pour les jours d'avril : seuls
les jours exactement identiques étaient reconnus. On ne crée plus que les
jours qui manquent ; une suite de jours non contigus fait une demande par
morceau, pour qu'aucune demande ne couvre un trou.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.modules.absences.application import commands

pytestmark = pytest.mark.unit

EMPLOYE = "emp-1"
SOCIETE = "co-1"


def _jours(debut: str, fin: str) -> list[str]:
    d, f = date.fromisoformat(debut), date.fromisoformat(fin)
    return [(d + timedelta(days=n)).isoformat() for n in range((f - d).days + 1)]


class _Requete:
    def __init__(self, data):
        self._data = data

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return MagicMock(data=self._data)


def _client(existantes: list[dict]):
    client = MagicMock()

    def table(nom):
        if nom == "employees":
            return _Requete({"id": EMPLOYE, "company_id": SOCIETE, "employment_status": "actif"})
        return _Requete(existantes)

    client.table.side_effect = table
    return client


def _reprendre(existantes: list[dict], jours: list[str], absence_type: str = "arret_maladie"):
    crees: list[dict] = []

    def creer(data):
        row = {"id": f"new-{len(crees) + 1}", **data}
        crees.append(row)
        return row

    with patch.object(commands.absence_repository, "create", side_effect=creer), patch.object(
        commands.calendar_update_provider, "update_calendar_from_days"
    ):
        resultat = commands.create_reconciliation_absence(
            EMPLOYE,
            SOCIETE,
            "user-1",
            absence_type=absence_type,
            selected_days=jours,
            arret_type="maladie_simple" if absence_type == "arret_maladie" else None,
            supabase_client=_client(existantes),
        )
    return resultat, crees


def test_la_prolongation_ne_cree_que_les_jours_qui_manquent():
    avril = {"id": "a-1", "type": "arret_maladie", "selected_days": _jours("2026-04-27", "2026-04-30")}
    _, crees = _reprendre([avril], _jours("2026-04-27", "2026-05-30"))
    assert [c["selected_days"] for c in crees] == [_jours("2026-05-01", "2026-05-30")]


def test_un_arret_deja_couvert_ne_cree_rien():
    deja = {"id": "a-1", "type": "arret_maladie", "selected_days": _jours("2026-04-27", "2026-05-30")}
    resultat, crees = _reprendre([deja], _jours("2026-04-27", "2026-04-30"))
    assert crees == []
    assert resultat["id"] == "a-1"


def test_les_memes_jours_rendent_la_demande_existante():
    deja = {"id": "a-1", "type": "arret_maladie", "selected_days": _jours("2026-04-27", "2026-04-30")}
    resultat, crees = _reprendre([deja], _jours("2026-04-27", "2026-04-30"))
    assert crees == [] and resultat["id"] == "a-1"


def test_un_trou_au_milieu_donne_une_demande_par_morceau():
    milieu = {"id": "a-1", "type": "arret_maladie", "selected_days": _jours("2026-05-10", "2026-05-12")}
    _, crees = _reprendre([milieu], _jours("2026-05-08", "2026-05-14"))
    assert [c["selected_days"] for c in crees] == [
        _jours("2026-05-08", "2026-05-09"),
        _jours("2026-05-13", "2026-05-14"),
    ]


def test_sans_demande_existante_tout_est_cree_d_un_bloc():
    _, crees = _reprendre([], _jours("2026-05-04", "2026-05-31"))
    assert [c["selected_days"] for c in crees] == [_jours("2026-05-04", "2026-05-31")]
    assert crees[0]["arret_type"] == "maladie_simple"
