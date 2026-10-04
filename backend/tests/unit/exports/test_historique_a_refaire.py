"""L'historique des exports dit, ligne par ligne, quel export est à refaire."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.exports.application import a_refaire, queries

pytestmark = pytest.mark.unit

SOCIETE = "c1"


def _ligne(id_, type_="journal_paie", period="2026-09", le="2026-10-03T08:00:00+00:00"):
    return {
        "id": id_,
        "export_type": type_,
        "period": period,
        "status": "generated",
        "generated_at": le,
        "generated_by": "u1",
        "report": {},
        "file_paths": ["f.csv"],
    }


def _lectures(calculs, suppressions=()):
    infra = MagicMock()
    infra.list_calculs_des_bulletins.return_value = list(calculs)
    infra.list_suppressions_de_bulletins.return_value = list(suppressions)
    return patch.object(a_refaire, "infra_queries", infra), infra


class TestIdsDesExportsARefaire:
    def test_lit_les_annees_des_exports_et_les_suppressions_depuis_le_plus_ancien(self):
        exports = [
            _ligne("sept", le="2026-10-03T08:00:00+00:00"),
            _ligne("dec", period="2025-12", le="2026-01-05T08:00:00+00:00"),
        ]
        ctx, infra = _lectures(
            [{"year": 2026, "month": 9, "generated_at": "2026-10-03T09:00:00+00:00"}],
        )
        with ctx:
            assert a_refaire.ids_des_exports_a_refaire(SOCIETE, exports) == {"sept"}

        infra.list_calculs_des_bulletins.assert_called_once_with(SOCIETE, [2025, 2026])
        infra.list_suppressions_de_bulletins.assert_called_once_with(
            SOCIETE, "2026-01-05T08:00:00+00:00"
        )

    def test_un_bulletin_supprime_apres_l_export(self):
        ctx, _ = _lectures(
            [{"year": 2026, "month": 9, "generated_at": "2026-10-01T09:00:00+00:00"}],
            [{"details": {"year": 2026, "month": 9}, "created_at": "2026-10-03T09:00:00+00:00"}],
        )
        with ctx:
            assert a_refaire.ids_des_exports_a_refaire(SOCIETE, [_ligne("e1")]) == {"e1"}

    def test_sans_export_tire_des_bulletins_rien_n_est_lu(self):
        ctx, infra = _lectures([])
        with ctx:
            assert a_refaire.ids_des_exports_a_refaire(SOCIETE, [_ligne("n", type_="notes_frais")]) == set()

        infra.list_calculs_des_bulletins.assert_not_called()
        infra.list_suppressions_de_bulletins.assert_not_called()


class TestHistorique:
    def test_chaque_ligne_porte_a_refaire(self):
        lignes = [_ligne("refaire"), _ligne("a-jour", period="2026-08")]
        ctx, _ = _lectures(
            [
                {"year": 2026, "month": 9, "generated_at": "2026-10-03T09:00:00+00:00"},
                {"year": 2026, "month": 8, "generated_at": "2026-09-01T09:00:00+00:00"},
            ]
        )
        with (
            ctx,
            patch.object(queries.infra_queries, "list_exports_by_company", return_value=lignes),
            patch.object(queries.infra_queries, "get_profiles_map", return_value={}),
        ):
            reponse = queries.get_export_history(SOCIETE)

        assert {e.id: e.a_refaire for e in reponse.exports} == {"refaire": True, "a-jour": False}
