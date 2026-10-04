"""Un export déjà fait est « à refaire » quand un bulletin de son mois a changé depuis.

Les exports relisent les bulletins à chaque génération, mais un fichier déjà
sorti (journal, virement, écritures, DSN…) ne bouge plus : un bulletin du mois
recalculé, supprimé ou ajouté après lui le laissait faux sans que rien ne le
dise (audit du 04/10). La règle se calcule à la lecture.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.modules.exports.domain.a_refaire import (
    derniere_modification_par_mois,
    exports_a_refaire,
    instant,
)

pytestmark = pytest.mark.unit


def _export(id_, type_="journal_paie", period="2026-09", le="2026-10-03T08:00:00+00:00", status="generated"):
    return {"id": id_, "export_type": type_, "period": period, "generated_at": le, "status": status}


def _le(texte: str) -> datetime:
    return datetime.fromisoformat(texte)


class TestDerniereModificationParMois:
    def test_le_dernier_calcul_du_mois(self):
        calculs = [
            {"year": 2026, "month": 9, "generated_at": "2026-10-02T10:00:00+00:00"},
            {"year": 2026, "month": 9, "generated_at": "2026-10-03T09:30:00.5+00:00"},
            {"year": 2026, "month": 8, "generated_at": "2026-09-01T10:00:00+00:00"},
        ]

        assert derniere_modification_par_mois(calculs, []) == {
            "2026-09": _le("2026-10-03T09:30:00.5+00:00"),
            "2026-08": _le("2026-09-01T10:00:00+00:00"),
        }

    def test_une_suppression_plus_recente_que_le_dernier_calcul(self):
        calculs = [{"year": 2026, "month": 9, "generated_at": "2026-10-02T10:00:00+00:00"}]
        suppressions = [
            {"details": {"year": 2026, "month": 9}, "created_at": "2026-10-03T11:00:00+00:00"},
            {"details": {"year": "2026", "month": "7"}, "created_at": "2026-10-03T12:00:00Z"},
        ]

        assert derniere_modification_par_mois(calculs, suppressions) == {
            "2026-09": _le("2026-10-03T11:00:00+00:00"),
            "2026-07": _le("2026-10-03T12:00:00+00:00"),
        }

    def test_une_ligne_illisible_est_ignoree(self):
        calculs = [
            {"year": 2026, "month": 9, "generated_at": None},
            {"year": None, "month": 9, "generated_at": "2026-10-02T10:00:00+00:00"},
        ]
        suppressions = [{"details": None, "created_at": "2026-10-03T11:00:00+00:00"}]

        assert derniere_modification_par_mois(calculs, suppressions) == {}


class TestExportsARefaire:
    def test_un_bulletin_recalcule_apres_l_export(self):
        modifies = {"2026-09": _le("2026-10-03T09:00:00+00:00")}

        assert exports_a_refaire([_export("e1")], modifies) == {"e1"}

    def test_rien_n_a_bouge_depuis_l_export(self):
        modifies = {"2026-09": _le("2026-10-03T07:59:59+00:00")}

        assert exports_a_refaire([_export("e1")], modifies) == set()

    def test_un_bulletin_d_un_autre_mois_ne_touche_pas_l_export(self):
        modifies = {"2026-08": _le("2026-10-04T09:00:00+00:00")}

        assert exports_a_refaire([_export("e1")], modifies) == set()

    def test_seul_le_dernier_export_du_type_et_du_mois(self):
        """Refait depuis, l'ancien est remplacé : le dire « à refaire » serait faux."""
        exports = [
            _export("ancien", le="2026-10-01T08:00:00+00:00"),
            _export("refait", le="2026-10-03T10:00:00+00:00"),
            _export("virement", type_="virement_salaires", le="2026-10-01T08:00:00+00:00"),
        ]
        modifies = {"2026-09": _le("2026-10-02T09:00:00+00:00")}

        assert exports_a_refaire(exports, modifies) == {"virement"}

    @pytest.mark.parametrize("type_", ["conges_absences", "notes_frais", "virement_acomptes"])
    def test_un_export_qui_ne_lit_pas_les_bulletins(self, type_):
        modifies = {"2026-09": _le("2026-10-04T09:00:00+00:00")}

        assert exports_a_refaire([_export("e1", type_=type_)], modifies) == set()

    @pytest.mark.parametrize("status", ["previewed", "cancelled", "replaced"])
    def test_seul_un_export_genere(self, status):
        modifies = {"2026-09": _le("2026-10-04T09:00:00+00:00")}

        assert exports_a_refaire([_export("e1", status=status)], modifies) == set()

    def test_une_date_d_export_sans_fuseau_est_en_utc(self):
        modifies = {"2026-09": _le("2026-10-03T08:30:00+00:00")}

        assert exports_a_refaire([_export("e1", le="2026-10-03T08:00:00")], modifies) == {"e1"}


class TestInstant:
    @pytest.mark.parametrize(
        ("texte", "attendu"),
        [
            ("2026-10-03T08:00:00+00:00", datetime(2026, 10, 3, 8, tzinfo=UTC)),
            ("2026-10-03T08:00:00Z", datetime(2026, 10, 3, 8, tzinfo=UTC)),
            ("2026-10-03T08:00:00", datetime(2026, 10, 3, 8, tzinfo=UTC)),
            ("2026-10-03 10:00:00+02:00", datetime(2026, 10, 3, 8, tzinfo=UTC)),
        ],
    )
    def test_lit_les_formats_de_la_base(self, texte, attendu):
        assert instant(texte) == attendu

    @pytest.mark.parametrize("texte", [None, "", "pas une date"])
    def test_illisible(self, texte):
        assert instant(texte) is None
