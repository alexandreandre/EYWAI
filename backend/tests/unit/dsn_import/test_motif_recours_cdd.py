"""R-103 : le motif de recours d'un CDD (S21.G00.40.021) se lit à l'import.

La DSN du cabinet le porte (accroissement temporaire d'activité, remplacement…). L'import le
perdait : le CDD importé n'avait plus de motif, la DSN suivante partait sans, et la fiche ne
pouvait pas dire si la prime de précarité est due (art. L1243-10, 1°).
"""

from app.modules.dsn_import.application.mapping import map_employee_payload
from app.modules.dsn_import.domain.model import ParsedDsnSet
from app.modules.dsn_import.domain.parser import parse_dsn_content
from app.modules.payroll.engine.motif_recours import motif_recours_cdd

_ENTETE = """S10.G00.00.001,'CEGID'
S10.G00.00.002,'TEST'
S10.G00.00.003,'01'
S10.G00.00.006,'01'
S20.G00.05.001,'11'
S20.G00.05.005,'01062026'
S21.G00.06.001,'498610351'
S21.G00.06.003,'2229A'
S21.G00.11.001,'49861035100013'
S21.G00.30.001,'1800175304789'
S21.G00.30.002,'NOM'
S21.G00.30.004,'Prenom'
S21.G00.30.005,'01'
S21.G00.30.006,'20012007'
S21.G00.40.001,'22062026'
S21.G00.40.002,'06'
S21.G00.40.003,'04'
S21.G00.40.006,'Operateur'
S21.G00.40.007,'02'
S21.G00.40.009,'00004'
S21.G00.40.010,'31072026'
S21.G00.40.017,'0292'
"""


def _payload(lignes_motif: str):
    dsn = parse_dsn_content((_ENTETE + lignes_motif).encode("latin-1"), file_name="test.dsn")
    etab = list(ParsedDsnSet(files=[dsn]).etablissements_by_siret().values())[0]
    contrat_individu = etab.individus[0]
    return map_employee_payload(contrat_individu, etab, "49861035100013"), contrat_individu.contrats[0]


def test_le_parseur_garde_le_motif_de_recours():
    _, contrat = _payload("S21.G00.40.021,'02'\n")
    assert contrat.rubriques["S21.G00.40.021"] == "02"


def test_le_motif_arrive_sur_la_fiche_et_se_lit_comme_a_l_export():
    payload, _ = _payload("S21.G00.40.021,'03'\n")
    classification = payload["classification_conventionnelle"]
    assert classification["motif_recours"] == "03"
    assert motif_recours_cdd(classification, {}) == "03"


def test_sans_rubrique_la_fiche_ne_porte_pas_de_motif():
    payload, _ = _payload("")
    assert "motif_recours" not in payload["classification_conventionnelle"]
