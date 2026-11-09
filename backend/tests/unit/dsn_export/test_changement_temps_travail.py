"""R-462 : le passage d'un forfait jours à 35 h se déclare au bloc « Changements Contrat ».

Cahier technique 2026.1.2 : valeur avant changement (p. 215), date et profondeur obligatoires
(p. 26), une modalité par bloc (p. 25 : « différents blocs changement, et ce même si plusieurs
changements sont concomitants »). Cas à venir : les forfaits de Zone 404 sous le plancher Syntec.
"""

from __future__ import annotations

import copy
from datetime import date

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.changement_temps_travail import (
    CLE,
    appliquer_changement_temps_travail as ap,
    avis_changements_temps_travail,
    blocs_changement_temps_travail as blocs,
    temps_du_mois,
    valeurs_dsn,
)
from app.modules.dsn_export.domain.writer import serialize_dsn_file
from tests.unit.dsn_export.test_changement_pcs import _sample_company, _sample_employee_row

RIEN: frozenset[str] = frozenset()
FORFAIT = {"is_forfait_jour": True, "is_temps_partiel": False, "duree_hebdomadaire": 35.0, "classification_conventionnelle": {"pcs": "389a"}}
NOTE = {
    "date": "2026-11-01",
    "anciens": {"S21.G00.41.006": "20", "S21.G00.41.007": "21.47", "S21.G00.41.022": "21.47"},
}
DEBUT = "2020-01-01"


def _ap(avant, apres, *, jour=date(2026, 11, 5), import_=False, deposees=RIEN, debut=DEBUT):
    return ap(
        avant, apres, aujourd_hui=jour, depuis_import=import_, periodes_declarees=deposees,
        debut_contrat=debut, quotite_forfait_jours="21.47",
    )


def test_le_forfait_passe_a_35_h_garde_les_anciennes_valeurs_au_premier_du_mois():
    assert _ap(FORFAIT, {**FORFAIT, "is_forfait_jour": False})[CLE] == NOTE


def test_rien_a_noter_si_rien_ne_change():
    assert CLE not in _ap(FORFAIT, dict(FORFAIT))


def test_l_import_ne_note_rien_mais_garde_ce_qui_attend():
    apres = {**FORFAIT, "is_forfait_jour": False}
    assert CLE not in _ap(FORFAIT, apres, import_=True)
    avec_note = {**FORFAIT, "classification_conventionnelle": {"pcs": "389a", CLE: NOTE}}
    assert _ap(avec_note, avec_note, import_=True)[CLE] == NOTE


def test_retour_a_l_origine_avant_depot_retire_la_note():
    avant = {**FORFAIT, "is_forfait_jour": False, "classification_conventionnelle": {"pcs": "389a", CLE: NOTE}}
    assert CLE not in _ap(avant, {**FORFAIT, "classification_conventionnelle": {"pcs": "389a", CLE: NOTE}})


def test_un_contrat_commence_ce_mois_ci_n_a_rien_a_declarer():
    assert CLE not in _ap(FORFAIT, {**FORFAIT, "is_forfait_jour": False}, debut="2026-11-03")


def test_valeurs_dsn_forfait_et_heures():
    assert valeurs_dsn(FORFAIT, "21.47") == {
        "S21.G00.41.006": "20", "S21.G00.41.007": "21.47",
        "S21.G00.41.008": "10", "S21.G00.41.022": "21.47",
    }
    assert valeurs_dsn({**FORFAIT, "is_forfait_jour": False}, "21.47")["S21.G00.41.006"] == "10"


def test_chaque_modalite_a_son_bloc_avec_date_et_profondeur():
    r = blocs({CLE: NOTE}, "2026-11", RIEN, DEBUT)
    assert [x.rubriques for x in r] == [
        {"S21.G00.41.001": "01112026", "S21.G00.41.006": "20", "S21.G00.41.028": "01112026"},
        {"S21.G00.41.001": "01112026", "S21.G00.41.007": "21.47", "S21.G00.41.028": "01112026"},
        {"S21.G00.41.001": "01112026", "S21.G00.41.022": "21.47", "S21.G00.41.028": "01112026"},
    ]


def test_le_bloc_ne_part_qu_une_fois():
    assert blocs({CLE: NOTE}, "2026-11", {"2026-11"}, DEBUT)
    assert blocs({CLE: NOTE}, "2026-12", {"2026-11"}, DEBUT) == []


def test_un_mois_avant_le_changement_declare_les_anciennes_valeurs():
    assert temps_du_mois({CLE: NOTE}, "2026-10", ("10", "151.67", "151.67", "10")) == ("20", "21.47", "21.47", "10")
    assert temps_du_mois({CLE: NOTE}, "2026-11", ("10", "151.67", "151.67", "10")) == ("10", "151.67", "151.67", "10")


def _ligne():
    ligne = copy.deepcopy(_sample_employee_row())
    ligne["employee"].update(
        is_forfait_jour=False, is_temps_partiel=False, duree_hebdomadaire=35.0,
        classification_conventionnelle={"pcs": "389a", "idcc": "1486", CLE: NOTE},
    )
    return ligne


def test_le_fichier_porte_un_bloc_par_modalite_juste_apres_le_contrat():
    dsn, _ = build_parsed_dsn_from_payroll(_sample_company(), [_ligne()], "2026-11")
    lignes = serialize_dsn_file(dsn).splitlines()
    assert sum(l.startswith("S21.G00.41.001,'01112026'") for l in lignes) == 3
    i = lignes.index("S21.G00.41.006,'20'")
    assert lignes[i - 1] == "S21.G00.41.001,'01112026'"
    assert lignes[i + 1] == "S21.G00.41.028,'01112026'"
    # L'ordre du cahier : la profondeur de chaque bloc se ferme avant le bloc suivant.
    assert lignes[i + 2] == "S21.G00.41.001,'01112026'"
    # Le contrat déclare les heures du mois.
    assert "S21.G00.40.011,'10'" in lignes


def test_avis_de_l_apercu():
    assert avis_changements_temps_travail([_ligne()], "2026-11", RIEN) == (
        "Temps de travail changé pour 1 salarié : la DSN déclare les anciennes valeurs "
        "(bloc Changements Contrat, S21.G00.41)."
    )
    assert avis_changements_temps_travail([_sample_employee_row()], "2026-11", RIEN) is None
