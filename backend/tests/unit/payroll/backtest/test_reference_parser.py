"""Tests parseur référence Cegid."""

import pytest

from app.modules.payroll.backtest.reference_parser import parse_cegid_block, parse_cegid_text
from tests.unit.payroll.backtest.fixtures import DUMAREL_PAGE1, DUMAREL_PAGE2

pytestmark = pytest.mark.unit


class TestReferenceParser:
    def test_parse_dumarel_block(self):
        text = DUMAREL_PAGE1 + DUMAREL_PAGE2
        ref = parse_cegid_block("DUMAREL", text)
        assert ref.matricule == "DUMAREL"
        assert ref.salaire_brut == 2952.34
        assert ref.net_imposable == 5600.16
        assert ref.montant_net_social == 5479.53
        assert ref.net_a_payer == 5289.12
        assert ref.pas_montant == 190.41
        assert ref.pas_taux == 3.40
        assert ref.coefficient == 720
        assert ref.cout_total_employeur == 7207.57

    def test_parse_cegid_text_groups_matricule(self):
        text = DUMAREL_PAGE1 + "\n\f\n" + DUMAREL_PAGE2
        refs = parse_cegid_text(text)
        assert "DUMAREL" in refs
        assert refs["DUMAREL"].salaire_brut == 2952.34

    def test_rubriques_extracted(self):
        ref = parse_cegid_block("DUMAREL", DUMAREL_PAGE1)
        labels = [r.libelle.lower() for r in ref.rubriques]
        assert any("salaire de base" in l for l in labels)
        assert any("prime exceptionnelle" in l for l in labels)
