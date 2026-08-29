"""
Un congé validé par les RH doit être lu par la paie.

Deux écrivains, deux vocabulaires : la validation d'absence pose `conge` sur le
calendrier (`ABSENCE_TYPE_TO_CALENDAR_TYPE`), tandis que le moteur de paie ne
compte que les jours `conges_payes`. Un congé payé saisi dans l'outil n'est
donc ni travaillé ni en congé aux yeux du bulletin : il disparaît.

Mesuré le 26/08/2026 : **371 jours portent l'étiquette `conge`** dans les
calendriers du groupe, contre 899 en `conges_payes`. Chez MAJI (117 jours) et
Zone 404 (47), c'est la totalité.

Ce test relie les deux vocabulaires : ce que l'absence écrit, la paie doit
savoir le lire.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.shared.domain.absence_calendar import ABSENCE_TYPE_TO_CALENDAR_TYPE

RACINE_PAIE = Path(__file__).resolve().parents[3] / "app" / "modules" / "payroll"

#: Fichiers du moteur qui décident, à partir du type d'un jour, s'il est payé,
#: déduit ou compté comme du travail.
LECTEURS = (
    "documents/payslip_run_heures.py",
    "application/analyzer.py",
    "engine/temps_travail_mois.py",
)


def _types_lus_par_la_paie() -> set[str]:
    """Types de jour que le moteur compare explicitement dans son code."""
    lus: set[str] = set()
    for relatif in LECTEURS:
        chemin = RACINE_PAIE / relatif
        if not chemin.exists():  # pragma: no cover - fichier déplacé
            continue
        source = chemin.read_text(encoding="utf-8")
        # `type == "x"`, `type in ("x", "y")`, `.get("type") in [...]`
        for bloc in re.findall(r'type["\']?\s*\)?\s*(?:==|in)\s*([^\n]+)', source):
            lus.update(re.findall(r'["\']([a-z_]+)["\']', bloc))
    return lus


class TestVocabulaireDesConges:
    def test_un_conge_paye_est_lisible_par_la_paie(self):
        ecrit = ABSENCE_TYPE_TO_CALENDAR_TYPE["conge_paye"]
        lus = _types_lus_par_la_paie()
        assert ecrit in lus, (
            f"La validation d'un congé payé écrit « {ecrit} » sur le calendrier, "
            f"or le moteur de paie ne connaît que {sorted(lus)}. Le jour est "
            "alors ni travaillé ni en congé : il disparaît du bulletin."
        )

    def test_le_detecteur_voit_bien_le_vocabulaire_de_la_paie(self):
        """Sans ça, le test ci-dessus passerait à vide."""
        lus = _types_lus_par_la_paie()
        assert "conges_payes" in lus and "ferie" in lus, (
            f"Le balayage du moteur n'a rien trouvé d'attendu : {sorted(lus)}"
        )
