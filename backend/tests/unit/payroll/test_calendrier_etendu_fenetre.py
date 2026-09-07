"""Fenêtre d'arrêté des variables — pavage via `creer_calendrier_etendu`.

Un événement de paie ne vit que dans le JSON de son mois civil
(`evenements_paie/MM.json`) ; c'est la période de paie qui décide du bulletin
auquel il appartient. Ces tests verrouillent le mécanisme qui rend l'arrêté à
l'avant-dernier vendredi correct de bout en bout : la queue de M-1 entre dans
le bulletin de M, la queue de M est reportée sur M+1 — ni trou, ni double
compte. Les fenêtres utilisées sont celles que fige
`test_domain.py::TestArreteAvantDernierVendredi`.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from app.modules.payroll.documents.payslip_run_common import creer_calendrier_etendu

pytestmark = pytest.mark.unit


def _ecrire_evenements(chemin_employe: Path, mois: int, evenements: list) -> None:
    dossier = chemin_employe / "evenements_paie"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / f"{mois:02d}.json").write_text(
        json.dumps({"calendrier_analyse": evenements}), encoding="utf-8"
    )


# Les événements agrégés par l'analyzer ne portent ni `mois` ni `annee` : la
# date vient du nom de fichier (06.json chargé pour juin, etc.). Les fixtures
# reproduisent volontairement cette forme minimale.
def test_juillet_prend_la_queue_de_juin_et_reporte_la_fin_juillet(tmp_path):
    # Colorplast (4, -2) : bulletin de juillet 2026 = 22/06 → 26/07 (S26→S30).
    _ecrire_evenements(
        tmp_path,
        6,
        [
            {"jour": 19, "type": "travail_hs25", "heures": 2.0},  # ≤ arrêté de juin → paie de juin
            {"jour": 26, "type": "travail_hs25", "heures": 3.0},  # S26 → paie de juillet
        ],
    )
    _ecrire_evenements(
        tmp_path,
        7,
        [
            {"jour": 24, "type": "travail_hs50", "heures": 1.0},  # S30 → paie de juillet
            {"jour": 31, "type": "travail_hs25", "heures": 4.0},  # après l'arrêté → paie d'août
        ],
    )

    calendrier = creer_calendrier_etendu(tmp_path, date(2026, 6, 22), date(2026, 7, 26))

    assert [(ev["date_complete"], ev["type"]) for ev in calendrier] == [
        ("2026-06-26", "travail_hs25"),
        ("2026-07-24", "travail_hs50"),
    ]


def test_aout_recupere_la_fin_juillet_une_seule_fois(tmp_path):
    # Fenêtre d'août 2026 = 27/07 → 23/08 : l'événement du 31/07 exclu du
    # bulletin de juillet y entre, sans être doublé par le fichier d'août.
    _ecrire_evenements(
        tmp_path, 7, [{"jour": 31, "type": "travail_hs25", "heures": 4.0}]
    )
    _ecrire_evenements(
        tmp_path, 8, [{"jour": 21, "type": "travail_hs25", "heures": 2.0}]
    )

    calendrier = creer_calendrier_etendu(tmp_path, date(2026, 7, 27), date(2026, 8, 23))

    assert [(ev["date_complete"], ev["heures"]) for ev in calendrier] == [
        ("2026-07-31", 4.0),
        ("2026-08-21", 2.0),
    ]


def test_janvier_traverse_le_changement_d_annee(tmp_path):
    # Fenêtre de janvier 2027 = 21/12/2026 → 24/01/2027 : 12.json est chargé
    # avec l'année du mois couvert (2026), pas celle du mois de paie — deux
    # événements au même quantième ne se confondent pas.
    _ecrire_evenements(
        tmp_path, 12, [{"jour": 22, "type": "travail_hs25", "heures": 2.0}]
    )
    _ecrire_evenements(
        tmp_path, 1, [{"jour": 22, "type": "travail_hs25", "heures": 1.0}]
    )

    calendrier = creer_calendrier_etendu(
        tmp_path, date(2026, 12, 21), date(2027, 1, 24)
    )

    assert [(ev["date_complete"], ev["heures"]) for ev in calendrier] == [
        ("2026-12-22", 2.0),
        ("2027-01-22", 1.0),
    ]
