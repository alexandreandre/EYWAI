"""Tests FEC et SEPA."""

import xml.etree.ElementTree as ET

import pytest

from app.modules.exports.infrastructure.export_fec import FEC_COLUMNS, generate_fec_export
from app.modules.exports.infrastructure.export_sepa import NS, generate_sepa_pain001

pytestmark = pytest.mark.unit


class TestFecExport:
    def test_fec_columns_header(self, monkeypatch):
        monkeypatch.setattr(
            "app.modules.exports.infrastructure.export_fec.build_fec_rows",
            lambda *a, **k: (
                [{"JournalCode": "OD", **{c: "" for c in FEC_COLUMNS[1:]}}],
                {"equilibre": True},
                None,
            ),
        )
        content = generate_fec_export("co-1", "2026-06")
        header = content.decode("utf-8").split("\n")[0]
        assert header == "\t".join(FEC_COLUMNS)

    def test_fec_tab_separated(self, monkeypatch):
        monkeypatch.setattr(
            "app.modules.exports.infrastructure.export_fec.build_fec_rows",
            lambda *a, **k: (
                [{"JournalCode": "OD", **{c: "" for c in FEC_COLUMNS[1:]}}],
                {"equilibre": True},
                None,
            ),
        )
        content = generate_fec_export("co-1", "2026-06")
        lines = [l for l in content.decode("utf-8").split("\n") if l.strip()]
        assert len(lines) >= 1
        assert "\t" in lines[0]


class TestSepaExport:
    def test_sepa_xml_structure(self, monkeypatch):
        monkeypatch.setattr(
            "app.modules.exports.infrastructure.export_sepa.get_paiement_salaires_data",
            lambda *a, **k: (
                [
                    {
                        "Statut_controle": "OK",
                        "IBAN": "FR7630001007941234567890185",
                        "Montant": 1500.0,
                        "Nom": "Dupont",
                        "Reference": "REF1",
                    }
                ],
                {},
                [],
                [],
            ),
        )
        monkeypatch.setattr(
            "app.modules.exports.infrastructure.export_sepa.validate_iban",
            lambda iban: iban.startswith("FR"),
        )
        xml_bytes = generate_sepa_pain001("co-1", "2026-06", execution_date="2026-06-30")
        root = ET.fromstring(xml_bytes)
        assert root.tag == f"{{{NS}}}Document"
        assert root.find(f".//{{{NS}}}ReqdExctnDt") is not None
        assert root.find(f".//{{{NS}}}CtrlSum") is not None


class TestFormatCabinet:
    """Éléments relevés sur l'OD de paie du cabinet (période 10/2025)."""

    def test_reference_de_piece_au_format_du_cabinet(self):
        from app.modules.exports.infrastructure.export_formats_cabinet import (
            format_piece_reference,
        )

        assert format_piece_reference("2025-10") == "PAIE1025"
        assert format_piece_reference("2026-06") == "PAIE0626"

    def test_libelle_ecriture(self):
        from app.modules.exports.infrastructure.export_formats_cabinet import (
            format_libelle_ecriture,
        )

        assert format_libelle_ecriture("2025-10") == "Salaire de 10/2025"
        assert format_libelle_ecriture("2026-06") == "Salaire de 06/2026"
