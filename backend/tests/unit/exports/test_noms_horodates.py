"""[I16] Chaque fichier d'export porte un horodatage dans son nom.

Avant : un chemin fixe par période (`virement_salaires_2026_06.csv`) et un dépôt
en `upsert` ; un export régénéré écrasait le fichier du précédent. L'historique
du 12/06 (virement de 11 228,22 €) renvoyait le fichier du 15/06 (10 246,18 €).
Seul le journal de paie portait déjà un horodatage.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from app.modules.exports.application import service as export_service
from app.modules.exports.schemas import ExportGenerateRequest

pytestmark = pytest.mark.unit


def _generer_virement(instant: float) -> tuple[list[str], object]:
    deposes: list[str] = []
    req = ExportGenerateRequest(
        export_type="virement_salaires", period="2026-06", format="csv"
    )
    with (
        patch.object(export_service.time, "time", return_value=instant),
        patch.object(export_service.providers, "generate_paiement_salaires_export", return_value=b"csv"),
        patch.object(export_service.providers, "generate_sepa_bank_file", return_value=b"<xml/>"),
        patch.object(
            export_service.providers,
            "get_paiement_salaires_data",
            return_value=([], {"employees_count": 1}, [], []),
        ),
        patch.object(
            export_service,
            "upload_export_file",
            side_effect=lambda _b, chemin, *_a: deposes.append(chemin) or chemin,
        ),
        patch.object(export_service, "create_signed_url", side_effect=lambda chemin, *_: f"https://{chemin}"),
        patch.object(export_service.commands, "record_export_history", return_value="exp-1"),
    ):
        reponse = export_service._generate_virement_salaires("comp-1", "u-1", "RH", req)
    return deposes, reponse


def test_deux_virements_du_meme_mois_ne_s_ecrasent_plus():
    premier, _ = _generer_virement(1781258400.0)
    second, _ = _generer_virement(1781517600.0)

    assert len(premier) == len(second) == 2
    assert set(premier).isdisjoint(second), "le second fichier écraserait le premier"


def test_le_nom_affiche_est_celui_du_fichier_depose_et_porte_l_horodatage():
    deposes, reponse = _generer_virement(1781258400.0)

    assert [Path(c).name for c in deposes] == [
        "virement_salaires_2026_06_1781258400.csv",
        "virement_salaires_sepa_2026_06_1781258400.xml",
    ]
    assert [f.filename for f in reponse.files] == [Path(c).name for c in deposes]
    assert set(reponse.download_urls) == {Path(c).name for c in deposes}


def test_tous_les_noms_de_fichier_d_export_sont_horodates():
    """Garde : aucun nom de fichier d'export n'est plus fixé par la seule période."""
    source = Path(export_service.__file__).read_text(encoding="utf-8")
    affectations = re.findall(r"^\s*(\w*filename) = (.+)$", source, re.MULTILINE)
    assert affectations, "noms de fichier introuvables dans le service"
    non_horodates = [
        f"{nom} = {valeur}"
        for nom, valeur in affectations
        if not valeur.startswith("_horodater(")
    ]
    assert non_horodates == []
