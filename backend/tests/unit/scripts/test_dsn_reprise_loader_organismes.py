"""Le bloc 15 se reprend de la même DSN que les affiliations des salariés.

Les 70.013 des salariés désignent un contrat par son ordre 15.005. Si le bloc 15
vient d'une autre DSN que les affiliations, et que le cabinet a réordonné ses
contrats entre les deux, chaque salarié est déclaré sur le contrat d'un autre.
"""
from pathlib import Path

from scripts.dsn_reprise_loader import organismes_du_jeu

DSN_JUIN = """S21.G00.15.001,'1000'
S21.G00.15.002,'ORGA'
S21.G00.15.003,'DELEG'
S21.G00.15.004,'01'
S21.G00.15.005,'1'
S21.G00.15.001,'RF9'
S21.G00.15.002,'ORGB'
S21.G00.15.004,'01'
S21.G00.15.005,'2'
S21.G00.15.001,'0NF'
S21.G00.15.002,'ORGC'
S21.G00.15.004,'02'
S21.G00.15.005,'3'
S21.G00.70.012,'1'
S21.G00.70.013,'2'
"""

SETTINGS_MAI = """{"organismes_complementaires": [
 {"reference": "1000", "organisme": "ORGA", "delegataire": "DELEG", "nature": "01", "ordre": "1"},
 {"reference": "0NF", "organisme": "ORGC", "nature": "02", "ordre": "2"},
 {"reference": "RF9", "organisme": "ORGB", "nature": "02", "ordre": "3"}
]}"""


def _jeu(tmp_path: Path, avec_reference: bool = True) -> Path:
    jeu = tmp_path / "societe" / "2026-06"
    jeu.mkdir(parents=True)
    (jeu / "input.json").write_text("{}")
    if avec_reference:
        (jeu / "reference.dsn").write_text(DSN_JUIN, encoding="latin-1")
    (tmp_path / "societe" / "settings.json").write_text(SETTINGS_MAI)
    return jeu


def test_le_bloc_15_vient_de_la_dsn_du_jeu(tmp_path):
    organismes = organismes_du_jeu(_jeu(tmp_path))

    assert organismes == [
        {"reference": "1000", "organisme": "ORGA", "delegataire": "DELEG", "nature": "01", "ordre": "1"},
        {"reference": "RF9", "organisme": "ORGB", "nature": "01", "ordre": "2"},
        {"reference": "0NF", "organisme": "ORGC", "nature": "02", "ordre": "3"},
    ]


def test_sans_dsn_de_reference_rien_n_est_repris(tmp_path):
    # Le settings.json peut venir d'un autre mois : mieux vaut ne rien poser
    # qu'un ordre qui ne correspond pas aux affiliations.
    assert organismes_du_jeu(_jeu(tmp_path, avec_reference=False)) == []
