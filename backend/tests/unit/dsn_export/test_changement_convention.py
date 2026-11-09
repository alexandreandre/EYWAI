"""R-462 : le changement de convention collective au bloc « Changements Contrat » (S21.G00.41.011).

Cas d'origine : Zone 404 passe de « sans convention » (9999) à Syntec (1486) en novembre 2026.
Cahier technique 2026.1.2 : valeur avant changement (p. 215), rubrique S21.G00.41.011 valeurs de
la table IDCC, 9999 admis (« sans convention collective »), date de la modification obligatoire
(p. 216, CCH-12 à 15), une modalité par bloc (p. 25).
"""

from __future__ import annotations

from datetime import date

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.changement_convention import (
    CLE,
    appliquer_changement_convention as ap,
    avis_changements_convention,
    bloc_changement_convention as b,
    idcc_du_mois,
)
from app.modules.dsn_export.domain.writer import serialize_dsn_file
from tests.unit.dsn_export.test_changement_pcs import _sample_company, _sample_employee_row

RIEN: frozenset[str] = frozenset()
DEBUT = "2020-01-01"
NOTE = {"ancien": "9999", "date": "2026-11-01"}
JOUR = date(2026, 11, 5)


def _ap(avant, apres, *, jour=JOUR, import_=False, deposees=RIEN, debut=DEBUT):
    return ap(avant, apres, aujourd_hui=jour, depuis_import=import_, periodes_declarees=deposees, debut_contrat=debut)


def test_changement_note_l_ancienne_convention_au_premier_du_mois():
    assert _ap({"idcc": "9999"}, {"idcc": "1486"})[CLE] == NOTE


def test_idcc_normalise_et_rien_a_noter_si_inchange():
    assert CLE not in _ap({"idcc": "292"}, {"idcc": "0292"})
    assert _ap({"idcc": "292"}, {"idcc": "1486"})[CLE]["ancien"] == "0292"


def test_import_dsn_ne_note_rien_mais_garde_ce_qui_attend():
    apres = _ap({"idcc": "9999", CLE: NOTE}, {"idcc": "1486"}, import_=True)
    assert apres[CLE] == NOTE
    assert CLE not in _ap({"idcc": "9999"}, {"idcc": "1486"}, import_=True)


def test_le_client_ne_peut_rien_poser_et_la_note_survit_a_une_fiche_inchangee():
    assert CLE not in _ap({"idcc": "1486"}, {"idcc": "1486", CLE: {"ancien": "0000", "date": "2020-01-01"}})
    assert _ap({"idcc": "1486", CLE: NOTE}, {"idcc": "1486"})[CLE] == NOTE


def test_contrat_du_mois_rien_a_noter():
    assert CLE not in _ap({"idcc": "9999"}, {"idcc": "1486"}, debut="2026-11-03")


def test_deux_changements_avant_tout_depot_gardent_l_ancien_d_origine():
    resultat = _ap({"idcc": "1486", CLE: NOTE}, {"idcc": "0016"})
    assert resultat[CLE] == {"ancien": "9999", "date": "2026-11-01"}
    # Retour à l'ancienne convention avant le dépôt : aucun changement à déclarer.
    assert CLE not in _ap({"idcc": "1486", CLE: NOTE}, {"idcc": "9999"})


def test_changement_apres_depot_du_mois_note_le_mois_courant():
    apres = _ap({"idcc": "1486", CLE: NOTE}, {"idcc": "0016"}, deposees=frozenset({"2026-11"}))
    assert apres[CLE] == {"ancien": "1486", "date": "2026-11-01"}


def test_idcc_du_mois_avant_le_changement_est_l_ancien():
    classification = {"idcc": "1486", CLE: NOTE}
    assert idcc_du_mois(classification, "1486", "2026-10") == "9999"
    assert idcc_du_mois(classification, "1486", "2026-11") == "1486"
    assert idcc_du_mois({"idcc": "1486"}, "1486", "2026-10") == "1486"


def test_bloc_du_mois_du_changement():
    bloc = b({"idcc": "1486", CLE: NOTE}, "2026-11", RIEN, DEBUT)
    assert bloc.date_modification == "01112026"
    assert bloc.rubriques == {
        "S21.G00.41.001": "01112026",
        "S21.G00.41.011": "9999",
        "S21.G00.41.028": "01112026",
    }


def test_bloc_parti_une_fois_seulement_et_jamais_avant_le_contrat():
    classification = {"idcc": "1486", CLE: NOTE}
    assert b(classification, "2026-10", RIEN, DEBUT) is None
    assert b(classification, "2026-12", RIEN, DEBUT) is not None  # novembre pas encore parti
    assert b(classification, "2026-12", frozenset({"2026-11"}), DEBUT) is None
    assert b(classification, "2026-11", RIEN, "2026-11-01") is None


def test_avis_de_l_apercu():
    classification = {"idcc": "1486", CLE: NOTE}
    rows = [{"employee": {"classification_conventionnelle": classification, "hire_date": DEBUT}}]
    avis = avis_changements_convention(rows, "2026-11", RIEN)
    assert "Convention collective changée pour 1 salarié" in avis
    assert avis_changements_convention(rows, "2026-10", RIEN) is None


def test_la_dsn_declare_l_ancienne_convention_dans_le_bloc_41():
    row = _sample_employee_row()
    row["employee"]["classification_conventionnelle"] = {"pcs": "389a", "idcc": "1486", CLE: NOTE}
    dsn_file, _ = build_parsed_dsn_from_payroll(
        _sample_company(), [row], "2026-11", essai=True, periodes_declarees=frozenset()
    )
    texte = serialize_dsn_file(dsn_file)
    lignes = texte.splitlines()
    i = lignes.index("S21.G00.41.011,'9999'")
    assert lignes[i - 1] == "S21.G00.41.001,'01112026'"
    assert lignes[i + 1] == "S21.G00.41.028,'01112026'"
    assert "S21.G00.40.017,'1486'" in lignes


def test_la_dsn_du_mois_d_avant_garde_l_ancienne_convention_sans_bloc():
    row = _sample_employee_row()
    row["employee"]["classification_conventionnelle"] = {"pcs": "389a", "idcc": "1486", CLE: NOTE}
    dsn_file, _ = build_parsed_dsn_from_payroll(
        _sample_company(), [row], "2026-10", essai=True, periodes_declarees=frozenset()
    )
    lignes = serialize_dsn_file(dsn_file).splitlines()
    assert "S21.G00.40.017,'9999'" in lignes
    assert "S21.G00.41.011,'9999'" not in lignes
