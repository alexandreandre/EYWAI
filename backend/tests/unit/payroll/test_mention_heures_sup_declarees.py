"""Le bulletin dit quand ses heures sup ont été déclarées depuis le bulletin."""

import pytest

from app.modules.payroll.documents.bulletin_view import mention_heures_sup_declarees
from app.modules.payslips.domain.heures_sup import (
    LIBELLE_HS_DECLAREES,
    LIBELLE_HS_DECLAREES_50,
    est_declaration_bulletin,
)

pytestmark = pytest.mark.unit


def test_seuls_les_deux_libelles_du_bulletin_sont_une_declaration_bulletin():
    assert est_declaration_bulletin({"name": LIBELLE_HS_DECLAREES, "payroll_quantity": 0})
    assert est_declaration_bulletin({"name": LIBELLE_HS_DECLAREES_50, "payroll_quantity": 2})
    assert not est_declaration_bulletin({"name": "Heures supplementaires conjoncturelles"})
    assert not est_declaration_bulletin(None)


def test_la_mention_dit_les_heures_retenues_et_celles_du_planning():
    bulletin = {"heures_sup_declarees": {"hs25": 4.0, "hs50": 0.0, "planning": 6.5}}
    assert mention_heures_sup_declarees(bulletin) == (
        "Heures supplémentaires déclarées au bulletin : 4 h à 25 %, 0 h à 50 % "
        "(le planning en donnait 6,5 h)."
    )


def test_pas_de_mention_sans_declaration():
    assert mention_heures_sup_declarees({}) is None


def test_la_mention_de_la_compensation_suffit_quand_elle_porte_deja_les_heures():
    bulletin = {
        "heures_sup_declarees": {"hs25": 4.0, "hs50": 0.0, "planning": 6.0},
        "compensation_semaines": {"heures_saisies": {"hs25": 4.0, "hs50": 0.0}, "mention": "…"},
    }
    assert mention_heures_sup_declarees(bulletin) is None
