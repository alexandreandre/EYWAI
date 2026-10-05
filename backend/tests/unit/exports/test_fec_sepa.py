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


ECRITURE_NET = {
    "date_ecriture": "2026-09-30",
    "journal": "PAI",
    "compte_comptable": "42100000",
    "libelle": "Net à payer Septembre 2026",
    "debit": 0.0,
    "credit": 13159.38,
    "periode_paie": "2026-09",
    "reference_export": "OD_PAIE_2026-09",
}


class TestFichierQuadra:
    """Fichier d'entrée ASCII de QuadraCOMPTA, enregistrement M (spécification
    Cegid) : compte en 2, journal en 10, folio, date JJMMAA, sens en 42,
    montant en centimes signé en 43. Le format précédent (journal en tête,
    date AAAAMMJJ, débit et crédit en euros) ne s'importait pas."""

    def test_ligne_aux_positions_de_la_specification(self):
        from app.modules.exports.infrastructure.export_formats_cabinet import (
            _format_quadra_line,
        )

        ligne = _format_quadra_line(ECRITURE_NET)
        assert len(ligne) == 146
        assert ligne[0] == "M"
        assert ligne[1:9] == "42100000"
        assert ligne[9:11] == "PA"
        assert ligne[11:14] == "000"
        assert ligne[14:20] == "300926"
        assert ligne[21:41] == "Salaire de 09/2026  "
        assert ligne[41] == "C"
        assert ligne[42:55] == "+000001315938"
        assert ligne[99:107] == "PAIE0926"
        assert ligne[107:110] == "EUR"
        assert ligne[110:113] == "PAI"
        assert ligne[116:146] == "Net à payer Septembre 2026".ljust(30)

    def test_compte_court_complete_a_huit_chiffres(self):
        from app.modules.exports.infrastructure.export_formats_cabinet import (
            _format_quadra_line,
        )

        ligne = _format_quadra_line({**ECRITURE_NET, "compte_comptable": "641000", "debit": 1.0, "credit": 0.0})
        assert ligne[1:9] == "64100000"
        assert ligne[41] == "D"
        assert ligne[42:55] == "+000000000100"

    def test_compte_trop_long_refuse_plutot_que_tronque(self):
        from app.modules.exports.infrastructure.export_formats_cabinet import (
            _format_quadra_line,
        )

        with pytest.raises(ValueError, match="8 caractères"):
            _format_quadra_line({**ECRITURE_NET, "compte_comptable": "421000001"})

    def test_fichier_relu_au_centime(self, monkeypatch):
        from app.modules.exports.infrastructure import export_formats_cabinet as cabinet

        ecritures = [
            {**ECRITURE_NET, "compte_comptable": "641000", "libelle": "Salaires Septembre 2026",
             "debit": 15944.12, "credit": 0.0},
            {**ECRITURE_NET, "credit": 13159.38},
            {**ECRITURE_NET, "compte_comptable": "431000", "libelle": "Dette URSSAF — Septembre 2026",
             "credit": 2784.74},
        ]
        monkeypatch.setattr(
            cabinet,
            "build_payroll_ledger",
            lambda *a, **k: (ecritures, {"equilibre": True, "anomalies": []}, {}),
        )
        contenu = cabinet.generate_cabinet_quadra_export("societe", "2026-09")
        lignes = contenu.decode("latin-1").split("\r\n")
        assert lignes[-1] == ""
        debit = credit = 0
        for ligne in lignes[:-1]:
            centimes = int(ligne[42:55])
            if ligne[41] == "D":
                debit += centimes
            else:
                credit += centimes
        assert debit == credit == 1594412


class TestFecConforme:
    """BOI-CF-IOR-60-40-20 : montants à la virgule décimale (« 96,28 »,
    « 0,00 ») ; CompteLib est l'intitulé du compte, pas le libellé de
    l'écriture."""

    def _rows(self, monkeypatch):
        from app.modules.exports.infrastructure import export_fec

        ecritures = [
            {**ECRITURE_NET, "compte_comptable": "641000", "libelle": "Salaires Septembre 2026",
             "compte_lib": "Salaires", "debit": 100.5, "credit": 0.0},
            {**ECRITURE_NET, "compte_comptable": "421000", "libelle": "Net à payer Septembre 2026",
             "compte_lib": "Net à payer", "credit": 80.5},
            {**ECRITURE_NET, "compte_comptable": "421000", "libelle": "Régularisations du net Septembre 2026",
             "compte_lib": "Régularisations du net", "credit": 20.0},
        ]
        monkeypatch.setattr(
            export_fec,
            "build_payroll_ledger",
            lambda *a, **k: (ecritures, {"equilibre": True, "anomalies": []}, {}),
        )
        rows, _, _ = export_fec.build_fec_rows("societe", "2026-09")
        return rows

    def test_montants_a_la_virgule(self, monkeypatch):
        rows = self._rows(monkeypatch)
        assert rows[0]["Debit"] == "100,50"
        assert rows[0]["Credit"] == "0,00"

    def test_comptelib_intitule_du_compte_identique_sur_toutes_ses_lignes(self, monkeypatch):
        rows = self._rows(monkeypatch)
        assert rows[0]["CompteLib"] == "Salaires"
        assert {r["CompteLib"] for r in rows if r["CompteNum"] == "421000"} == {"Net à payer"}
        assert rows[2]["EcritureLib"] == "Régularisations du net Septembre 2026"
