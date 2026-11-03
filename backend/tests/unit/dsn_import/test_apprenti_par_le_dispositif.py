"""Un apprenti déclaré en DSN arrive en apprentissage sur sa fiche, pas en CDD ordinaire.

La DSN déclare un contrat d'apprentissage en CDD (nature 02, S21.G00.40.007) : ce qui
le distingue est le dispositif de politique publique (S21.G00.40.008 = 64, 65, 66 ou
81), comme Martine l'écrit elle-même à l'export. L'import lisait la seule nature : les
trois apprentis de MAJI embauchés en septembre 2026 seraient arrivés en « CDD », donc
payés sans le régime apprenti (cotisations, impôt) et avec une prime de fin de contrat.
"""

import pytest

from app.modules.dsn_import.application.mapping import map_employee_payload
from app.modules.dsn_import.domain.parser import parse_dsn_content

pytestmark = pytest.mark.unit

_DSN = """S10.G00.00.001,'CEGID'
S10.G00.00.002,'TEST'
S10.G00.00.003,'01'
S10.G00.00.006,'01'
S20.G00.05.001,'01'
S20.G00.05.005,'01092026'
S21.G00.06.001,'498610351'
S21.G00.06.003,'2229A'
S21.G00.11.001,'49861035100013'
S21.G00.30.001,'2000175304789'
S21.G00.30.002,'ESSAI'
S21.G00.30.004,'Camille'
S21.G00.30.005,'02'
S21.G00.30.006,'20012007'
S21.G00.40.001,'01092026'
S21.G00.40.002,'06'
S21.G00.40.003,'04'
S21.G00.40.006,'Controleur de gestion - APPRENTI'
S21.G00.40.007,'02'
S21.G00.40.008,'{dispositif}'
S21.G00.40.009,'00000'
S21.G00.40.010,'31082028'
S21.G00.40.017,'9999'
"""


def _payload(dispositif: str) -> dict:
    dsn = parse_dsn_content(_DSN.format(dispositif=dispositif).encode("latin-1"), file_name="test.dsn")
    from app.modules.dsn_import.domain.model import ParsedDsnSet

    etab = list(ParsedDsnSet(files=[dsn]).etablissements_by_siret().values())[0]
    return map_employee_payload(etab.individus[0], etab, "49861035100013")


@pytest.mark.parametrize("dispositif", ["64", "65", "66", "81"])
def test_un_cdd_avec_un_dispositif_d_apprentissage_est_un_apprentissage(dispositif):
    payload = _payload(dispositif)
    assert payload["contract_type"] == "apprentissage"
    assert payload["date_debut_execution"] == "2026-09-01"


def test_un_cdd_sans_dispositif_reste_un_cdd():
    assert _payload("99")["contract_type"] == "CDD"
