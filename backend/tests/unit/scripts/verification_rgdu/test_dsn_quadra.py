"""Lecture du SMIC retenu et des codes 018 / 106 d'une DSN Quadra (latin-1, CRLF)."""
from datetime import date

import pytest

from scripts.verification_rgdu.dsn_quadra import lire_dsn

pytestmark = pytest.mark.unit

DSN = (
    "S20.G00.05.005,'01012026'\r\n"
    "S21.G00.30.001,'1999999999999'\r\nS21.G00.30.002,'ESSAI'\r\nS21.G00.30.004,'Léa'\r\n"
    "S21.G00.78.001,'02'\r\nS21.G00.78.002,'01012026'\r\nS21.G00.78.003,'31012026'\r\nS21.G00.78.004,'3023.40'\r\n"
    "S21.G00.81.001,'076'\r\nS21.G00.81.004,'400.00'\r\n"
    "S21.G00.78.001,'03'\r\nS21.G00.78.002,'01012026'\r\nS21.G00.78.003,'31012026'\r\nS21.G00.78.004,'3023.40'\r\n"
    "S21.G00.79.001,'01'\r\nS21.G00.79.004,'2277.75'\r\nS21.G00.79.001,'04'\r\nS21.G00.79.004,'29.23'\r\n"
    "S21.G00.81.001,'018'\r\nS21.G00.81.003,'3023.40'\r\nS21.G00.81.004,'-483.87'\r\n"
    "S21.G00.81.001,'106'\r\nS21.G00.81.003,'3023.40'\r\nS21.G00.81.004,'-86.04'\r\n"
    "S21.G00.81.001,'114'\r\nS21.G00.81.004,'-10.00'\r\n"
)


def test_une_base_03_donne_le_smic_retenu_et_la_reduction(tmp_path):
    f = tmp_path / "2026-01.dsn"
    f.write_bytes(DSN.encode("latin-1"))
    [b] = lire_dsn(f)
    assert (b.nir, b.nom, b.prenom) == ("1999999999999", "ESSAI", "Léa")
    assert (b.debut, b.fin) == (date(2026, 1, 1), date(2026, 1, 31))
    assert b.smic_retenu == 2277.75 and b.assiette == 3023.40
    assert b.reduction == 569.91
