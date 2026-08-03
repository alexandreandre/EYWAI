"""Conformité de notre DSN face à celle réellement déposée par le cabinet.

Les entrées vivent hors dépôt (`data/_dsn_conformance/`, gitignoré) parce
qu'elles contiennent l'état civil et la paie de salariés réels. Sans elles les
tests se marquent `skipped` : la CI reste verte, l'exécution locale reste
complète. Pour les produire :

    python scripts/dsn_conformance_snapshot.py

Le chantier avance bloc par bloc. `BLOCS_LIVRES` liste ce qui est censé être
conforme aujourd'hui ; tout le reste est neutralisé. Un lot se clôt en ajoutant
ses blocs ici et en gardant les tests verts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.conformance import EcartAttendu, comparer
from app.modules.dsn_export.domain.settings import depuis_dict
from app.modules.dsn_export.domain.writer import encode_dsn_bytes

FIXTURES = Path(__file__).resolve().parents[4] / "data" / "_dsn_conformance"

# Blocs dont la conformité est acquise. À étendre lot par lot.
BLOCS_LIVRES: List[str] = [
    "S10.G00.00",
    "S10.G00.01",
    "S20.G00.05",
    "S20.G00.07",
    "S21.G00.06",
    "S21.G00.11",
    "S90.G00.90",
]

# Tout ce qui n'est pas encore livré, neutralisé pour ne pas masquer les
# régressions sur ce qui l'est.
BLOCS_A_VENIR: List[str] = [
    "S10.G00.02",
    "S21.G00.15",
    "S21.G00.20",
    "S21.G00.22",
    "S21.G00.23",
    "S21.G00.30",
    "S21.G00.31",
    "S21.G00.40",
    "S21.G00.41",
    "S21.G00.44",
    "S21.G00.50",
    "S21.G00.51",
    "S21.G00.52",
    "S21.G00.53",
    "S21.G00.54",
    "S21.G00.58",
    "S21.G00.60",
    "S21.G00.62",
    "S21.G00.65",
    "S21.G00.70",
    "S21.G00.71",
    "S21.G00.78",
    "S21.G00.79",
    "S21.G00.81",
    "S21.G00.85",
    "S21.G00.86",
]

ECARTS_ATTENDUS: List[EcartAttendu] = [
    EcartAttendu(
        rubrique="S10.G00.00.001",
        motif="nom du logiciel émetteur : EYWAI, pas Cegid",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S10.G00.00.002",
        motif="éditeur du logiciel émetteur : EYWAI, pas Cegid",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S10.G00.00.003",
        motif="version de notre logiciel, sans rapport avec celle du cabinet",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S10.G00.00.008",
        motif="numéro d'ordre de l'envoi, propre à l'émetteur",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S20.G00.05.007",
        motif="date de constitution du fichier : celle du jour où on le produit",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.06.004",
        motif="libellé d'adresse issu de notre fiche société, forme libre",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.11.003",
        motif="libellé d'adresse issu de notre fiche société, forme libre",
        depuis="2026-08-03",
    ),
]


def instantanes() -> List[Tuple[str, str, Path]]:
    if not FIXTURES.exists():
        return []
    trouves = []
    for input_json in sorted(FIXTURES.glob("*/*/input.json")):
        repertoire = input_json.parent
        if (repertoire / "reference.dsn").exists():
            trouves.append((repertoire.parent.name, repertoire.name, repertoire))
    return trouves


INSTANTANES = instantanes()

besoin_de_fixtures = pytest.mark.skipif(
    not INSTANTANES,
    reason="instantanés absents : lancer scripts/dsn_conformance_snapshot.py",
)


def generer(donnees: Dict[str, Any]) -> bytes:
    fichier, _avertissements = build_parsed_dsn_from_payroll(
        donnees["company"],
        donnees["employees_data"],
        donnees["periode"],
        file_name=f"dsn_mensuelle_{donnees['periode'].replace('-', '_')}.dsn",
        settings=depuis_dict(donnees.get("dsn_settings")),
    )
    return encode_dsn_bytes(fichier)


@besoin_de_fixtures
@pytest.mark.parametrize(
    "societe,periode,repertoire",
    INSTANTANES,
    ids=[f"{s}-{p}" for s, p, _ in INSTANTANES],
)
def test_blocs_livres_sont_conformes(societe: str, periode: str, repertoire: Path):
    donnees = json.loads((repertoire / "input.json").read_text())
    rapport = comparer(
        generer(donnees),
        (repertoire / "reference.dsn").read_bytes(),
        ecarts_attendus=ECARTS_ATTENDUS,
        rubriques_hors_perimetre=BLOCS_A_VENIR,
    )
    assert rapport.conforme, f"{societe} {periode} :\n{rapport.texte()}"


@besoin_de_fixtures
def test_aucun_bloc_oublie_entre_livres_et_a_venir():
    """Tout bloc vu dans une référence est soit livré, soit explicitement à venir."""
    connus = set(BLOCS_LIVRES) | set(BLOCS_A_VENIR)
    for _societe, _periode, repertoire in INSTANTANES:
        contenu = (repertoire / "reference.dsn").read_bytes().decode("latin-1")
        for ligne in contenu.splitlines():
            if "," not in ligne:
                continue
            rubrique = ligne.split(",", 1)[0].strip()
            if rubrique.count(".") == 3:
                bloc = rubrique.rsplit(".", 1)[0]
                assert bloc in connus, f"bloc {bloc} ni livré ni planifié"
