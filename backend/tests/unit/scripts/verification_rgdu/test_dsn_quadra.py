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


# Cas réel le plus courant (ex. data/mbc/dsn/2026-03.dsn, lignes 3754-3769) : avant la
# vraie base 03 du mois, Quadra déclare une base 03 vide pour la période du mois
# précédent (assiette 0.00, sans bloc 79 ni 81). Deux individus fictifs, le second
# n'hérite de rien du premier.
DSN_PERIODE_VIDE = (
    "S21.G00.30.001,'1888888888888'\r\nS21.G00.30.002,'DUPONT'\r\nS21.G00.30.004,'Marc'\r\n"
    "S21.G00.78.001,'03'\r\nS21.G00.78.002,'01022026'\r\nS21.G00.78.003,'28022026'\r\nS21.G00.78.004,'0.00'\r\n"
    "S21.G00.78.001,'03'\r\nS21.G00.78.002,'01032026'\r\nS21.G00.78.003,'31032026'\r\nS21.G00.78.004,'2260.21'\r\n"
    "S21.G00.79.001,'01'\r\nS21.G00.79.004,'1898.02'\r\nS21.G00.79.001,'04'\r\nS21.G00.79.004,'46.86'\r\n"
    "S21.G00.81.001,'018'\r\nS21.G00.81.003,'2260.21'\r\nS21.G00.81.004,'-492.50'\r\n"
    "S21.G00.81.001,'106'\r\nS21.G00.81.003,'2260.21'\r\nS21.G00.81.004,'-87.50'\r\n"
    "S21.G00.30.001,'1777777777777'\r\nS21.G00.30.002,'MARTIN'\r\nS21.G00.30.004,'Sophie'\r\n"
    "S21.G00.78.001,'03'\r\nS21.G00.78.002,'01032026'\r\nS21.G00.78.003,'31032026'\r\nS21.G00.78.004,'1900.00'\r\n"
    "S21.G00.79.001,'01'\r\nS21.G00.79.004,'1823.03'\r\n"
    "S21.G00.81.001,'018'\r\nS21.G00.81.003,'1900.00'\r\nS21.G00.81.004,'-300.00'\r\n"
)


def test_base_03_vide_du_mois_precedent_ne_contamine_pas_la_suivante(tmp_path):
    f = tmp_path / "2026-03.dsn"
    f.write_bytes(DSN_PERIODE_VIDE.encode("latin-1"))
    bases = lire_dsn(f)
    assert len(bases) == 3

    fevrier, mars_marc, mars_sophie = bases

    assert fevrier.nir == "1888888888888"
    assert (fevrier.debut, fevrier.fin) == (date(2026, 2, 1), date(2026, 2, 28))
    assert fevrier.assiette == 0.0
    assert fevrier.smic_retenu is None
    assert fevrier.reduction == 0.0

    assert mars_marc.nir == "1888888888888"
    assert (mars_marc.debut, mars_marc.fin) == (date(2026, 3, 1), date(2026, 3, 31))
    assert mars_marc.smic_retenu == 1898.02
    assert mars_marc.reduction == 580.00

    assert mars_sophie.nir == "1777777777777"
    assert mars_sophie.smic_retenu == 1823.03
    assert mars_sophie.montant_018 == -300.00
    assert mars_sophie.montant_106 == 0.0
    assert mars_sophie.reduction == 300.00
