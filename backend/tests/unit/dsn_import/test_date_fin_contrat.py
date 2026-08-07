"""La date de fin d'un CDD vient de S21.G00.40.010, pas de .003.

Le .003 est le « Code statut catégoriel Retraite Complémentaire obligatoire », un
code sur deux chiffres. Le lire comme une date rendait `None` sans bruit : tous
les CDD importés perdaient leur terme, donc l'alerte de fin de contrat aussi —
28 CDD actifs sur 32 en production le 7 août 2026.
"""

from app.modules.dsn_import.application.mapping import map_employee_payload
from app.modules.dsn_import.domain.parser import parse_dsn_content

pytest_plugins: list = []

# Bloc réel simplifié, repris de la DSN de juin de Comitech : un CDD du 22/06 au
# 31/07, avec .003 = '04' (statut retraite) et .010 = '31072026' (terme).
_DSN = """S10.G00.00.001,'CEGID'
S10.G00.00.002,'TEST'
S10.G00.00.003,'01'
S10.G00.00.006,'01'
S20.G00.05.001,'11'
S20.G00.05.005,'01062026'
S21.G00.06.001,'498610351'
S21.G00.06.003,'2229A'
S21.G00.11.001,'49861035100013'
S21.G00.30.001,'1070101034042'
S21.G00.30.002,'VUILLERMET'
S21.G00.30.004,'Sebastien'
S21.G00.30.005,'01'
S21.G00.30.006,'20012007'
S21.G00.40.001,'22062026'
S21.G00.40.002,'06'
S21.G00.40.003,'04'
S21.G00.40.006,'Operateur polyvalent'
S21.G00.40.007,'02'
S21.G00.40.009,'00004'
S21.G00.40.010,'31072026'
S21.G00.40.017,'0292'
"""


def _contrat():
    dsn = parse_dsn_content(_DSN.encode("latin-1"), file_name="test.dsn")
    etablissements = list(dsn.etablissements.values()) if hasattr(dsn, "etablissements") else []
    if not etablissements:
        from app.modules.dsn_import.domain.model import ParsedDsnSet

        etablissements = list(ParsedDsnSet(files=[dsn]).etablissements_by_siret().values())
    individu = etablissements[0].individus[0]
    return etablissements[0], individu, individu.contrats[0]


def test_la_date_de_fin_vient_de_la_rubrique_010():
    _, _, contrat = _contrat()
    assert contrat.date_fin == "31072026"


def test_le_statut_retraite_n_est_pas_pris_pour_une_date():
    """.003 vaut '04' : s'il alimentait date_fin, le terme serait perdu."""
    _, _, contrat = _contrat()
    assert contrat.date_fin != "04"


def test_le_terme_du_cdd_arrive_dans_la_fiche():
    etab, individu, _ = _contrat()
    payload = map_employee_payload(individu, etab, "49861035100013")
    assert payload["contract_end_date"] == "2026-07-31"
