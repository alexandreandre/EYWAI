"""Chaque écriture d'un bulletin calculé le date (`generated_at`).

La colonne ne valait que la date de création : l'upsert d'une régénération ne
la touchait pas. Un bulletin recalculé après un export ne rendait donc pas cet
export « à refaire ». Le générateur au temps passé est vérifié pour de vrai
dans `test_pdf_du_bulletin.py` ; le forfait jours et la régularisation de
participation écrivent leur ligne de la même façon. Les écritures qui ne
touchent pas les montants (acquittement d'alerte, marque de notification, note
du PDF, validation) ne datent rien : elles ne rendent aucun export faux.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

APP = Path(__file__).resolve().parents[3] / "app"
ECRIVAINS = (
    APP / "modules" / "payroll" / "documents" / "payslip_generator.py",
    APP / "modules" / "payroll" / "documents" / "payslip_generator_forfait.py",
    APP / "modules" / "participation" / "application" / "regularisation_bulletin_service.py",
)


@pytest.mark.parametrize("chemin", ECRIVAINS, ids=lambda c: c.name)
def test_l_upsert_du_bulletin_porte_la_date_du_calcul(chemin):
    source = chemin.read_text(encoding="utf-8")
    debut = source.index(".upsert(")
    upsert = source[debut : source.index("on_conflict=", debut)]

    assert re.search(r'"generated_at": datetime\.now\(timezone\.utc\)\.isoformat\(\)', upsert)
